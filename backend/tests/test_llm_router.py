import os
from pathlib import Path
from types import SimpleNamespace

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
import app.services.llm_router as llm_router
from app.models import ProviderToggle
from app.services.quota import consume_api_key_quota, consume_quota

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_llm_router.db"


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_llm_router.db")
    if db_file.exists():
        db_file.unlink()


def _new_session():
    return get_session_factory()()


def test_is_supported_provider_includes_siliconflow() -> None:
    assert llm_router.is_supported_provider("siliconflow") is True
    assert llm_router.is_supported_provider("openrouter") is True
    assert llm_router.is_supported_provider("groq") is True


def test_select_probe_provider_candidates_prefers_requested_then_priority() -> None:
    session = _new_session()
    try:
        settings = SimpleNamespace(
            llm_provider_priority_order=["groq", "openrouter", "siliconflow"],
            openrouter_base_url="https://api.openrouter.ai/v1",
            openrouter_model="openrouter-model",
            openrouter_api_key="openrouter-key",
            groq_base_url="https://api.groq.com/openai/v1",
            groq_model="groq-model",
            groq_api_key="groq-key",
            siliconflow_base_url="https://api.siliconflow.cn/v1",
            siliconflow_model="siliconflow-model",
            siliconflow_api_key="siliconflow-key",
        )

        candidates = llm_router.select_probe_provider_candidates(
            session=session,
            settings=settings,
            requested_provider="openrouter",
            max_calls_per_day=10,
        )

        assert candidates == ("openrouter", "groq", "siliconflow")
    finally:
        session.close()


def test_select_probe_provider_candidates_skips_disabled_provider_and_uses_next_priority() -> None:
    session = _new_session()
    try:
        session.query(ProviderToggle).filter(ProviderToggle.provider == "openrouter").delete()
        session.add(ProviderToggle(provider="openrouter", enabled=False))
        session.flush()

        settings = SimpleNamespace(
            llm_provider_priority_order=["openrouter", "siliconflow", "groq"],
            openrouter_base_url="https://api.openrouter.ai/v1",
            openrouter_model="openrouter-model",
            openrouter_api_key="openrouter-key",
            groq_base_url="https://api.groq.com/openai/v1",
            groq_model="groq-model",
            groq_api_key="groq-key",
            siliconflow_base_url="https://api.siliconflow.cn/v1",
            siliconflow_model="siliconflow-model",
            siliconflow_api_key="siliconflow-key",
        )

        candidates = llm_router.select_probe_provider_candidates(
            session=session,
            settings=settings,
            requested_provider="openrouter",
            max_calls_per_day=10,
        )

        assert candidates == ("siliconflow", "groq")
    finally:
        session.close()


def test_select_probe_provider_candidates_skips_quota_exhausted_provider() -> None:
    session = _new_session()
    try:
        _, _ = consume_quota(session=session, provider="openrouter", max_calls_per_day=1)
        _, _ = consume_quota(session=session, provider="openrouter", max_calls_per_day=1)

        settings = SimpleNamespace(
            llm_provider_priority_order=["openrouter", "groq", "siliconflow"],
            openrouter_base_url="https://api.openrouter.ai/v1",
            openrouter_model="openrouter-model",
            openrouter_api_key="openrouter-key",
            groq_base_url="https://api.groq.com/openai/v1",
            groq_model="groq-model",
            groq_api_key="groq-key",
            siliconflow_base_url="https://api.siliconflow.cn/v1",
            siliconflow_model="siliconflow-model",
            siliconflow_api_key="siliconflow-key",
        )

        candidates = llm_router.select_probe_provider_candidates(
            session=session,
            settings=settings,
            requested_provider="openrouter",
            max_calls_per_day=1,
        )

        assert candidates == ("groq", "siliconflow")
    finally:
        session.close()


def test_select_probe_provider_candidates_uses_next_provider_when_requested_api_keys_are_quota_reached() -> None:
    session = _new_session()
    try:
        consume_api_key_quota(session=session, provider="openrouter", provider_api_key="or-key-a", max_calls_per_day=1)
        consume_api_key_quota(session=session, provider="openrouter", provider_api_key="or-key-a", max_calls_per_day=1)
        consume_api_key_quota(session=session, provider="openrouter", provider_api_key="or-key-b", max_calls_per_day=1)
        consume_api_key_quota(session=session, provider="openrouter", provider_api_key="or-key-b", max_calls_per_day=1)

        settings = SimpleNamespace(
            llm_provider_priority_order=["openrouter", "groq", "siliconflow"],
            openrouter_base_url="https://api.openrouter.ai/v1",
            openrouter_model="openrouter-model",
            openrouter_api_key="or-key-legacy",
            openrouter_api_keys="or-key-a, or-key-b",
            groq_base_url="https://api.groq.com/openai/v1",
            groq_model="groq-model",
            groq_api_key="groq-key",
            siliconflow_base_url="https://api.siliconflow.cn/v1",
            siliconflow_model="siliconflow-model",
            siliconflow_api_key="siliconflow-key",
        )

        candidates = llm_router.select_probe_provider_candidates(
            session=session,
            settings=settings,
            requested_provider="openrouter",
            max_calls_per_day=1,
        )

        assert candidates == ("groq", "siliconflow")
    finally:
        session.close()


def test_is_provider_requestable_returns_quota_reached_when_all_api_keys_exhausted() -> None:
    session = _new_session()
    try:
        consume_api_key_quota(session=session, provider="openrouter", provider_api_key="or-key-a", max_calls_per_day=1)
        consume_api_key_quota(session=session, provider="openrouter", provider_api_key="or-key-a", max_calls_per_day=1)
        consume_api_key_quota(session=session, provider="openrouter", provider_api_key="or-key-b", max_calls_per_day=1)
        consume_api_key_quota(session=session, provider="openrouter", provider_api_key="or-key-b", max_calls_per_day=1)

        settings = SimpleNamespace(
            openrouter_api_keys="or-key-a, or-key-b",
            openrouter_api_key="or-key-legacy",
            openrouter_base_url="https://api.openrouter.ai/v1",
            openrouter_model="openrouter-model",
            groq_base_url="https://api.groq.com/openai/v1",
            groq_model="groq-model",
            groq_api_key="groq-key",
        )

        requestable, reason = llm_router.is_provider_requestable(
            session=session,
            settings=settings,
            provider_name="openrouter",
            max_calls_per_day=1,
        )

        assert requestable is False
        assert reason == "quota_reached"
    finally:
        session.close()


