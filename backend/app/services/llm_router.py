from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests

from app.services.llm_task_types import LLMTaskType, LLMTaskTypeError, normalize_task_type


_SILICONFLOW_BASE_URL_DEFAULT = "https://api.siliconflow.cn/v1"


@dataclass(frozen=True)
class LLMProviderMetadata:
    settings_base_url_key: str
    settings_model_key: str
    settings_key_key: str
    settings_key_list_key: str | None = None


_LLM_PROVIDER_REGISTRY: dict[str, LLMProviderMetadata] = {
    "openrouter": LLMProviderMetadata(
        settings_base_url_key="openrouter_base_url",
        settings_model_key="openrouter_model",
        settings_key_key="openrouter_api_key",
        settings_key_list_key="openrouter_api_keys",
    ),
    "siliconflow": LLMProviderMetadata(
        settings_base_url_key="siliconflow_base_url",
        settings_model_key="siliconflow_model",
        settings_key_key="siliconflow_api_key",
        settings_key_list_key="siliconflow_api_keys",
    ),
    "groq": LLMProviderMetadata(
        settings_base_url_key="groq_base_url",
        settings_model_key="groq_model",
        settings_key_key="groq_api_key",
        settings_key_list_key="groq_api_keys",
    ),
}


@dataclass
class LLMRequest:
    request_id: str
    project_id: int
    task_type: str
    input_text: str
    expected_schema: dict[str, Any]
    configuration_snapshot_id: str


@dataclass
class LLMResponse:
    provider_used: str
    model_identifier: str
    raw_output: str
    parsed_output: dict[str, Any]
    confidence: float | None
    token_usage_estimate: int | None
    success_flag: bool
    error_code: str | None
    rate_limit_reset_at: datetime | None
    timestamp: str


