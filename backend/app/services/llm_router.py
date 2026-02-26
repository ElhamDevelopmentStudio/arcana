from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping
from typing import Any

import requests
from sqlalchemy.orm import Session

from app.services.llm_task_types import LLMTaskType, LLMTaskTypeError, normalize_task_type
from app.services import quota


_SILICONFLOW_BASE_URL_DEFAULT = "https://api.siliconflow.cn/v1"
_DEFAULT_ERROR_RETRY_ATTEMPTS: dict[str, int] = {
    "timeout": 2,
    "service_unavailable": 2,
    "other": 1,
}
_DEFAULT_FAILOVER_ERROR_CODES = {"rate_limit", "quota", "timeout", "service_unavailable", "other"}


@dataclass(frozen=True)
class LLMDispatchRequest:
    endpoint: str
    payload: dict[str, Any]
    headers: dict[str, str]


@dataclass(frozen=True)
class LLMDispatchResponse:
    status_code: int | None
    body: dict[str, Any] | None
    headers: dict[str, str]
    transport_error: str | None = None


class LLMDispatcher:
    def dispatch(self, request: LLMDispatchRequest) -> LLMDispatchResponse:
        try:
            response = requests.post(
                request.endpoint,
                json=request.payload,
                headers=request.headers,
                timeout=20,
            )
            return LLMDispatchResponse(
                status_code=getattr(response, "status_code", 200),
                body=_coerce_json_response(response=response),
                headers={
                    str(header_key): str(header_value)
                    for header_key, header_value in getattr(response, "headers", {}).items()
                },
            )
        except requests.Timeout:
            return LLMDispatchResponse(
                status_code=None,
                body=None,
                headers={},
                transport_error="timeout",
            )
        except requests.RequestException as exc:
            response = getattr(exc, "response", None)
            if response is None:
                return LLMDispatchResponse(
                    status_code=None,
                    body=None,
                    headers={},
                    transport_error="other",
                )

            return LLMDispatchResponse(
                status_code=getattr(response, "status_code", 200),
                body=_coerce_json_response(response=response),
                headers={
                    str(header_key): str(header_value)
                    for header_key, header_value in getattr(response, "headers", {}).items()
                },
                transport_error="provider_error",
            )


