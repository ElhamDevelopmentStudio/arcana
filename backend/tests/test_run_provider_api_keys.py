import os
import io
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipc_provider_keys.db"

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.database import get_session_factory
from app.main import app
from app.models import Project
from app.schemas import RunCreateRequest
from app.services import pipeline
from app.services import llm_router


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipc_provider_keys.db")
    if db_file.exists():
        db_file.unlink()


def test_run_create_request_normalizes_provider_api_keys_payload() -> None:
    payload = RunCreateRequest(
        provider_api_keys={
            "OPENROUTER": "key-a, key-b",
            "groq": ["k1", "", None, "k2"],
            "siliconflow": [],
            "": "ignored",
        }
    )

    assert payload.provider_api_keys == {
        "openrouter": ["key-a", "key-b"],
        "groq": ["k1", "k2"],
    }


def test_pipeline_prefers_user_supplied_provider_api_keys_for_run() -> None:
    settings = SimpleNamespace(
        openrouter_base_url="https://api.openrouter.ai/v1",
        openrouter_model="openai/gpt-4o-mini",
        openrouter_api_key="global-openrouter",
        openrouter_api_keys=["global-openrouter"],
        groq_base_url="https://api.groq.com/openai/v1",
        groq_model="llama-3.3-70b-versatile",
        groq_api_key="global-groq",
        groq_api_keys=None,
        siliconflow_base_url="https://api.siliconflow.cn/v1",
        siliconflow_model="deepseek-ai/DeepSeek-V3",
        siliconflow_api_key="global-siliconflow",
        siliconflow_api_keys=["global-siliconflow"],
    )

    run_config = {
        "provider_api_keys": {
            "openrouter": ["run-openrouter-a", "run-openrouter-b"],
            "groq": "run-groq-a, run-groq-b",
        }
    }

    scoped_settings = pipeline._build_run_scoped_llm_settings(
        settings=settings,
        run_config=run_config,
    )

    assert llm_router.get_provider_api_keys(settings=scoped_settings, provider_name="openrouter") == [
        "run-openrouter-a",
        "run-openrouter-b",
    ]
    assert llm_router.get_provider_api_keys(settings=scoped_settings, provider_name="groq") == [
        "run-groq-a",
        "run-groq-b",
    ]
    assert llm_router.get_provider_api_keys(settings=scoped_settings, provider_name="siliconflow") == [
        "global-siliconflow",
    ]
    assert llm_router.get_provider_runtime_settings(
        settings=scoped_settings,
        provider_name="openrouter",
    )[2] == "run-openrouter-a"


def test_pipeline_prefers_project_provider_config_over_global_env() -> None:
    settings = SimpleNamespace(
        openrouter_base_url="https://api.openrouter.ai/v1",
        openrouter_model="openai/gpt-4o-mini",
        openrouter_api_key="global-openrouter",
        openrouter_api_keys=["global-openrouter"],
        groq_base_url="https://api.groq.com/openai/v1",
        groq_model="llama-3.3-70b-versatile",
        groq_api_key="global-groq",
        groq_api_keys=None,
    )

    run_config = {
        "provider_config": {
            "OPENROUTER": {
                "base_url": "https://project.example.com/openrouter",
                "model": "project/openrouter/model",
                "api_key": "project-openrouter-key",
                "api_keys": ["project-or-a", "", None, "project-or-b"],
            },
            "groq": {
                "base_url": "https://project.example.com/groq",
                "model": "project/groq/model",
                "api_key": "project-groq-key",
            },
            "": {"api_key": "ignored"},
        }
    }

    scoped_settings = pipeline._build_run_scoped_llm_settings(
        settings=settings,
        run_config=run_config,
    )

    assert llm_router.get_provider_runtime_settings(
        settings=scoped_settings,
        provider_name="openrouter",
    ) == (
        "https://project.example.com/openrouter",
        "project/openrouter/model",
        "project-or-a",
    )
    assert llm_router.get_provider_api_keys(
        settings=scoped_settings,
        provider_name="openrouter",
    ) == ["project-or-a", "project-or-b"]
    assert llm_router.get_provider_runtime_settings(
        settings=scoped_settings,
        provider_name="groq",
    ) == (
        "https://project.example.com/groq",
        "project/groq/model",
        "project-groq-key",
    )


