import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_acceptance_reproducible_outputs.db"

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.main import app


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_acceptance_reproducible_outputs.db")
    if db_file.exists():
        db_file.unlink()


def test_acceptance_identical_input_and_config_yield_reproducible_outputs() -> None:
    run_payload = {
        "mode": "author",
        "max_segment_chars": 120,
        "llm_enabled": False,
        "provider_name": "openrouter",
        "max_calls_per_day": 5,
        "allow_unfinalized_character_map": True,
        "deterministic_mode": True,
        "deterministic_seed": 20260226,
        "randomization_config": {"strategy": "stable", "shuffle_enabled": False},
    }

    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "ACC-008 Reproducible Outputs"})
        assert project_resp.status_code == 201
        project_id = int(project_resp.json()["id"])

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": (
                    "reproducible-source.txt",
                    io.BytesIO(
                        (
                            "Chapter 1\n"
                            "Stormlight traced the ruined arch while the sentries waited.\n\n"
                            "Chapter 2\n"
                            "By dawn, the harbor lanterns dimmed and the bells fell silent."
                        ).encode("utf-8")
                    ),
                    "text/plain",
                )
            },
        )
        assert ingest_resp.status_code == 200

        first_run_resp = client.post(f"/api/projects/{project_id}/runs", json=run_payload)
        assert first_run_resp.status_code == 200
        first_run_id = int(first_run_resp.json()["run_id"])

        second_run_resp = client.post(f"/api/projects/{project_id}/runs", json=run_payload)
        assert second_run_resp.status_code == 200
        second_run_id = int(second_run_resp.json()["run_id"])
        assert second_run_id != first_run_id

        first_export_resp = client.get(f"/api/projects/{project_id}/exports/{first_run_id}.json")
        assert first_export_resp.status_code == 200
        first_export_payload = first_export_resp.json()
        assert first_export_payload["status"] == "completed"

        second_export_resp = client.get(f"/api/projects/{project_id}/exports/{second_run_id}.json")
        assert second_export_resp.status_code == 200
        second_export_payload = second_export_resp.json()
        assert second_export_payload["status"] == "completed"

        assert first_export_payload["segments"] == second_export_payload["segments"]

