import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

DB_FILE = "test_nipe_project_archive_restore_endpoints.db"
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


def _force_running_state(project_id: int) -> None:
    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        project.lifecycle_state = "running"
        project.last_run_status = "running"
        project.next_required_action = "none"
        session.add(project)
        session.commit()
    finally:
        session.close()


def test_integration_archive_and_restore_project_from_draft_state() -> None:
    with TestClient(app) as client:
        create_resp = client.post("/api/projects/drafts", json={"title": "Archive Restore Draft"})
        assert create_resp.status_code == 201
        project_id = create_resp.json()["id"]

        archive_resp = client.post(f"/api/projects/{project_id}/archive")
        assert archive_resp.status_code == 200
        archive_payload = archive_resp.json()
        assert archive_payload["action"] == "archive"
        assert archive_payload["previous_lifecycle_state"] == "draft"
        assert archive_payload["lifecycle_state"] == "archived"
        assert archive_payload["next_required_action"] == "archived"
        assert archive_payload["allowed_actions"] == ["restore"]

        archived_actions_resp = client.get(f"/api/projects/{project_id}/actions")
        assert archived_actions_resp.status_code == 200
        assert archived_actions_resp.json()["allowed_actions"] == ["restore"]

        restore_resp = client.post(f"/api/projects/{project_id}/restore")
        assert restore_resp.status_code == 200
        restore_payload = restore_resp.json()
        assert restore_payload["action"] == "restore"
        assert restore_payload["previous_lifecycle_state"] == "archived"
        assert restore_payload["lifecycle_state"] == "draft"
        assert restore_payload["next_required_action"] == "ingest"
        assert restore_payload["allowed_actions"] == ["ingest", "select_mode", "configure", "archive"]

        detail_resp = client.get(f"/api/projects/{project_id}")
        assert detail_resp.status_code == 200
        detail_payload = detail_resp.json()
        assert detail_payload["lifecycle_state"] == "draft"
        assert detail_payload["allowed_actions"] == ["ingest", "select_mode", "configure", "archive"]


def test_integration_restore_recovers_previous_ingested_state() -> None:
    with TestClient(app) as client:
        create_resp = client.post("/api/projects/drafts", json={"title": "Archive Restore Ingested"})
        assert create_resp.status_code == 201
        project_id = create_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("restore-ingested.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        archive_resp = client.post(f"/api/projects/{project_id}/archive")
        assert archive_resp.status_code == 200
        assert archive_resp.json()["previous_lifecycle_state"] == "ingested"

        restore_resp = client.post(f"/api/projects/{project_id}/restore")
        assert restore_resp.status_code == 200
        restore_payload = restore_resp.json()
        assert restore_payload["lifecycle_state"] == "ingested"
        assert restore_payload["next_required_action"] == "run"
        assert "run" in restore_payload["allowed_actions"]


def test_regression_archive_rejected_for_running_state_and_restore_rejected_for_non_archived() -> None:
    with TestClient(app) as client:
        create_resp = client.post("/api/projects/drafts", json={"title": "Archive Reject Running"})
        assert create_resp.status_code == 201
        project_id = create_resp.json()["id"]

    _force_running_state(project_id)

    with TestClient(app) as client:
        archive_resp = client.post(f"/api/projects/{project_id}/archive")
        assert archive_resp.status_code == 409
        assert archive_resp.json()["detail"] == "Project cannot be archived in its current state."

        non_archived_restore_resp = client.post(f"/api/projects/{project_id}/restore")
        assert non_archived_restore_resp.status_code == 409
        assert non_archived_restore_resp.json()["detail"] == "Only archived projects can be restored."

