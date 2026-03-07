import json
import os
import re
from pathlib import Path
from typing import Any

import pytest

from app.services.llm_router import LLMRequest, LLMRouter
from app.services.llm_task_types import LLMTaskType

RUN_OPENROUTER_INTEGRATION = os.getenv("RUN_OPENROUTER_INTEGRATION") == "1"


def _read_backend_env_value(key: str) -> str | None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return None

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        if name == key:
            return value.strip().strip("\"'")
    return None


def _openrouter_config() -> tuple[str, str, str]:
    api_key = os.getenv("OPENROUTER_API_KEY") or _read_backend_env_value("OPENROUTER_API_KEY")
    model = os.getenv("OPENROUTER_MODEL") or _read_backend_env_value("OPENROUTER_MODEL") or "openai/gpt-4o-mini"
    base_url = os.getenv("OPENROUTER_BASE_URL") or _read_backend_env_value("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1"

    if not api_key:
        pytest.skip("Set OPENROUTER_API_KEY in the environment or backend/.env to run OpenRouter tests.")
    if not RUN_OPENROUTER_INTEGRATION:
        pytest.skip("Set RUN_OPENROUTER_INTEGRATION=1 to execute OpenRouter integration tests.")

    return api_key, model, base_url.rstrip("/")


def _parse_llm_json(raw_output: str) -> dict[str, Any] | None:
    candidate = raw_output.strip()
    if not candidate:
        return None

    # Try direct parse
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # Remove common fenced blocks like ```json ... ```
    if candidate.startswith("```"):
        fenced = re.sub(r"^```(?:json)?\n?", "", candidate, flags=re.IGNORECASE).rstrip("`").strip()
        try:
            return json.loads(fenced)
        except json.JSONDecodeError:
            pass

    # Fall back to first/last brace extraction
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(candidate[start : end + 1])
    except json.JSONDecodeError:
        return None


@pytest.mark.slow
def test_openrouter_connection_smoke_call() -> None:
    api_key, model, base_url = _openrouter_config()
    router = LLMRouter(openrouter_base_url=base_url)

    request = LLMRequest(
        request_id="openrouter-smoke",
        project_id=1,
        task_type=LLMTaskType.SENTIMENT_PROBE.value,
        input_text="The moonlight shimmered over the harbor as the crowd celebrated.",
        expected_schema={"sentiment": "string", "confidence": "number"},
        configuration_snapshot_id="test-openrouter-smoke",
    )

    response = router.call(
        request=request,
        provider_name="openrouter",
        model_identifier=model,
        api_key=api_key,
    )

    assert response.success_flag is True
    assert response.error_code is None
    assert response.provider_used == "openrouter"
    assert response.model_identifier == model
    assert response.raw_output.strip() != ""
    assert response.raw_output is not None


@pytest.mark.slow
def test_openrouter_sentiment_probe_response_matches_expected_fields() -> None:
    api_key, model, base_url = _openrouter_config()
    router = LLMRouter(openrouter_base_url=base_url)

    request = LLMRequest(
        request_id="openrouter-usecase-sentiment",
        project_id=1,
        task_type=LLMTaskType.SENTIMENT_PROBE.value,
        input_text="She whispered softly, and the room felt at peace.",
        expected_schema={"sentiment": "string", "confidence": "number"},
        configuration_snapshot_id="test-openrouter-usecase",
    )

    response = router.call(
        request=request,
        provider_name="openrouter",
        model_identifier=model,
        api_key=api_key,
    )

    assert response.success_flag is True
    parsed = _parse_llm_json(response.raw_output)
    assert parsed is not None, f"Expected JSON-like raw output, got: {response.raw_output}"
    assert set(parsed.keys()) >= {"sentiment", "confidence"}
    assert parsed["sentiment"] in {"positive", "negative", "neutral"}
    confidence: Any = parsed["confidence"]
    assert isinstance(confidence, int | float)
    assert 0.0 <= float(confidence) <= 1.0