def test_run_create_endpoints_store_user_supplied_provider_keys_in_config() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Run Provider Key Support"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("run-key-sample.txt", io.BytesIO(b"Chapter 1\\n\\nThis is sample text for provider key testing."), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        run_payload = {
            "max_segment_chars": 120,
            "provider_name": "openrouter",
            "max_calls_per_day": 4,
            "llm_enabled": False,
            "provider_api_keys": {
                "openrouter": "run-key-a, run-key-b",
                "groq": ["run-groq-key"],
                "siliconflow": "",
            },
        }
        run_resp = client.post(f"/api/projects/{project_id}/runs", json=run_payload)
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        detail_resp = client.get(f"/api/projects/{project_id}/runs/{run_id}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()

        assert "provider_api_keys" not in detail["config"]


def test_project_llm_provider_config_is_stored_and_inherited_by_runs() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Project Provider Config Inheritance"})
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    with TestClient(app) as client:
        update_resp = client.put(
            f"/api/projects/{project_id}/llm",
            json={
                "llm_enabled": True,
                "provider_config": {
                    "openrouter": {
                        "base_url": "https://project.example.com/openrouter",
                        "model": "project/openrouter/model",
                        "api_keys": ["project-or-a", "", "project-or-b"],
                    },
                    "groq": {
                        "model": "project/groq/model",
                        "api_key": "project-groq-key",
                    },
                },
            },
        )
    assert update_resp.status_code == 200
    llm_settings = update_resp.json()
    assert llm_settings["provider_config"]["openrouter"]["base_url"] == "https://project.example.com/openrouter"
    assert llm_settings["provider_config"]["openrouter"]["model"] == "project/openrouter/model"
    assert "api_keys" not in llm_settings["provider_config"]["openrouter"]
    assert "api_key" not in llm_settings["provider_config"]["groq"]
    assert llm_settings["provider_config"]["groq"]["model"] == "project/groq/model"
    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        assert project.llm_provider_config_json["openrouter"]["api_keys"] == ["project-or-a", "project-or-b"]
        assert project.llm_provider_config_json["groq"]["api_key"] == "project-groq-key"
    finally:
        session.close()

    with TestClient(app) as client:
        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("provider-config-sample.txt", io.BytesIO(b"Chapter 1\n\nSample text."), "text/plain")},
        )
    assert ingest_resp.status_code == 200

    with TestClient(app) as client:
        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={
                "mode": "author",
                "max_segment_chars": 120,
                "provider_name": "openrouter",
                "max_calls_per_day": 5,
                "llm_enabled": False,
                "allow_unfinalized_character_map": True,
            },
        )
    assert run_resp.status_code == 200
    run_id = run_resp.json()["run_id"]

    with TestClient(app) as client:
        run_detail = client.get(f"/api/projects/{project_id}/runs/{run_id}")
    assert run_detail.status_code == 200
    run_config = run_detail.json()["config"]

    assert run_config["provider_config"]["openrouter"]["base_url"] == "https://project.example.com/openrouter"
    assert run_config["provider_config"]["openrouter"]["model"] == "project/openrouter/model"
    assert "api_keys" not in run_config["provider_config"]["openrouter"]
    assert "api_key" not in run_config["provider_config"]["groq"]
    assert run_config["provider_config"]["groq"]["model"] == "project/groq/model"


def test_export_payload_redacts_api_keys_in_run_config_snapshots() -> None:
    with TestClient(app) as client:
        project_resp = client.post(
            "/api/projects",
            json={"title": "Export API Key Redaction Project"},
        )
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    with TestClient(app) as client:
        update_resp = client.put(
            f"/api/projects/{project_id}/llm",
            json={
                "llm_enabled": True,
                "provider_config": {
                    "openrouter": {
                        "base_url": "https://project.example.com/openrouter",
                        "model": "project/openrouter/model",
                        "api_key": "project-openrouter-key",
                        "api_keys": ["project-or-a", "project-or-b"],
                    },
                    "groq": {
                        "base_url": "https://project.example.com/groq",
                        "model": "project/groq/model",
                        "api_key": "project-groq-key",
                        "api_keys": ["project-groq-a", "project-groq-b"],
                    },
                },
            },
        )
    assert update_resp.status_code == 200

    with TestClient(app) as client:
        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("provider-key-export.txt", io.BytesIO(b"Chapter 1\n\nExport should sanitize provider key data."), "text/plain")},
        )
    assert ingest_resp.status_code == 200

    with TestClient(app) as client:
        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={
                "mode": "author",
                "max_segment_chars": 120,
                "llm_enabled": False,
                "allow_unfinalized_character_map": True,
            },
        )
    assert run_resp.status_code == 200
    run_id = run_resp.json()["run_id"]

    with TestClient(app) as client:
        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
    assert export_resp.status_code == 200

    payload = export_resp.json()

    run_snapshot = payload["manifest"]["run"]["config_snapshot"]
    comparative_snapshot = payload["manifest"]["academic_reports"]["comparative_run_metrics_snapshot"][
        "run_config_snapshot"
    ]

    assert "provider_api_keys" not in run_snapshot
    assert "provider_api_keys" not in comparative_snapshot

    for snapshot in (run_snapshot, comparative_snapshot):
        provider_config = snapshot.get("provider_config")
        assert isinstance(provider_config, dict)
        assert "api_key" not in provider_config
        for provider in provider_config.values():
            if not isinstance(provider, dict):
                continue
            assert "api_key" not in provider
            assert "api_keys" not in provider
