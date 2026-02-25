from types import SimpleNamespace

import app.services.llm_router as llm_router


def test_is_supported_provider_includes_siliconflow() -> None:
    assert llm_router.is_supported_provider("siliconflow") is True
    assert llm_router.is_supported_provider("openrouter") is True
    assert llm_router.is_supported_provider("groq") is True


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
