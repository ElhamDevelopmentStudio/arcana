import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_export_manifest.db"

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

    db_file = Path("test_nipe_export_manifest.db")
    if db_file.exists():
        db_file.unlink()


def test_export_json_includes_manifest_metadata() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Manifest Package Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", io.BytesIO(b"Chapter 1\nThe lantern burned low and the rain beat softly outside."), "text/plain")},
        )
        assert ingest_resp.status_code == 200
        assert ingest_resp.json()["chapter_count"] == 1

        run_resp = client.post(f"/api/projects/{project_id}/runs", json={"max_segment_chars": 80})
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200
        export_payload = export_resp.json()

        assert export_payload["project_id"] == project_id
        assert export_payload["run_id"] == run_id
        assert export_payload["status"] == "completed"
        assert isinstance(export_payload["segments"], list)

        manifest = export_payload.get("manifest")
        assert isinstance(manifest, dict)
        assert manifest["schema_version"] == "1.0.0"
        assert manifest["export_type"] == "audiobook_tts_package"
        assert manifest["export_format"] == "json"
        assert isinstance(manifest["generated_at"], str)
        assert manifest["segment_count"] == len(export_payload["segments"])
        assert manifest["ordered_by"] == ["chapter_index", "segment_index"]
        assert manifest["project"]["id"] == project_id
        assert manifest["project"]["title"] == "Manifest Package Project"
        assert manifest["run"]["id"] == run_id
        assert manifest["run"]["status"] == "completed"
        assert isinstance(manifest["run"]["config_snapshot"], dict)