def test_is_provider_requestable_reports_disabled_provider() -> None:
    session = _new_session()
    try:
        session.query(ProviderToggle).filter(ProviderToggle.provider == "openrouter").delete()
        session.add(ProviderToggle(provider="openrouter", enabled=False))
        settings = SimpleNamespace(openrouter_base_url="https://api.openrouter.ai/v1", openrouter_model="openrouter-model")

        requestable, reason = llm_router.is_provider_requestable(
            session=session,
            settings=settings,
            provider_name="openrouter",
            max_calls_per_day=10,
        )

        assert requestable is False
        assert reason == "provider_disabled"
    finally:
        session.close()


def test_is_provider_requestable_reports_true_when_one_of_multiple_keys_is_available() -> None:
    session = _new_session()
    try:
        consume_api_key_quota(session=session, provider="openrouter", provider_api_key="or-key-a", max_calls_per_day=1)
        consume_api_key_quota(session=session, provider="openrouter", provider_api_key="or-key-a", max_calls_per_day=1)

        settings = SimpleNamespace(
            openrouter_api_keys="or-key-a, or-key-b",
            openrouter_api_key="or-key-b",
            openrouter_base_url="https://api.openrouter.ai/v1",
            openrouter_model="openrouter-model",
        )

        requestable, reason = llm_router.is_provider_requestable(
            session=session,
            settings=settings,
            provider_name="openrouter",
            max_calls_per_day=1,
        )

        assert requestable is True
        assert reason is None
    finally:
        session.close()


def test_get_provider_runtime_settings_uses_openrouter_settings() -> None:
    settings = SimpleNamespace(
        openrouter_base_url="https://openrouter.ai/api/v1",
        openrouter_model="openai/gpt-4o-mini",
        openrouter_api_key="openrouter-key",
    )

    base_url, model_identifier, api_key = llm_router.get_provider_runtime_settings(
        settings=settings,
        provider_name=" openrouter ",
    )

    assert base_url == "https://openrouter.ai/api/v1"
    assert model_identifier == "openai/gpt-4o-mini"
    assert api_key == "openrouter-key"


def test_get_provider_runtime_settings_uses_siliconflow_settings() -> None:
    settings = SimpleNamespace(
        openrouter_base_url="https://openrouter.ai/api/v1",
        openrouter_model="openai/gpt-4o-mini",
        openrouter_api_key="openrouter-key",
        siliconflow_base_url="https://api.siliconflow.cn/v1",
        siliconflow_model="deepseek-ai/DeepSeek-V3",
        siliconflow_api_key="siliconflow-key",
        groq_base_url="https://api.groq.com/openai/v1",
        groq_model="llama-3.3-70b-versatile",
        groq_api_key="groq-key",
    )

    base_url, model_identifier, api_key = llm_router.get_provider_runtime_settings(
        settings=settings,
        provider_name=" siliconflow ",
    )

    assert base_url == "https://api.siliconflow.cn/v1"
    assert model_identifier == "deepseek-ai/DeepSeek-V3"
    assert api_key == "siliconflow-key"


def test_get_provider_runtime_settings_uses_groq_settings() -> None:
    settings = SimpleNamespace(
        openrouter_base_url="https://openrouter.ai/api/v1",
        openrouter_model="openai/gpt-4o-mini",
        openrouter_api_key="openrouter-key",
        groq_base_url="https://api.groq.com/openai/v1",
        groq_model="llama-3.3-70b-versatile",
        groq_api_key="groq-key",
    )

    base_url, model_identifier, api_key = llm_router.get_provider_runtime_settings(
        settings=settings,
        provider_name="groq",
    )

    assert base_url == "https://api.groq.com/openai/v1"
    assert model_identifier == "llama-3.3-70b-versatile"
    assert api_key == "groq-key"


def test_get_provider_priority_order_prefers_configured_provider_order() -> None:
    settings = SimpleNamespace(
        llm_provider_priority_order=["groq", "openrouter", "siliconflow"],
    )

    provider_order = llm_router.get_provider_priority_order(settings=settings)

    assert provider_order == ("groq", "openrouter", "siliconflow")


def test_get_provider_priority_order_is_case_and_whitespace_tolerant() -> None:
    settings = SimpleNamespace(
        llm_provider_priority_order=["  GROQ  ", " openrouter ", "openrouter", "", "siliconflow", "unknown-provider"],
    )

    provider_order = llm_router.get_provider_priority_order(settings=settings)

    assert provider_order == ("groq", "openrouter", "siliconflow")


def test_get_provider_priority_order_uses_comma_separated_config_fallback_and_defaults() -> None:
    settings = SimpleNamespace(
        llm_provider_priority_order="groq, openrouter, siliconflow",
    )

    provider_order = llm_router.get_provider_priority_order(settings=settings)

    assert provider_order == ("groq", "openrouter", "siliconflow")


def test_get_provider_priority_order_falls_back_to_registered_providers_when_unset() -> None:
    settings = SimpleNamespace()

    provider_order = llm_router.get_provider_priority_order(settings=settings)

    assert provider_order == ("groq", "openrouter", "siliconflow")


def test_get_provider_runtime_settings_prefers_multi_key_list() -> None:
    settings = SimpleNamespace(
        openrouter_base_url="https://openrouter.ai/api/v1",
        openrouter_model="openai/gpt-4o-mini",
        openrouter_api_key="fallback-key",
        openrouter_api_keys=["first-openrouter-key", "second-openrouter-key"],
    )

    base_url, model_identifier, api_key = llm_router.get_provider_runtime_settings(
        settings=settings,
        provider_name="openrouter",
    )

    assert base_url == "https://openrouter.ai/api/v1"
    assert model_identifier == "openai/gpt-4o-mini"
    assert api_key == "first-openrouter-key"


