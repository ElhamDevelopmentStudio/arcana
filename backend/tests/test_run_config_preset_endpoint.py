import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_run_config_preset_endpoint.db"

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

    db_file = Path("test_nipe_run_config_preset_endpoint.db")
    if db_file.exists():
        db_file.unlink()


def _sample_txt() -> str:
    return (
        "Chapter 1\n"
        '"Aster paused," Aster said. Rain fell in silver lines.\n\n'
        "Chapter 2\n"
        "The city gates opened at dawn."
    )


def _create_project_with_ingested_text(client: TestClient, title: str) -> int:
    project_resp = client.post("/api/projects", json={"title": title})
    assert project_resp.status_code == 201
    project_id = int(project_resp.json()["id"])

    ingest_resp = client.post(
        f"/api/projects/{project_id}/ingest/txt",
        files={"file": ("sample.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
    )
    assert ingest_resp.status_code == 200
    return project_id


def test_integration_run_config_preset_endpoint_exports_reusable_payload() -> None:
    with TestClient(app) as client:
        project_id = _create_project_with_ingested_text(client, "Run Config Preset Export")

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={
                "mode": "author",
                "max_segment_chars": 180,
                "export_formats": ["json", "csv"],
                "deterministic_mode": True,
                "deterministic_seed": 2026,
                "allow_unfinalized_character_map": True,
            },
        )
        assert run_resp.status_code == 200
        run_id = int(run_resp.json()["run_id"])

        preset_resp = client.get(f"/api/projects/{project_id}/runs/{run_id}/config-preset")
        assert preset_resp.status_code == 200
        payload = preset_resp.json()

        assert payload["project_id"] == project_id
        assert payload["run_id"] == run_id
        assert payload["preset_schema_version"] == "1.0.0"
        assert isinstance(payload["generated_at"], str)
        assert payload["run_config"]["mode"] == "author"
        assert payload["run_config"]["max_segment_chars"] == 180
        assert payload["run_config"]["export_formats"] == ["json", "csv"]
        assert payload["run_config"]["deterministic_mode"] is True
        assert payload["run_config"]["deterministic_seed"] == 2026
        assert "allow_unfinalized_character_map" not in payload["run_config"]
        assert "configuration_snapshot_id" not in payload["run_config"]
        assert "configuration_snapshot_version" not in payload["run_config"]

        imported_run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json=payload["run_config"],
        )
        assert imported_run_resp.status_code == 200
        imported_run_id = int(imported_run_resp.json()["run_id"])

        imported_run_detail = client.get(f"/api/projects/{project_id}/runs/{imported_run_id}")
        assert imported_run_detail.status_code == 200
        imported_config = imported_run_detail.json()["config"]
        assert imported_config["mode"] == "author"
        assert imported_config["max_segment_chars"] == 180
        assert imported_config["export_formats"] == ["json", "csv"]
        assert imported_config["deterministic_mode"] is True
