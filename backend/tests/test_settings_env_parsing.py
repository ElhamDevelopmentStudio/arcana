from app.config import Settings


def test_settings_accepts_comma_separated_provider_priority_order(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER_PRIORITY_ORDER", "openrouter,siliconflow,groq")
    settings = Settings(_env_file=None)
    assert settings.llm_provider_priority_order == ["openrouter", "siliconflow", "groq"]


def test_settings_accepts_comma_separated_provider_api_keys(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEYS", "key-a,key-b")
    settings = Settings(_env_file=None)
    assert settings.openrouter_api_keys == ["key-a", "key-b"]