def test_get_provider_runtime_settings_uses_comma_separated_key_list() -> None:
    settings = SimpleNamespace(
        openrouter_base_url="https://openrouter.ai/api/v1",
        openrouter_model="openai/gpt-4o-mini",
        openrouter_api_key="fallback-key",
        openrouter_api_keys="first-openrouter-key, second-openrouter-key",
    )

    base_url, model_identifier, api_key = llm_router.get_provider_runtime_settings(
        settings=settings,
        provider_name="openrouter",
    )

    assert base_url == "https://openrouter.ai/api/v1"
    assert model_identifier == "openai/gpt-4o-mini"
    assert api_key == "first-openrouter-key"


def test_get_provider_api_keys_prefers_multikey_list() -> None:
    settings = SimpleNamespace(
        openrouter_base_url="https://openrouter.ai/api/v1",
        openrouter_model="openai/gpt-4o-mini",
        openrouter_api_key="fallback-key",
        openrouter_api_keys=["primary-key", "secondary-key", "tertiary-key"],
    )

    api_keys = llm_router.get_provider_api_keys(
        settings=settings,
        provider_name="openrouter",
    )

    assert api_keys == ["primary-key", "secondary-key", "tertiary-key"]


def test_get_provider_api_keys_uses_comma_string_list() -> None:
    settings = SimpleNamespace(
        openrouter_base_url="https://openrouter.ai/api/v1",
        openrouter_model="openai/gpt-4o-mini",
        openrouter_api_key="fallback-key",
        openrouter_api_keys="a-key, b-key, c-key",
    )

    api_keys = llm_router.get_provider_api_keys(
        settings=settings,
        provider_name="openrouter",
    )

    assert api_keys == ["a-key", "b-key", "c-key"]



def test_llm_router_call_hits_provider_base_url_and_model(monkeypatch: object) -> None:
    observed = {}

    class DummyResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "choices": [{"message": {"content": "{\"sentiment\":\"neutral\",\"confidence\":0.83}"}}],
                "usage": {"total_tokens": 17},
            }

    def fake_post(url: str, *args: object, **kwargs: object) -> DummyResponse:
        observed["url"] = url
        observed["headers"] = kwargs.get("headers")
        observed["payload"] = kwargs.get("json")
        return DummyResponse()

    monkeypatch.setattr(llm_router.requests, "post", fake_post)

    router = llm_router.LLMRouter("https://api.siliconflow.cn/v1")
    response = router.call(
        request=llm_router.LLMRequest(
            request_id="router-base-url-test",
            project_id=1,
            task_type=llm_router.LLMTaskType.SENTIMENT_PROBE.value,
            input_text="The wind turned calm.",
            expected_schema={"sentiment": "string", "confidence": "number"},
            configuration_snapshot_id="router-base-url-test",
        ),
        provider_name="SILICONFLOW",
        model_identifier="deepseek-ai/DeepSeek-V3",
        api_key="siliconflow-key",
    )

    assert response.success_flag is True
    assert response.model_identifier == "deepseek-ai/DeepSeek-V3"
    assert response.provider_used == "siliconflow"
    assert observed["url"] == "https://api.siliconflow.cn/v1/chat/completions"
    assert observed["headers"]["Authorization"] == "Bearer siliconflow-key"
    assert observed["payload"]["max_tokens"] == 60


def test_llm_router_call_honors_request_max_tokens(monkeypatch: object) -> None:
    observed = {}

    class DummyResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "choices": [{"message": {"content": "{\"sentiment\":\"positive\",\"confidence\":0.93}"}}],
                "usage": {"total_tokens": 19},
            }

    def fake_post(_url: str, *args: object, **kwargs: object) -> DummyResponse:
        observed["payload"] = kwargs.get("json")
        return DummyResponse()

    monkeypatch.setattr(llm_router.requests, "post", fake_post)

    router = llm_router.LLMRouter("https://api.siliconflow.cn/v1")
    response = router.call(
        request=llm_router.LLMRequest(
            request_id="router-max-tokens-test",
            project_id=2,
            task_type=llm_router.LLMTaskType.SENTIMENT_PROBE.value,
            input_text="The path split into two.",
            expected_schema={"sentiment": "string", "confidence": "number"},
            configuration_snapshot_id="router-max-tokens-test",
            max_tokens=72,
        ),
        provider_name="SILICONFLOW",
        model_identifier="deepseek-ai/DeepSeek-V3",
        api_key="siliconflow-key",
    )

    assert response.success_flag is True
    assert observed["payload"]["max_tokens"] == 72


def test_llm_router_call_rejects_invalid_request_fields() -> None:
    router = llm_router.LLMRouter("https://api.siliconflow.cn/v1")
    response = router.call(
        request=llm_router.LLMRequest(
            request_id="",
            project_id=1,
            task_type=llm_router.LLMTaskType.SENTIMENT_PROBE.value,
            input_text="Text",
            expected_schema={"sentiment": "string"},
            configuration_snapshot_id="missing-id",
        ),
        provider_name="SILICONFLOW",
        model_identifier="deepseek-ai/DeepSeek-V3",
        api_key="siliconflow-key",
    )

    assert response.success_flag is False
    assert response.error_code == "invalid_request"


def test_llm_router_call_rejects_invalid_request_max_tokens() -> None:
    router = llm_router.LLMRouter("https://api.siliconflow.cn/v1")
    response = router.call(
        request=llm_router.LLMRequest(
            request_id="invalid-max-tokens",
            project_id=1,
            task_type=llm_router.LLMTaskType.SENTIMENT_PROBE.value,
            input_text="Text",
            expected_schema={"sentiment": "string"},
            configuration_snapshot_id="invalid-max-tokens",
            max_tokens=0,
        ),
        provider_name="SILICONFLOW",
        model_identifier="deepseek-ai/DeepSeek-V3",
        api_key="siliconflow-key",
    )

    assert response.success_flag is False
    assert response.error_code == "invalid_request"


