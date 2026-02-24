from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests


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

        endpoint = f"{self.openrouter_base_url}/chat/completions"
        payload = {
            "model": model_identifier,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a classifier. Respond with JSON only: "
                        '{"sentiment":"positive|negative|neutral","confidence":0.0-1.0}'
                    ),
                },
                {
                    "role": "user",
                    "content": f"Classify this text for valence only: {request.input_text}",
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
