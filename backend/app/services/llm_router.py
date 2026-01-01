from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests

from app.services.llm_task_types import LLMTaskType, LLMTaskTypeError, normalize_task_type


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
    timestamp: str


class LLMRouter:
    def __init__(self, openrouter_base_url: str) -> None:
        self.openrouter_base_url = openrouter_base_url.rstrip("/")

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
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        provider = provider_name.lower()

        if provider != "openrouter":
            return LLMResponse(
                provider_used=provider,
                model_identifier=model_identifier,
                raw_output="",
                parsed_output={},
                confidence=None,
                token_usage_estimate=None,
                success_flag=False,
                error_code="unsupported_provider",
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
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        system_prompt, user_prompt = _build_task_prompts(task_type=task_type, input_text=request.input_text)
        endpoint = f"{self.openrouter_base_url}/chat/completions"
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
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        except requests.RequestException:
            return LLMResponse(
                provider_used=provider,
                model_identifier=model_identifier,
                raw_output="",
                parsed_output={},
                confidence=None,
                token_usage_estimate=None,
                success_flag=False,
                error_code="provider_error",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )


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