def test_llm_router_call_with_failover_rejects_invalid_provider_config() -> None:
    router = llm_router.LLMRouter("https://api.should-not-be-used.example")
    response = router.call_with_failover(
        request=llm_router.LLMRequest(
            request_id="failover-invalid-config",
            project_id=1,
            task_type=llm_router.LLMTaskType.SENTIMENT_PROBE.value,
            input_text="Test",
            expected_schema={"sentiment": "string"},
            configuration_snapshot_id="invalid-provider-config",
        ),
        provider_configs=(
            llm_router.LLMProviderConfig(
                provider_name="",
                base_url="https://api.openrouter.ai/v1",
                model_identifier="openai/gpt-4o-mini",
                api_key="openrouter-key",
            ),
        ),
    )

    assert response.success_flag is False
    assert response.error_code == "invalid_request"
    assert response.model_identifier == "openai/gpt-4o-mini"


def test_llm_standard_response_fields_match_srs_contract() -> None:
    assert llm_router.LLM_STANDARD_RESPONSE_FIELDS == (
        "provider_used",
        "model_identifier",
        "raw_output",
        "parsed_output",
        "confidence",
        "token_usage_estimate",
        "success_flag",
        "error_code",
        "timestamp",
    )


def test_router_success_response_exports_standardized_payload() -> None:
    response = llm_router.LLMResponse(
        provider_used="openrouter",
        model_identifier="openai/gpt-4o-mini",
        raw_output='{ "sentiment": "neutral", "confidence": 0.9 }',
        parsed_output={"sentiment": "neutral", "confidence": 0.9},
        confidence=0.9,
        token_usage_estimate=12,
        success_flag=True,
        error_code=None,
        rate_limit_reset_at=None,
        timestamp="2026-02-26T00:00:00+00:00",
    )

    payload = response.to_standardized_payload()

    assert set(payload.keys()) == set(llm_router.LLM_STANDARD_RESPONSE_FIELDS)
    assert payload["provider_used"] == "openrouter"
    assert payload["success_flag"] is True


def test_parser_error_response_exports_standardized_payload() -> None:
    parser = llm_router.LLMResponseParser()
    response = parser.parse(
        request=llm_router.LLMRequest(
            request_id="parser-contract-error",
            project_id=1,
            task_type=llm_router.LLMTaskType.SENTIMENT_PROBE.value,
            input_text="storm front",
            expected_schema={"sentiment": "string", "confidence": "number"},
            configuration_snapshot_id="parser-contract-error",
        ),
        provider_name="groq",
        model_identifier="llama",
        dispatch_response=llm_router.LLMDispatchResponse(
            status_code=429,
            headers={"retry-after": "120"},
            body={},
        ),
    )

    payload = response.to_standardized_payload()

    assert set(payload.keys()) == set(llm_router.LLM_STANDARD_RESPONSE_FIELDS)
    assert payload["provider_used"] == "groq"
    assert payload["success_flag"] is False
    assert payload["error_code"] == "rate_limit"


def test_llm_router_call_with_failover_uses_next_provider_after_rate_limit(monkeypatch: object) -> None:
    observed: dict[str, int] = {"openrouter": 0, "groq": 0}

    class DummyRateLimitResponse:
        status_code = 429

        @property
        def headers(self) -> dict[str, str]:
            return {"retry-after": "45"}

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {}

    class DummySuccessResponse:
        status_code = 200

        @property
        def headers(self) -> dict[str, str]:
            return {}

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "choices": [{"message": {"content": "{\"sentiment\":\"positive\",\"confidence\":0.9}"}}],
                "usage": {"total_tokens": 11},
            }

    def fake_post(url: str, *args: object, **kwargs: object) -> object:
        if "openrouter" in url:
            observed["openrouter"] += 1
            return DummyRateLimitResponse()
        observed["groq"] += 1
        return DummySuccessResponse()

    monkeypatch.setattr(llm_router.requests, "post", fake_post)

    router = llm_router.LLMRouter("https://api.should-not-be-used.example")
    response = router.call_with_failover(
        request=llm_router.LLMRequest(
            request_id="router-failover-rate-limit",
            project_id=1,
            task_type=llm_router.LLMTaskType.SENTIMENT_PROBE.value,
            input_text="The room dimmed.",
            expected_schema={"sentiment": "string", "confidence": "number"},
            configuration_snapshot_id="router-failover-rate-limit",
        ),
        provider_configs=(
            llm_router.LLMProviderConfig(
                provider_name="openrouter",
                base_url="https://api.openrouter.ai/v1",
                model_identifier="openai/gpt-4o-mini",
                api_key="openrouter-key",
            ),
            llm_router.LLMProviderConfig(
                provider_name="groq",
                base_url="https://api.groq.com/openai/v1",
                model_identifier="llama-3.3-70b-versatile",
                api_key="groq-key",
            ),
        ),
    )

    assert response.success_flag is True
    assert response.provider_used == "groq"
    assert response.raw_output == '{"sentiment":"positive","confidence":0.9}'
    assert observed["openrouter"] == 1
    assert observed["groq"] == 1


def test_llm_router_call_with_failover_retries_in_failed_provider_then_handoffs(monkeypatch: object) -> None:
    observed: dict[str, int] = {"openrouter": 0, "groq": 0}

    class DummyServiceUnavailableResponse:
        status_code = 503

        @property
        def headers(self) -> dict[str, str]:
            return {}

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {}

    class DummySuccessResponse:
        status_code = 200

        @property
        def headers(self) -> dict[str, str]:
            return {}

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "choices": [{"message": {"content": "{\"sentiment\":\"neutral\",\"confidence\":0.76}"}}],
                "usage": {"total_tokens": 13},
            }

    def fake_post(url: str, *args: object, **kwargs: object) -> object:
        if "openrouter" in url:
            observed["openrouter"] += 1
            return DummyServiceUnavailableResponse()
        observed["groq"] += 1
        return DummySuccessResponse()

    monkeypatch.setattr(llm_router.requests, "post", fake_post)

    router = llm_router.LLMRouter("https://api.should-not-be-used.example")
    response = router.call_with_failover(
        request=llm_router.LLMRequest(
            request_id="router-failover-retry-then-failover",
            project_id=1,
            task_type=llm_router.LLMTaskType.SENTIMENT_PROBE.value,
            input_text="A candle flickers.",
            expected_schema={"sentiment": "string", "confidence": "number"},
            configuration_snapshot_id="router-failover-retry-then-failover",
        ),
        provider_configs=(
            llm_router.LLMProviderConfig(
                provider_name="openrouter",
                base_url="https://api.openrouter.ai/v1",
                model_identifier="openai/gpt-4o-mini",
                api_key="openrouter-key",
            ),
            llm_router.LLMProviderConfig(
                provider_name="groq",
                base_url="https://api.groq.com/openai/v1",
                model_identifier="llama-3.3-70b-versatile",
                api_key="groq-key",
            ),
        ),
    )

    assert response.success_flag is True
    assert response.provider_used == "groq"
    assert response.raw_output == '{"sentiment":"neutral","confidence":0.76}'
    assert observed["openrouter"] == 2
    assert observed["groq"] == 1


