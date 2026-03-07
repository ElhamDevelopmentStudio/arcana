import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

DB_FILE = "test_nipe_project_dashboard_projection_fields.db"
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


def _get_project(project_id: int) -> Project:
    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        session.expunge(project)
        return project
    finally:
        session.close()


def test_integration_project_dashboard_projection_updates_after_completed_run_and_export() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Projection Completed Run"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("projection.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(f"/api/projects/{project_id}/runs", json={"mode": "author"})
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200

    project = _get_project(project_id)
    assert project.last_run_status == "completed"
    assert project.last_export_at is not None
    assert project.next_required_action == "export"


def test_integration_project_dashboard_projection_updates_after_failed_run() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Projection Failed Run"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"mode": "audiobook"},
        )
        assert run_resp.status_code == 400

    project = _get_project(project_id)
    assert project.last_run_status == "failed"
    assert project.last_export_at is None
    assert project.next_required_action == "review_failure"
