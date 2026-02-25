import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_mode_profile_snapshot.db"

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.main import app
from app.modes import MODE_DEFAULT_PROFILES
from app.services.mode_profiles import build_run_config_snapshot


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_mode_profile_snapshot.db")
    if db_file.exists():
        db_file.unlink()


def _sample_txt() -> str:
    return (
        "Chapter 1\n"
        '"Sunny looked around," Sunny said. The cold wind cut through the street.\n\n'
        "Chapter 2\n"
        "Nephis smiled. Hope rose."
    )


def _create_project_with_ingested_text(client: TestClient, title: str) -> int:
    project_resp = client.post("/api/projects", json={"title": title})
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    ingest_resp = client.post(
        f"/api/projects/{project_id}/ingest/txt",
        files={"file": ("sample.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
    )
    assert ingest_resp.status_code == 200
    return project_id


def test_unit_build_run_config_snapshot_keeps_profile_snapshot_and_applies_overrides() -> None:
    snapshot = build_run_config_snapshot(
        mode="author",
        overrides={
            "max_segment_chars": 144,
            "provider_name": "groq",
        },
    )
    assert snapshot["mode"] == "author"
    assert snapshot["max_segment_chars"] == 144
    assert snapshot["provider_name"] == "groq"
    assert snapshot["mode_profile_snapshot"] == MODE_DEFAULT_PROFILES["author"]
    assert snapshot["mode_profile_snapshot"]["provider_name"] == "openrouter"


def test_integration_run_config_stores_loaded_mode_profile_snapshot() -> None:
    with TestClient(app) as client:
        project_id = _create_project_with_ingested_text(client, "Mode Snapshot Integration")

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"mode": "academic"},
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        detail_resp = client.get(f"/api/projects/{project_id}/runs/{run_id}")
        assert detail_resp.status_code == 200
        config = detail_resp.json()["config"]
        assert config["mode"] == "academic"
        assert config["max_segment_chars"] == MODE_DEFAULT_PROFILES["academic"]["max_segment_chars"]
        assert config["mode_profile_snapshot"] == MODE_DEFAULT_PROFILES["academic"]


def test_e2e_run_config_uses_overrides_without_mutating_profile_snapshot() -> None:
    with TestClient(app) as client:
        project_id = _create_project_with_ingested_text(client, "Mode Snapshot E2E")

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={
                "mode": "audiobook",
                "max_segment_chars": 99,
                "llm_enabled": True,
                "provider_name": "siliconflow",
                "max_calls_per_day": 3,
            },
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        detail_resp = client.get(f"/api/projects/{project_id}/runs/{run_id}")
        assert detail_resp.status_code == 200
        config = detail_resp.json()["config"]
        assert config["max_segment_chars"] == 99
        assert config["llm_enabled"] is True
        assert config["provider_name"] == "siliconflow"
        assert config["max_calls_per_day"] == 3
        assert config["mode_profile_snapshot"] == MODE_DEFAULT_PROFILES["audiobook"]
        assert config["mode_profile_snapshot"]["provider_name"] == "openrouter"


def test_regression_custom_mode_snapshot_payload_shape() -> None:
    assert build_run_config_snapshot("custom") == {
        "mode": "custom",
        "max_segment_chars": 255,
        "llm_enabled": False,
        "provider_name": "openrouter",
        "max_calls_per_day": 25,
        "mode_profile_snapshot": {
            "max_segment_chars": 255,
            "llm_enabled": False,
            "provider_name": "openrouter",
            "max_calls_per_day": 25,
            "profile_intent": "user-tuned baseline with conservative defaults",
        },
    }