def test_llm_router_call_with_failover_no_fallback_without_candidates() -> None:
    router = llm_router.LLMRouter("https://api.example.com")
    response = router.call_with_failover(
        request=llm_router.LLMRequest(
            request_id="router-failover-empty-candidates",
            project_id=1,
            task_type=llm_router.LLMTaskType.SENTIMENT_PROBE.value,
            input_text="The tide moved.",
            expected_schema={"sentiment": "string", "confidence": "number"},
            configuration_snapshot_id="router-failover-empty-candidates",
        ),
        provider_configs=(),
    )

    assert response.success_flag is False
    assert response.error_code == "unsupported_provider"
    assert response.provider_used == ""


def test_llm_router_call_retries_on_timeout_errors(monkeypatch: object) -> None:
    observed = {"attempts": 0}

    class DummyTimeoutResponse:
        status_code = 200

        @property
        def headers(self) -> dict[str, str]:
            return {}

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "choices": [{"message": {"content": "{\"sentiment\":\"neutral\",\"confidence\":0.9}"}}],
                "usage": {"total_tokens": 7},
            }

    def fake_post(_url: str, *args: object, **kwargs: object) -> object:
        observed["attempts"] += 1
        if observed["attempts"] == 1:
            raise llm_router.requests.Timeout()
        return DummyTimeoutResponse()

    monkeypatch.setattr(llm_router.requests, "post", fake_post)

    router = llm_router.LLMRouter("https://api.siliconflow.cn/v1")
    response = router.call(
        request=llm_router.LLMRequest(
            request_id="router-timeout-retry",
            project_id=1,
            task_type=llm_router.LLMTaskType.SENTIMENT_PROBE.value,
            input_text="The wind turned calm.",
            expected_schema={"sentiment": "string", "confidence": "number"},
            configuration_snapshot_id="router-timeout-retry",
        ),
        provider_name="SILICONFLOW",
        model_identifier="deepseek-ai/DeepSeek-V3",
        api_key="siliconflow-key",
    )

    assert response.success_flag is True
    assert response.raw_output == '{"sentiment":"neutral","confidence":0.9}'
    assert observed["attempts"] == 2


def test_llm_router_call_retries_on_service_unavailable(monkeypatch: object) -> None:
    observed = {"attempts": 0}

    class DummyServiceUnavailableResponse:
        status_code = 503

        @property
        def headers(self) -> dict[str, str]:
            return {}

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {}

    class DummySuccessResponse:
        status_code = 200

        @property
        def headers(self) -> dict[str, str]:
            return {}

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "choices": [{"message": {"content": "{\"sentiment\":\"positive\",\"confidence\":0.9}"}}],
                "usage": {"total_tokens": 8},
            }

    def fake_post(_url: str, *args: object, **kwargs: object) -> object:
        observed["attempts"] += 1
        if observed["attempts"] == 1:
            return DummyServiceUnavailableResponse()
        return DummySuccessResponse()

    monkeypatch.setattr(llm_router.requests, "post", fake_post)

    router = llm_router.LLMRouter("https://api.groq.com/openai/v1")
    response = router.call(
        request=llm_router.LLMRequest(
            request_id="router-service-unavailable-retry",
            project_id=1,
            task_type=llm_router.LLMTaskType.SENTIMENT_PROBE.value,
            input_text="A scene changes.",
            expected_schema={"sentiment": "string", "confidence": "number"},
            configuration_snapshot_id="router-service-unavailable-retry",
        ),
        provider_name="GROQ",
        model_identifier="llama-3.3-70b-versatile",
        api_key="groq-key",
    )

    assert response.success_flag is True
    assert response.raw_output == '{"sentiment":"positive","confidence":0.9}'
    assert observed["attempts"] == 2


def test_llm_router_call_emits_usage_metric_hooks(monkeypatch: object) -> None:
    observed: list[llm_router.LLMRouterUsageMetric] = []

    class DummyTimeoutResponse:
        status_code = 503

        @property
        def headers(self) -> dict[str, str]:
            return {}

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {}

    class DummySuccessResponse:
        status_code = 200

        @property
        def headers(self) -> dict[str, str]:
            return {}

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "choices": [{"message": {"content": "{\"sentiment\":\"positive\",\"confidence\":0.9}"}}],
                "usage": {"total_tokens": 9},
            }

    attempts = {"count": 0}

    def fake_post(_url: str, *args: object, **kwargs: object) -> object:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return DummyTimeoutResponse()
        return DummySuccessResponse()

    def track_metric(metric: llm_router.LLMRouterUsageMetric) -> None:
        observed.append(metric)

    monkeypatch.setattr(llm_router.requests, "post", fake_post)

    router = llm_router.LLMRouter(
        "https://api.siliconflow.cn/v1",
        usage_metric_hooks=(track_metric,),
    )
    response = router.call(
        request=llm_router.LLMRequest(
            request_id="router-metrics-hook",
            project_id=3,
            task_type=llm_router.LLMTaskType.SENTIMENT_PROBE.value,
            input_text="The candle flickers.",
            expected_schema={"sentiment": "string", "confidence": "number"},
            configuration_snapshot_id="router-metrics-hook",
        ),
        provider_name="SILICONFLOW",
        model_identifier="deepseek-ai/DeepSeek-V3",
        api_key="siliconflow-key",
    )

    assert response.success_flag is True
    assert len(observed) == 2
    assert observed[0].provider == "siliconflow"
    assert observed[0].success is False
    assert observed[0].error_code == "service_unavailable"
    assert observed[1].provider == "siliconflow"
    assert observed[1].success is True
    assert observed[1].attempt_index == 2
    assert observed[1].token_usage_estimate == 9