class LLMRouter:
    def __init__(self, openrouter_base_url: str) -> None:
        self.base_url = openrouter_base_url.rstrip("/")

    def call(
        self,
        request: LLMRequest,
        provider_name: str,
        model_identifier: str,
        api_key: str | None,
    ) -> LLMResponse:
        try:
            task_type = normalize_task_type(request.task_type)
        except LLMTaskTypeError:
            return LLMResponse(
                provider_used=provider_name,
                model_identifier=model_identifier,
                raw_output="",
                parsed_output={},
                confidence=None,
                token_usage_estimate=None,
                success_flag=False,
                error_code="unsupported_task_type",
                rate_limit_reset_at=None,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        provider = _normalize_provider_name(provider_name)

        if not is_supported_provider(provider):
            return LLMResponse(
                provider_used=provider,
                model_identifier=model_identifier,
                raw_output="",
                parsed_output={},
                confidence=None,
                token_usage_estimate=None,
                success_flag=False,
                error_code="unsupported_provider",
                rate_limit_reset_at=None,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        if not api_key:
            return LLMResponse(
                provider_used=provider,
                model_identifier=model_identifier,
                raw_output="",
                parsed_output={},
                confidence=None,
                token_usage_estimate=None,
                success_flag=False,
                error_code="missing_api_key",
                rate_limit_reset_at=None,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        system_prompt, user_prompt = _build_task_prompts(task_type=task_type, input_text=request.input_text)
        endpoint = f"{self.base_url}/chat/completions"
        payload = {
            "model": model_identifier,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            "temperature": 0,
            "max_tokens": 60,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(endpoint, json=payload, headers=headers, timeout=20)
            if getattr(response, "status_code", 200) == 429:
                rate_limit_reset_at = _extract_rate_limit_reset_timestamp(response=response)
                return LLMResponse(
                    provider_used=provider,
                    model_identifier=model_identifier,
                    raw_output="",
                    parsed_output={},
                    confidence=None,
                    token_usage_estimate=None,
                    success_flag=False,
                    error_code="rate_limit",
                    rate_limit_reset_at=rate_limit_reset_at,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )

            response.raise_for_status()
            body = response.json()
            choices = body.get("choices", [])
            raw_output = ""
            if choices:
                raw_output = choices[0].get("message", {}).get("content", "")

            token_usage = body.get("usage", {}).get("total_tokens")
            return LLMResponse(
                provider_used=provider,
                model_identifier=model_identifier,
                raw_output=raw_output,
                parsed_output={"raw": raw_output},
                confidence=None,
                token_usage_estimate=token_usage,
                success_flag=True,
                error_code=None,
                rate_limit_reset_at=None,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        except requests.RequestException as exc:
            status_code = None
            response = getattr(exc, "response", None)
            if response is not None:
                status_code = getattr(response, "status_code", None)
            if status_code == 429:
                rate_limit_reset_at = _extract_rate_limit_reset_timestamp(response=response)
                return LLMResponse(
                    provider_used=provider,
                    model_identifier=model_identifier,
                    raw_output="",
                    parsed_output={},
                    confidence=None,
                    token_usage_estimate=None,
                    success_flag=False,
                    error_code="rate_limit",
                    rate_limit_reset_at=rate_limit_reset_at,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )

            return LLMResponse(
                provider_used=provider,
                model_identifier=model_identifier,
                raw_output="",
                parsed_output={},
                confidence=None,
                token_usage_estimate=None,
                success_flag=False,
                error_code="provider_error",
                rate_limit_reset_at=None,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )


def _normalize_provider_name(value: str) -> str:
    return str(value).strip().lower()


def _extract_rate_limit_reset_timestamp(response: Any) -> datetime | None:
    headers = getattr(response, "headers", None)
    if not headers:
        return None

    reset_candidates = (
        headers.get("x-ratelimit-reset"),
        headers.get("x-ratelimit-reset-requests"),
        headers.get("x-rate-limit-reset"),
        headers.get("retry-after"),
        headers.get("x-rate-limit-reset-requests"),
    )

    for candidate in reset_candidates:
        parsed = _coerce_rate_limit_reset_timestamp(candidate)
        if parsed is not None:
            return parsed

    return None


def _coerce_rate_limit_reset_timestamp(value: object) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)

    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None

        if text.isdigit():
            return datetime.fromtimestamp(float(text), tz=timezone.utc)

        try:
            value_as_float = float(text)
        except ValueError:
            value_as_float = None
        if value_as_float is not None:
            return datetime.fromtimestamp(value_as_float, tz=timezone.utc)

        for date_format in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S GMT"):
            try:
                return datetime.strptime(text, date_format).replace(tzinfo=timezone.utc)
            except ValueError:
                pass

        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None

    return None


def is_supported_provider(provider_name: str) -> bool:
    return _normalize_provider_name(provider_name) in _LLM_PROVIDER_REGISTRY


def get_supported_providers() -> tuple[str, ...]:
    return tuple(sorted(_LLM_PROVIDER_REGISTRY.keys()))


def _coerce_provider_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        candidates = [str(item).strip() for item in value]
        return [candidate for candidate in candidates if candidate]
    if isinstance(value, tuple):
        candidates = [str(item).strip() for item in value]
        return [candidate for candidate in candidates if candidate]
    if isinstance(value, str):
        candidates = [item.strip() for item in value.split(",")]
        return [candidate for candidate in candidates if candidate]
    candidate = str(value).strip()
    return [candidate] if candidate else []


def get_provider_priority_order(settings: Any) -> tuple[str, ...]:
    configured_order = _coerce_provider_list(getattr(settings, "llm_provider_priority_order", None))
    normalized_order: list[str] = []
    seen: set[str] = set()
    for value in configured_order:
        normalized = _normalize_provider_name(value)
        if not normalized or normalized not in _LLM_PROVIDER_REGISTRY or normalized in seen:
            continue
        seen.add(normalized)
        normalized_order.append(normalized)

    if normalized_order:
        return tuple(normalized_order)

    return get_supported_providers()


def _coerce_api_key_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        candidates = [str(item).strip() for item in value]
        return [candidate for candidate in candidates if candidate]
    if isinstance(value, tuple):
        candidates = [str(item).strip() for item in value]
        return [candidate for candidate in candidates if candidate]
    if isinstance(value, str):
        parts = [item.strip() for item in value.split(",")]
        return [part for part in parts if part]
    return [str(value).strip()] if str(value).strip() else []


def _resolve_api_key(settings: Any, metadata: LLMProviderMetadata) -> str | None:
    if metadata.settings_key_list_key is not None:
        candidate_keys = _coerce_api_key_list(getattr(settings, metadata.settings_key_list_key, None))
        if candidate_keys:
            return candidate_keys[0]

    api_key = getattr(settings, metadata.settings_key_key, None)
    if api_key is not None and str(api_key).strip():
        return str(api_key).strip()
    return None


def get_provider_runtime_settings(settings: Any, provider_name: str) -> tuple[str, str, str | None]:
    normalized_provider = _normalize_provider_name(provider_name)
    metadata = _LLM_PROVIDER_REGISTRY.get(normalized_provider)

    if metadata is None:
        return (
            settings.openrouter_base_url,
            settings.openrouter_model,
            settings.openrouter_api_key,
        )

    base_url = str(getattr(settings, metadata.settings_base_url_key))
    if normalized_provider == "siliconflow" and not base_url:
        base_url = _SILICONFLOW_BASE_URL_DEFAULT

    model_identifier = str(getattr(settings, metadata.settings_model_key))
    api_key = _resolve_api_key(settings=settings, metadata=metadata)
    if api_key is None:
        fallback = getattr(settings, "openrouter_api_key", None)
        api_key = str(fallback) if isinstance(fallback, str) else None

    return (base_url, model_identifier, api_key)


def _build_task_prompts(task_type: str, input_text: str) -> tuple[str, str]:
    if task_type == LLMTaskType.SENTIMENT_PROBE.value:
        return (
            "You are a classifier. Respond with JSON only: "
            '{"sentiment":"positive|negative|neutral","confidence":0.0-1.0}',
            f"Classify this text for valence only: {input_text}",
        )
    if task_type == LLMTaskType.EMOTION_REFINEMENT.value:
        return (
            (
                "You are a literary emotion analyst. Respond with JSON only using the keys "
                '"emotion_primary","emotion_secondary","confidence".'
            ),
            f"Refine emotional analysis for this text with nuanced literary context: {input_text}",
        )
    if task_type == LLMTaskType.SPEAKER_RESOLUTION.value:
        return (
            (
                "You are a speaker-attribution analyst. Respond with JSON only using keys "
                '"speaker","confidence","evidence".'
            ),
            f"Resolve likely speaker attribution for this text and provide confidence: {input_text}",
        )
    if task_type == LLMTaskType.CHARACTER_EXTRACTION.value:
        return (
            (
                "You are a character mention extractor. Respond with JSON only using keys "
                '"character_name","confidence","evidence".'
            ),
            f"Identify the principal character references in this text: {input_text}",
        )
    if task_type == LLMTaskType.EDGE_CASE_STRUCTURAL_INTERPRETATION.value:
        return (
            (
                "You are a narrative structure analyst. Respond with JSON only using keys "
                '"structure_type","confidence","evidence".'
            ),
            f"Interpret possible structural edge case in this text: {input_text}",
        )
    if task_type == LLMTaskType.SCENE_CLASSIFICATION.value:
        return (
            (
                "You are a scene-stage classifier. Respond with JSON only using keys "
                '"scene_type","confidence","evidence".'
            ),
            f"Classify scene structure for this text: {input_text}",
        )
    return (
        "You are a classifier. Respond with JSON only.",
        f"Classify this text: {input_text}",
    )
