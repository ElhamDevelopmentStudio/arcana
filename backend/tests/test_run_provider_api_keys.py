import os
import io
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipc_provider_keys.db"

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.main import app
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

        assert detail["config"]["provider_api_keys"] == {
            "openrouter": ["run-key-a", "run-key-b"],
            "groq": ["run-groq-key"],
        }