def test_llm_router_call_with_failover_emits_usage_metric_hooks(monkeypatch: object) -> None:
    observed: list[llm_router.LLMRouterUsageMetric] = []

    class DummyServiceUnavailableResponse:
        status_code = 503

        @property
        def headers(self) -> dict[str, str]:
            return {}

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {}

    class DummySuccessResponse:
        status_code = 200

        @property
        def headers(self) -> dict[str, str]:
            return {}

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "choices": [{"message": {"content": "{\"sentiment\":\"neutral\",\"confidence\":0.76}"}}],
                "usage": {"total_tokens": 15},
            }

    attempts = {"openrouter": 0, "groq": 0}

    def fake_post(url: str, *args: object, **kwargs: object) -> object:
        if "openrouter" in url:
            attempts["openrouter"] += 1
            return DummyServiceUnavailableResponse()

        attempts["groq"] += 1
        return DummySuccessResponse()

    def track_metric(metric: llm_router.LLMRouterUsageMetric) -> None:
        observed.append(metric)

    monkeypatch.setattr(llm_router.requests, "post", fake_post)

    router = llm_router.LLMRouter(
        "https://api.should-not-be-used.example",
        usage_metric_hooks=(track_metric,),
    )
    response = router.call_with_failover(
        request=llm_router.LLMRequest(
            request_id="router-failover-metrics-hook",
            project_id=4,
            task_type=llm_router.LLMTaskType.SENTIMENT_PROBE.value,
            input_text="She turned down the music.",
            expected_schema={"sentiment": "string", "confidence": "number"},
            configuration_snapshot_id="router-failover-metrics-hook",
        ),
        provider_configs=(
            llm_router.LLMProviderConfig(
                provider_name="openrouter",
                base_url="https://api.openrouter.ai/v1/",
                model_identifier="openai/gpt-4o-mini",
                api_key="openrouter-key",
            ),
            llm_router.LLMProviderConfig(
                provider_name="groq",
                base_url="https://api.groq.com/openai/v1",
                model_identifier="llama-3.3-70b-versatile",
                api_key="groq-key",
            ),
        ),
    )

    assert response.success_flag is True
    assert response.provider_used == "groq"
    assert len(observed) == 3
    assert [metric.provider for metric in observed] == ["openrouter", "openrouter", "groq"]
    assert [metric.attempt_index for metric in observed] == [1, 2, 1]
    assert [metric.success for metric in observed] == [False, False, True]
    assert [metric.error_code for metric in observed] == ["service_unavailable", "service_unavailable", None]
    assert observed[0].provider_base_url == "https://api.openrouter.ai/v1"
    assert observed[2].provider_base_url == "https://api.groq.com/openai/v1"
    assert observed[2].token_usage_estimate == 15
    assert attempts["openrouter"] == 2
    assert attempts["groq"] == 1


def test_llm_router_call_does_not_retry_on_rate_limit(monkeypatch: object) -> None:
    observed = {"attempts": 0}

    class DummyRateLimitResponse:
        status_code = 429

        @property
        def headers(self) -> dict[str, str]:
            return {"retry-after": "60"}

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {}

    def fake_post(_url: str, *args: object, **kwargs: object) -> object:
        observed["attempts"] += 1
        return DummyRateLimitResponse()

    monkeypatch.setattr(llm_router.requests, "post", fake_post)

    router = llm_router.LLMRouter("https://api.openrouter.ai/v1")
    response = router.call(
        request=llm_router.LLMRequest(
            request_id="router-rate-limit-no-retry",
            project_id=1,
            task_type=llm_router.LLMTaskType.SENTIMENT_PROBE.value,
            input_text="The storm was loud.",
            expected_schema={"sentiment": "string", "confidence": "number"},
            configuration_snapshot_id="router-rate-limit-no-retry",
        ),
        provider_name="OPENROUTER",
        model_identifier="openai/gpt-4o-mini",
        api_key="openrouter-key",
    )

    assert response.success_flag is False
    assert response.error_code == "rate_limit"
    assert observed["attempts"] == 1


def test_llm_router_call_does_not_retry_on_quota(monkeypatch: object) -> None:
    observed = {"attempts": 0}

    class DummyQuotaResponse:
        status_code = 402

        @property
        def headers(self) -> dict[str, str]:
            return {"x-provider": "groq"}

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"error": {"message": "quota limit reached"}}

    def fake_post(_url: str, *args: object, **kwargs: object) -> object:
        observed["attempts"] += 1
        return DummyQuotaResponse()

    monkeypatch.setattr(llm_router.requests, "post", fake_post)

    router = llm_router.LLMRouter("https://api.groq.com/openai/v1")
    response = router.call(
        request=llm_router.LLMRequest(
            request_id="router-quota-no-retry",
            project_id=1,
            task_type=llm_router.LLMTaskType.SENTIMENT_PROBE.value,
            input_text="The tower fell.",
            expected_schema={"sentiment": "string", "confidence": "number"},
            configuration_snapshot_id="router-quota-no-retry",
        ),
        provider_name="GROQ",
        model_identifier="llama-3.3-70b-versatile",
        api_key="groq-key",
    )

    assert response.success_flag is False
    assert response.error_code == "quota"
    assert observed["attempts"] == 1


def test_llm_router_extracts_rate_limit_reset_timestamp_from_headers(monkeypatch: object) -> None:
    response = llm_router.LLMRouter("https://api.example.com")

    class DummyResponse:
        status_code = 429

        @property
        def headers(self) -> dict[str, str]:
            return {"retry-after": "60", "x-ratelimit-reset": "1735689600"}

        def raise_for_status(self) -> None:
            raise RuntimeError("should not reach")

        def json(self) -> dict:
            return {}

    def fake_post(_url: str, *args: object, **kwargs: object) -> DummyResponse:
        return DummyResponse()

    monkeypatch.setattr(llm_router.requests, "post", fake_post)
    call = response.call(
        request=llm_router.LLMRequest(
            request_id="rate-limit-reset-test",
            project_id=1,
            task_type=llm_router.LLMTaskType.SENTIMENT_PROBE.value,
            input_text="The wind shifted.",
            expected_schema={"sentiment": "string", "confidence": "number"},
            configuration_snapshot_id="rate-limit-reset-test",
        ),
        provider_name="openrouter",
        model_identifier="openai/gpt-4o-mini",
        api_key="api-key",
    )

    assert call.success_flag is False
    assert call.error_code == "rate_limit"
    assert call.rate_limit_reset_at is not None
    assert call.rate_limit_reset_at.timestamp() == 1735689600


