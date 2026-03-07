import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

DB_FILE = "test_nipe_project_allowed_actions_endpoint.db"
DB_URL = f"sqlite:///./{DB_FILE}"
os.environ["DATABASE_URL"] = DB_URL

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Project


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


def test_integration_project_allowed_actions_for_draft_and_completed_states() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects/drafts", json={"title": "Allowed Actions Draft"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        draft_actions_resp = client.get(f"/api/projects/{project_id}/actions")
        assert draft_actions_resp.status_code == 200
        draft_actions_payload = draft_actions_resp.json()
        assert draft_actions_payload["allowed_actions"] == ["ingest", "select_mode", "configure", "archive"]
        assert draft_actions_payload["next_required_action"] == "ingest"
        assert draft_actions_payload["blocked_reason"] is not None
        assert draft_actions_payload["required_step"] == "ingestion"

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("actions.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(f"/api/projects/{project_id}/runs", json={"mode": "author"})
        assert run_resp.status_code == 200

        completed_actions_resp = client.get(f"/api/projects/{project_id}/actions")
        assert completed_actions_resp.status_code == 200
        completed_actions_payload = completed_actions_resp.json()
        assert completed_actions_payload["lifecycle_state"] == "completed"
        assert completed_actions_payload["last_run_status"] == "completed"
        assert completed_actions_payload["next_required_action"] == "export"
        assert completed_actions_payload["blocked_reason"] is None
        assert completed_actions_payload["required_step"] is None
        assert completed_actions_payload["allowed_actions"] == [
            "ingest",
            "select_mode",
            "configure",
            "run",
            "export",
            "archive",
        ]


def test_integration_project_allowed_actions_for_failed_and_archived_states() -> None:
    with TestClient(app) as client:
        failed_project_resp = client.post("/api/projects/drafts", json={"title": "Allowed Actions Failed"})
        assert failed_project_resp.status_code == 201
        failed_project_id = failed_project_resp.json()["id"]

        failed_run_resp = client.post(
            f"/api/projects/{failed_project_id}/runs",
            json={"mode": "audiobook"},
        )
        assert failed_run_resp.status_code == 400

        failed_actions_resp = client.get(f"/api/projects/{failed_project_id}/actions")
        assert failed_actions_resp.status_code == 200
        failed_actions_payload = failed_actions_resp.json()
        assert failed_actions_payload["lifecycle_state"] == "failed"
        assert failed_actions_payload["last_run_status"] == "failed"
        assert failed_actions_payload["blocked_reason"] is not None
        assert failed_actions_payload["required_step"] == "initial_run"
        assert failed_actions_payload["allowed_actions"] == [
            "ingest",
            "select_mode",
            "configure",
            "run",
            "rerun",
            "archive",
        ]

        archived_project_resp = client.post("/api/projects/drafts", json={"title": "Allowed Actions Archived"})
        assert archived_project_resp.status_code == 201
        archived_project_id = archived_project_resp.json()["id"]

    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == archived_project_id).one()
        project.lifecycle_state = "archived"
        project.next_required_action = "archived"
        session.add(project)
        session.commit()
    finally:
        session.close()

    with TestClient(app) as client:
        archived_actions_resp = client.get(f"/api/projects/{archived_project_id}/actions")
        assert archived_actions_resp.status_code == 200
        archived_actions_payload = archived_actions_resp.json()
        assert archived_actions_payload["lifecycle_state"] == "archived"
        assert archived_actions_payload["next_required_action"] == "archived"
        assert archived_actions_payload["blocked_reason"] is not None
        assert archived_actions_payload["required_step"] == "restore"
        assert archived_actions_payload["allowed_actions"] == ["restore"]
