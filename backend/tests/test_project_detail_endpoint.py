import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

DB_FILE = "test_nipe_project_detail_endpoint.db"
DB_URL = f"sqlite:///./{DB_FILE}"
os.environ["DATABASE_URL"] = DB_URL

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.main import app


def setup_module() -> None:
    os.environ["DATABASE_URL"] = DB_URL
    db_file = Path(DB_FILE)
    if db_file.exists():
        db_file.unlink()
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()
    db_file = Path(DB_FILE)
    if db_file.exists():
        db_file.unlink()


def _sample_txt() -> str:
    return (
        "Chapter 1\n"
        '"Sunny looked around," Sunny said. The cold wind cut through the dark street.\n\n'
        "Chapter 2\n"
        "Nephis smiled. Hope rose with the warm light."
    )


def test_integration_project_detail_endpoint_returns_expected_contract_for_draft_project() -> None:
    with TestClient(app) as client:
        create_resp = client.post("/api/projects/drafts", json={"title": "Project Detail Draft"})
        assert create_resp.status_code == 201
        project_id = create_resp.json()["id"]

        metadata_resp = client.patch(
            f"/api/projects/{project_id}/metadata",
            json={"description": "Detail endpoint description", "tags": ["detail", "draft"]},
        )
        assert metadata_resp.status_code == 200

        detail_resp = client.get(f"/api/projects/{project_id}")
        assert detail_resp.status_code == 200
        payload = detail_resp.json()

    assert payload["schema_version"] == "1.0.0"
    assert payload["output_schema"] == "project_detail_json"
    assert payload["project_id"] == project_id
    assert payload["title"] == "Project Detail Draft"
    assert payload["description"] == "Detail endpoint description"
    assert payload["tags"] == ["detail", "draft"]
    assert payload["lifecycle_state"] == "draft"
    assert payload["last_run_status"] is None
    assert payload["next_required_action"] == "ingest"
    assert payload["allowed_actions"] == ["ingest", "select_mode", "configure", "archive"]


def test_integration_project_detail_endpoint_reflects_ingested_and_completed_projection_fields() -> None:
    with TestClient(app) as client:
        create_resp = client.post("/api/projects/drafts", json={"title": "Project Detail Completed"})
        assert create_resp.status_code == 201
        project_id = create_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("detail.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(f"/api/projects/{project_id}/runs", json={"mode": "author"})
        assert run_resp.status_code == 200

        detail_resp = client.get(f"/api/projects/{project_id}")
        assert detail_resp.status_code == 200
        payload = detail_resp.json()

    assert payload["lifecycle_state"] == "completed"
    assert payload["last_run_status"] == "completed"
    assert payload["next_required_action"] == "export"
    assert "export" in payload["allowed_actions"]
    assert payload["ingestion_timestamp"] is not None


def test_regression_project_detail_endpoint_rejects_unknown_project() -> None:
    with TestClient(app) as client:
        detail_resp = client.get("/api/projects/999999999")

    assert detail_resp.status_code == 404
    assert detail_resp.json()["detail"] == "Project not found"