def test_default_llm_dispatcher_delegates_to_requests(monkeypatch: object) -> None:
    observed = {}

    class DummyResponse:
        status_code = 200

        @property
        def headers(self) -> dict[str, str]:
            return {"x-test": "header"}

        def json(self) -> dict:
            return {"choices": [], "usage": {"total_tokens": 11}}

    def fake_post(url: str, *args: object, **kwargs: object) -> DummyResponse:
        observed["url"] = url
        observed["headers"] = kwargs.get("headers", {})
        observed["payload"] = kwargs.get("json", {})
        return DummyResponse()

    monkeypatch.setattr(llm_router.requests, "post", fake_post)

    result = llm_router.LLMDispatcher().dispatch(
        request=llm_router.LLMDispatchRequest(
            endpoint="https://api.example.com/chat/completions",
            payload={"model": "test-model", "messages": []},
            headers={"Authorization": "Bearer test"},
        )
    )

    assert observed["url"] == "https://api.example.com/chat/completions"
    assert observed["headers"]["Authorization"] == "Bearer test"
    assert result.status_code == 200
    assert result.headers == {"x-test": "header"}
    assert result.body == {"choices": [], "usage": {"total_tokens": 11}}


def test_response_parser_extracts_raw_payload_on_success() -> None:
    parser = llm_router.LLMResponseParser()
    response = parser.parse(
        request=llm_router.LLMRequest(
            request_id="parser-success",
            project_id=1,
            task_type=llm_router.LLMTaskType.SENTIMENT_PROBE.value,
            input_text="calm dawn and bright sky",
            expected_schema={"sentiment": "string", "confidence": "number"},
            configuration_snapshot_id="parser-success",
        ),
        provider_name="openrouter",
        model_identifier="openai/gpt-4o-mini",
        dispatch_response=llm_router.LLMDispatchResponse(
            status_code=200,
            headers={"x-test": "ok"},
            body={
                "choices": [{"message": {"content": "{\"sentiment\": \"neutral\", \"confidence\": 0.95}"}}],
                "usage": {"total_tokens": 44},
            },
        ),
    )

    assert response.success_flag is True
    assert response.raw_output == '{"sentiment": "neutral", "confidence": 0.95}'
    assert response.parsed_output == {"sentiment": "neutral", "confidence": 0.95}
    assert response.token_usage_estimate == 44


def test_response_parser_marks_rate_limit_from_dispatch() -> None:
    parser = llm_router.LLMResponseParser()
    response = parser.parse(
        request=llm_router.LLMRequest(
            request_id="parser-rate-limit",
            project_id=1,
            task_type=llm_router.LLMTaskType.SENTIMENT_PROBE.value,
            input_text="storm front",
            expected_schema={"sentiment": "string", "confidence": "number"},
            configuration_snapshot_id="parser-rate-limit",
        ),
        provider_name="groq",
        model_identifier="llama",
        dispatch_response=llm_router.LLMDispatchResponse(
            status_code=429,
            headers={"retry-after": "120"},
            body={},
        ),
    )

    assert response.success_flag is False
    assert response.error_code == "rate_limit"
    assert response.rate_limit_reset_at is not None
    assert int(response.rate_limit_reset_at.timestamp()) > 0


def test_response_parser_classifies_provider_rate_limit_from_status_code() -> None:
    parser = llm_router.LLMResponseParser()
    response = parser.parse(
        request=llm_router.LLMRequest(
            request_id="parser-rate-limit-code",
            project_id=1,
            task_type=llm_router.LLMTaskType.SENTIMENT_PROBE.value,
            input_text="test input",
            expected_schema={"sentiment": "string", "confidence": "number"},
            configuration_snapshot_id="parser-rate-limit-code",
        ),
        provider_name="openrouter",
        model_identifier="openai/gpt-4o-mini",
        dispatch_response=llm_router.LLMDispatchResponse(
            status_code=429,
            headers={"retry-after": "1"},
            body={},
        ),
    )

    assert response.error_code == "rate_limit"


def test_response_parser_classifies_provider_quota_from_http_and_body() -> None:
    parser = llm_router.LLMResponseParser()
    response = parser.parse(
        request=llm_router.LLMRequest(
            request_id="parser-quota",
            project_id=1,
            task_type=llm_router.LLMTaskType.SENTIMENT_PROBE.value,
            input_text="test input",
            expected_schema={"sentiment": "string", "confidence": "number"},
            configuration_snapshot_id="parser-quota",
        ),
        provider_name="groq",
        model_identifier="llama",
        dispatch_response=llm_router.LLMDispatchResponse(
            status_code=403,
            headers={},
            body={"error": {"message": "quota has been exceeded for this month"}},
        ),
    )

    assert response.error_code == "quota"


def test_response_parser_classifies_timeout_from_status_or_transport_error() -> None:
    parser = llm_router.LLMResponseParser()
    transport_timeout_response = parser.parse(
        request=llm_router.LLMRequest(
            request_id="parser-timeout-transport",
            project_id=1,
            task_type=llm_router.LLMTaskType.SENTIMENT_PROBE.value,
            input_text="test input",
            expected_schema={"sentiment": "string", "confidence": "number"},
            configuration_snapshot_id="parser-timeout-transport",
        ),
        provider_name="groq",
        model_identifier="llama",
        dispatch_response=llm_router.LLMDispatchResponse(
            status_code=None,
            headers={},
            body=None,
            transport_error="timeout",
        ),
    )

    http_timeout_response = parser.parse(
        request=llm_router.LLMRequest(
            request_id="parser-timeout-http",
            project_id=1,
            task_type=llm_router.LLMTaskType.SENTIMENT_PROBE.value,
            input_text="test input",
            expected_schema={"sentiment": "string", "confidence": "number"},
            configuration_snapshot_id="parser-timeout-http",
        ),
        provider_name="groq",
        model_identifier="llama",
        dispatch_response=llm_router.LLMDispatchResponse(
            status_code=408,
            headers={},
            body={},
        ),
    )

    assert transport_timeout_response.error_code == "timeout"
    assert http_timeout_response.error_code == "timeout"