class LLMResponseParser:
    def parse(
        self,
        request: LLMRequest,
        provider_name: str,
        model_identifier: str,
        dispatch_response: LLMDispatchResponse,
    ) -> LLMResponse:
        provider = _normalize_provider_name(provider_name)
        status_code = dispatch_response.status_code
        headers = dispatch_response.headers
        body = dispatch_response.body or {}
        transport_error = dispatch_response.transport_error

        if status_code == 429:
            rate_limit_reset_at = _extract_rate_limit_reset_timestamp(response=headers)
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

        if status_code is not None and status_code >= 400:
            error_code, rate_limit_reset_at = _classify_provider_error(
                status_code=status_code,
                headers=headers,
                body=body,
            )
            return LLMResponse(
                provider_used=provider,
                model_identifier=model_identifier,
                raw_output="",
                parsed_output={},
                confidence=None,
                token_usage_estimate=None,
                success_flag=False,
                error_code=error_code,
                rate_limit_reset_at=rate_limit_reset_at,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        if status_code is None:
            if transport_error == "timeout":
                return LLMResponse(
                    provider_used=provider,
                    model_identifier=model_identifier,
                    raw_output="",
                    parsed_output={},
                    confidence=None,
                    token_usage_estimate=None,
                    success_flag=False,
                    error_code="timeout",
                    rate_limit_reset_at=None,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
            if transport_error is not None:
                return LLMResponse(
                    provider_used=provider,
                    model_identifier=model_identifier,
                    raw_output="",
                    parsed_output={},
                    confidence=None,
                    token_usage_estimate=None,
                    success_flag=False,
                    error_code="other",
                    rate_limit_reset_at=None,
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
                error_code="other",
                rate_limit_reset_at=None,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        if status_code is not None and status_code < 200:
            return LLMResponse(
                provider_used=provider,
                model_identifier=model_identifier,
                raw_output="",
                parsed_output={},
                confidence=None,
                token_usage_estimate=None,
                success_flag=False,
                error_code="other",
                rate_limit_reset_at=None,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        choices = body.get("choices", [])
        raw_output = ""
        if choices:
            message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
            raw_output = message.get("content", "") if isinstance(message, dict) else ""

        token_usage = body.get("usage", {}).get("total_tokens") if isinstance(body.get("usage", {}), dict) else None
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


class DefaultLLMDispatcher(LLMDispatcher):
    pass


class DefaultLLMResponseParser(LLMResponseParser):
    pass


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


@dataclass(frozen=True)
class LLMProviderConfig:
    provider_name: str
    base_url: str
    model_identifier: str
    api_key: str | None


class LLMRouter:
    def __init__(
        self,
        openrouter_base_url: str,
        *,
        dispatcher: LLMDispatcher | None = None,
        response_parser: LLMResponseParser | None = None,
        error_class_retry_attempts: Mapping[str, int] | None = None,
    ) -> None:
        self.base_url = openrouter_base_url.rstrip("/")
        self.dispatcher = dispatcher or DefaultLLMDispatcher()
        self.response_parser = response_parser or DefaultLLMResponseParser()
        self.error_class_retry_attempts = dict(_DEFAULT_ERROR_RETRY_ATTEMPTS)
        if error_class_retry_attempts is not None:
            self.error_class_retry_attempts.update(error_class_retry_attempts)

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

        return self._call_provider_with_retry(
            request=request,
            provider_name=provider_name,
            model_identifier=model_identifier,
            api_key=api_key,
            base_url=self.base_url,
            task_type=task_type,
        )

    def call_with_failover(
        self,
        request: LLMRequest,
        provider_configs: tuple[LLMProviderConfig, ...],
    ) -> LLMResponse:
        if not provider_configs:
            return LLMResponse(
                provider_used="",
                model_identifier="",
                raw_output="",
                parsed_output={},
                confidence=None,
                token_usage_estimate=None,
                success_flag=False,
                error_code="unsupported_provider",
                rate_limit_reset_at=None,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        try:
            task_type = normalize_task_type(request.task_type)
        except LLMTaskTypeError:
            return LLMResponse(
                provider_used=provider_configs[0].provider_name,
                model_identifier=provider_configs[0].model_identifier,
                raw_output="",
                parsed_output={},
                confidence=None,
                token_usage_estimate=None,
                success_flag=False,
                error_code="unsupported_task_type",
                rate_limit_reset_at=None,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        final_response: LLMResponse | None = None
        for provider_config in provider_configs:
            response = self._call_provider_with_retry(
                request=request,
                provider_name=provider_config.provider_name,
                model_identifier=provider_config.model_identifier,
                api_key=provider_config.api_key,
                base_url=provider_config.base_url,
                task_type=task_type,
            )
            final_response = response
            if response.success_flag:
                return response
            if response.error_code not in _DEFAULT_FAILOVER_ERROR_CODES:
                return response

        assert final_response is not None
        return final_response

    def _call_provider_with_retry(
        self,
        *,
        request: LLMRequest,
        provider_name: str,
        model_identifier: str,
        api_key: str | None,
        base_url: str,
        task_type: str,
    ) -> LLMResponse:
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
        endpoint = f"{base_url.rstrip('/')}/chat/completions"
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

        dispatch_request = LLMDispatchRequest(endpoint=endpoint, payload=payload, headers=headers)
        attempt = 0
        while True:
            attempt += 1
            dispatch_response = self.dispatcher.dispatch(request=dispatch_request)
            response = self.response_parser.parse(
                request=request,
                provider_name=provider,
                model_identifier=model_identifier,
                dispatch_response=dispatch_response,
            )

            if response.success_flag:
                return response

            max_attempts = self.error_class_retry_attempts.get(response.error_code or "", 1)
            if response.error_code is None or attempt >= max_attempts:
                return response

            continue


def _coerce_json_response(response: object) -> dict[str, Any] | None:
    if response is None:
        return None

    body = getattr(response, "json", None)
    if not callable(body):
        return None

    try:
        payload = body()
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _classify_provider_error(
    status_code: int,
    headers: dict[str, str],
    body: dict[str, Any],
) -> tuple[str, datetime | None]:
    if status_code == 408:
        return "timeout", None

    if status_code in (500, 502, 503, 504):
        return "service_unavailable", None

    if status_code in (401, 402, 403):
        if _contains_indicator(body=body, headers=headers, indicators=("quota", "limit", "billing", "credit")):
            return "quota", None
        return "other", None

    if status_code >= 500:
        return "service_unavailable", None

    return "other", None


def _contains_indicator(body: dict[str, Any], headers: dict[str, str], indicators: tuple[str, ...]) -> bool:
    for text in _collect_error_messages(body=body, headers=headers):
        normalized = text.strip().lower()
        if not normalized:
            continue
        if any(indicator in normalized for indicator in indicators):
            return True
    return False


def _collect_error_messages(body: dict[str, Any], headers: dict[str, str]) -> tuple[str, ...]:
    texts: list[str] = []
    for value in headers.values():
        if isinstance(value, str):
            texts.append(value)

    if isinstance(body, dict):
        root_message = body.get("message")
        if isinstance(root_message, str):
            texts.append(root_message)

        error_block = body.get("error")
        if isinstance(error_block, str):
            texts.append(error_block)
        elif isinstance(error_block, dict):
            for key in ("message", "code", "type", "error", "name"):
                message_part = error_block.get(key)
                if isinstance(message_part, str):
                    texts.append(message_part)

        for text_candidate in (body.get("detail"), body.get("title")):
            if isinstance(text_candidate, str):
                texts.append(text_candidate)

    return tuple(texts)


def _normalize_provider_name(value: str) -> str:
    return str(value).strip().lower()


def _extract_rate_limit_reset_timestamp(response: Any) -> datetime | None:
    if isinstance(response, dict):
        headers = response
    else:
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


def _resolve_api_key_list(settings: Any, metadata: LLMProviderMetadata) -> list[str]:
    if metadata.settings_key_list_key is not None:
        candidate_keys = _coerce_api_key_list(getattr(settings, metadata.settings_key_list_key, None))
        if candidate_keys:
            return candidate_keys

    api_key = getattr(settings, metadata.settings_key_key, None)
    if api_key is not None and str(api_key).strip():
        return [str(api_key).strip()]
    return []


def get_provider_api_keys(settings: Any, provider_name: str) -> list[str]:
    metadata = _LLM_PROVIDER_REGISTRY.get(_normalize_provider_name(provider_name))
    if metadata is None:
        return []

    return _resolve_api_key_list(settings=settings, metadata=metadata)


def is_provider_requestable(
    session: Session,
    settings: Any,
    provider_name: str,
    max_calls_per_day: int,
) -> tuple[bool, str | None]:
    provider = _normalize_provider_name(provider_name)
    if not is_supported_provider(provider):
        return False, "unsupported_provider"

    from app.services.provider_toggle import is_provider_enabled

    if not is_provider_enabled(session=session, provider=provider):
        return False, "provider_disabled"

    if not quota.is_provider_available_for_request(session=session, provider=provider, max_calls_per_day=max_calls_per_day):
        return False, "quota_reached"

    _, _, runtime_api_key = get_provider_runtime_settings(settings=settings, provider_name=provider)
    api_keys = get_provider_api_keys(settings=settings, provider_name=provider)
    if not api_keys and runtime_api_key:
        api_keys = [runtime_api_key]

    if not api_keys:
        return True, None

    for key in api_keys:
        if not quota.is_api_key_available_for_request(
            session=session,
            provider=provider,
            provider_api_key=key,
            max_calls_per_day=max_calls_per_day,
        ):
            continue
        return True, None

    return False, "quota_reached"


def select_probe_provider_candidates(
    session: Session,
    settings: Any,
    requested_provider: str,
    max_calls_per_day: int,
) -> tuple[str, ...]:
    requested = _normalize_provider_name(requested_provider)
    candidate_order = [requested]
    for provider in get_provider_priority_order(settings=settings):
        normalized = _normalize_provider_name(provider)
        if normalized and normalized not in candidate_order:
            candidate_order.append(normalized)

    selected: list[str] = []
    seen: set[str] = set()

    for provider in candidate_order:
        if not provider or provider in seen:
            continue
        seen.add(provider)
        requestable, _ = is_provider_requestable(
            session=session,
            settings=settings,
            provider_name=provider,
            max_calls_per_day=max_calls_per_day,
        )
        if requestable:
            selected.append(provider)

    return tuple(selected)


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
    provider_api_keys = get_provider_api_keys(settings=settings, provider_name=normalized_provider)
    api_key = provider_api_keys[0] if provider_api_keys else None
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
