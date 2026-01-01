import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import LLMCall, ProviderToggle, Project, ProviderQuota, Run
from app.services import pipeline


os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_llm_provider_toggles.db"


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_llm_provider_toggles.db")
    if db_file.exists():
        db_file.unlink()


def _new_session():
    return get_session_factory()()


def test_integration_llm_provider_endpoints_list_default_status_for_supported_providers() -> None:
    with TestClient(app) as client:
        response = client.get("/api/llm/providers")
    assert response.status_code == 200

    providers = response.json()["providers"]
    assert isinstance(providers, list)
    assert {entry["provider"] for entry in providers} == {"openrouter", "siliconflow", "groq"}
    assert all(entry["enabled"] is True for entry in providers)


def test_integration_llm_provider_toggle_endpoint_can_disable_then_enable_provider() -> None:
    with TestClient(app) as client:
        disable_resp = client.put("/api/llm/providers/openrouter", json={"enabled": False})
    assert disable_resp.status_code == 200
    assert disable_resp.json() == {"provider": "openrouter", "enabled": False}

    with TestClient(app) as client:
        providers_resp = client.get("/api/llm/providers")
    assert providers_resp.status_code == 200
    providers = {entry["provider"]: entry["enabled"] for entry in providers_resp.json()["providers"]}
    assert providers["openrouter"] is False

    with TestClient(app) as client:
        enable_resp = client.put("/api/llm/providers/openrouter", json={"enabled": True})
    assert enable_resp.status_code == 200
    assert enable_resp.json() == {"provider": "openrouter", "enabled": True}

    with TestClient(app) as client:
        enabled_resp = client.get("/api/llm/providers")
    assert enabled_resp.status_code == 200
    providers = {entry["provider"]: entry["enabled"] for entry in enabled_resp.json()["providers"]}
    assert providers["openrouter"] is True


def test_pipeline_skips_llm_probe_when_provider_is_manually_disabled(monkeypatch: object) -> None:
    session = _new_session()
    try:
        project = Project(title="Provider Disable Probe Project")
        session.add(project)
        session.flush()

        run = Run(
            project_id=project.id,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        session.add(run)
        session.flush()

        session.query(ProviderToggle).filter(ProviderToggle.provider == "openrouter").delete()
        session.add(ProviderToggle(provider="openrouter", enabled=False))
        session.commit()

        call_count = {"value": 0}

        class _UnexpectedLLMRouter:
            def __init__(self, openrouter_base_url: str) -> None:
                self.openrouter_base_url = openrouter_base_url

            def call(self, *args: object, **kwargs: object) -> object:
                call_count["value"] += 1
                raise AssertionError("LLM router should not be called when provider is disabled")

        monkeypatch.setattr(pipeline, "LLMRouter", _UnexpectedLLMRouter)
        monkeypatch.setattr(
            pipeline,
            "get_provider_runtime_settings",
            lambda **kwargs: ("https://api.example.com", "gpt-test", "api-key"),
        )

        pipeline._run_llm_probe(
            session=session,
            project=project,
            run=run,
            run_config={"provider_name": "openrouter", "max_calls_per_day": 10},
            input_text="A disabled provider should not run.",
        )

        assert call_count["value"] == 0

        call = session.query(LLMCall).filter(LLMCall.run_id == run.id).one_or_none()
        assert call is not None
        assert call.provider == "openrouter"
        assert call.success is False
        assert call.detail == "provider_disabled"
        assert call.request_count == 0
        assert session.query(ProviderQuota).filter(ProviderQuota.provider == "openrouter").one_or_none() is None
    finally:
        session.close()