def test_response_parser_classifies_service_unavailable() -> None:
    parser = llm_router.LLMResponseParser()
    response = parser.parse(
        request=llm_router.LLMRequest(
            request_id="parser-service-unavailable",
            project_id=1,
            task_type=llm_router.LLMTaskType.SENTIMENT_PROBE.value,
            input_text="test input",
            expected_schema={"sentiment": "string", "confidence": "number"},
            configuration_snapshot_id="parser-service-unavailable",
        ),
        provider_name="openrouter",
        model_identifier="openai/gpt-4o-mini",
        dispatch_response=llm_router.LLMDispatchResponse(
            status_code=503,
            headers={},
            body={},
        ),
    )

    assert response.error_code == "service_unavailable"


def test_response_parser_classifies_other_errors() -> None:
    parser = llm_router.LLMResponseParser()
    response = parser.parse(
        request=llm_router.LLMRequest(
            request_id="parser-other",
            project_id=1,
            task_type=llm_router.LLMTaskType.SENTIMENT_PROBE.value,
            input_text="test input",
            expected_schema={"sentiment": "string", "confidence": "number"},
            configuration_snapshot_id="parser-other",
        ),
        provider_name="siliconflow",
        model_identifier="deepseek-ai/DeepSeek-V3",
        dispatch_response=llm_router.LLMDispatchResponse(
            status_code=418,
            headers={},
            body={},
        ),
    )

    assert response.error_code == "other"


def test_response_parser_flags_invalid_json_response_as_invalid_response() -> None:
    parser = llm_router.LLMResponseParser()
    response = parser.parse(
        request=llm_router.LLMRequest(
            request_id="parser-invalid-json",
            project_id=1,
            task_type=llm_router.LLMTaskType.SENTIMENT_PROBE.value,
            input_text="test input",
            expected_schema={"sentiment": "string", "confidence": "number"},
            configuration_snapshot_id="parser-invalid-json",
        ),
        provider_name="openrouter",
        model_identifier="openai/gpt-4o-mini",
        dispatch_response=llm_router.LLMDispatchResponse(
            status_code=200,
            headers={"x-test": "ok"},
            body={
                "choices": [{"message": {"content": "{\"sentiment\": \"neutral\", \"confidence\": 0.95"}}],
                "usage": {"total_tokens": 44},
            },
        ),
    )

    assert response.success_flag is False
    assert response.error_code == "invalid_response"
    assert response.parsed_output == {}
    assert response.raw_output == '{"sentiment": "neutral", "confidence": 0.95'


def test_response_parser_flags_missing_schema_key_as_invalid_response() -> None:
    parser = llm_router.LLMResponseParser()
    response = parser.parse(
        request=llm_router.LLMRequest(
            request_id="parser-missing-key",
            project_id=1,
            task_type=llm_router.LLMTaskType.SENTIMENT_PROBE.value,
            input_text="test input",
            expected_schema={"sentiment": "string", "confidence": "number"},
            configuration_snapshot_id="parser-missing-key",
        ),
        provider_name="openrouter",
        model_identifier="openai/gpt-4o-mini",
        dispatch_response=llm_router.LLMDispatchResponse(
            status_code=200,
            headers={"x-test": "ok"},
            body={
                "choices": [{"message": {"content": '{"sentiment": "neutral"}'}}],
                "usage": {"total_tokens": 32},
            },
        ),
    )

    assert response.success_flag is False
    assert response.error_code == "invalid_response"
    assert response.raw_output == '{"sentiment": "neutral"}'


def test_response_parser_flags_schema_type_mismatch_as_invalid_response() -> None:
    parser = llm_router.LLMResponseParser()
    response = parser.parse(
        request=llm_router.LLMRequest(
            request_id="parser-type-mismatch",
            project_id=1,
            task_type=llm_router.LLMTaskType.SENTIMENT_PROBE.value,
            input_text="test input",
            expected_schema={"sentiment": "string", "confidence": "number"},
            configuration_snapshot_id="parser-type-mismatch",
        ),
        provider_name="openrouter",
        model_identifier="openai/gpt-4o-mini",
        dispatch_response=llm_router.LLMDispatchResponse(
            status_code=200,
            headers={"x-test": "ok"},
            body={
                "choices": [{"message": {"content": '{"sentiment": "neutral", "confidence": "not-a-number"}'}}],
                "usage": {"total_tokens": 33},
            },
        ),
    )

    assert response.success_flag is False
    assert response.error_code == "invalid_response"
    assert response.raw_output == '{"sentiment": "neutral", "confidence": "not-a-number"}'


def test_response_parser_classifies_invalid_request_from_provider_body() -> None:
    parser = llm_router.LLMResponseParser()
    response = parser.parse(
        request=llm_router.LLMRequest(
            request_id="parser-invalid-request",
            project_id=1,
            task_type=llm_router.LLMTaskType.SENTIMENT_PROBE.value,
            input_text="test input",
            expected_schema={"sentiment": "string", "confidence": "number"},
            configuration_snapshot_id="parser-invalid-request",
        ),
        provider_name="groq",
        model_identifier="llama",
        dispatch_response=llm_router.LLMDispatchResponse(
            status_code=400,
            headers={},
            body={"error": {"message": "Invalid request body: missing required field", "type": "invalid_request_error"}},
        ),
    )

    assert response.success_flag is False
    assert response.error_code == "invalid_request"


def test_dispatcher_maps_timeout_to_transport_error(monkeypatch: object) -> None:
    class DummyTimeoutResponse:
        def raise_for_status(self) -> None:
            return None

    def fake_post(*_args: object, **_kwargs: object) -> object:
        raise llm_router.requests.Timeout()

    monkeypatch.setattr(llm_router.requests, "post", fake_post)

    dispatch_response = llm_router.LLMDispatcher().dispatch(
        request=llm_router.LLMDispatchRequest(
            endpoint="https://api.example.com/chat/completions",
            payload={},
            headers={},
        )
    )

    assert dispatch_response.status_code is None
    assert dispatch_response.transport_error == "timeout"
