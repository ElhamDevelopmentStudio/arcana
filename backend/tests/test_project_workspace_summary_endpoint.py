import os
from pathlib import Path

from fastapi.testclient import TestClient

DB_FILE = "test_nipe_project_workspace_summary_endpoint.db"
DB_URL = f"sqlite:///./{DB_FILE}"
os.environ["DATABASE_URL"] = DB_URL

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.main import app
from app.schemas import ProjectWorkspaceSummaryResponse


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


def test_integration_project_workspace_summary_endpoint_for_draft_project() -> None:
    with TestClient(app) as client:
        create_resp = client.post("/api/projects/drafts", json={"title": "Workspace Summary Draft"})
        assert create_resp.status_code == 201
        project_id = create_resp.json()["id"]

        summary_resp = client.get(f"/api/projects/{project_id}/workspace-summary")
        assert summary_resp.status_code == 200
        payload = summary_resp.json()
        parsed = ProjectWorkspaceSummaryResponse.model_validate(payload)

    assert parsed.output_schema == "project_workspace_summary_json"
    assert parsed.project_id == project_id
    assert parsed.lifecycle_state == "draft"
    assert parsed.last_run_status is None
    assert parsed.next_required_action == "ingest"
    assert parsed.is_setup_complete is False
    assert parsed.chapters_count == 0
    assert parsed.characters_count == 0
    assert parsed.voice_mappings_count == 0
    assert parsed.runs_total_count == 0
    assert parsed.runs_completed_count == 0
    assert parsed.runs_failed_count == 0
    assert parsed.last_export_at is None


def test_regression_project_workspace_summary_endpoint_rejects_unknown_project() -> None:
    with TestClient(app) as client:
        summary_resp = client.get("/api/projects/999999999/workspace-summary")

    assert summary_resp.status_code == 404
    assert summary_resp.json()["detail"] == "Project not found"
