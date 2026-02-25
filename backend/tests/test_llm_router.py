from types import SimpleNamespace

import app.services.llm_router as llm_router


def test_is_supported_provider_includes_siliconflow() -> None:
    assert llm_router.is_supported_provider("siliconflow") is True
    assert llm_router.is_supported_provider("openrouter") is True
    assert llm_router.is_supported_provider("groq") is False


def test_get_provider_runtime_settings_uses_siliconflow_settings() -> None:
    settings = SimpleNamespace(
        openrouter_base_url="https://openrouter.ai/api/v1",
        openrouter_model="openai/gpt-4o-mini",
        openrouter_api_key="openrouter-key",
        siliconflow_base_url="https://api.siliconflow.cn/v1",
        siliconflow_model="deepseek-ai/DeepSeek-V3",
        siliconflow_api_key="siliconflow-key",
    )

    base_url, model_identifier, api_key = llm_router.get_provider_runtime_settings(
        settings=settings,
        provider_name=" siliconflow ",
    )

    assert base_url == "https://api.siliconflow.cn/v1"
    assert model_identifier == "deepseek-ai/DeepSeek-V3"
    assert api_key == "siliconflow-key"


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
