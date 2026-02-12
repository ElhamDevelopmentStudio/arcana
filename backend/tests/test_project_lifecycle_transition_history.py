import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

DB_FILE = "test_nipe_project_lifecycle_transition_history.db"
DB_URL = f"sqlite:///./{DB_FILE}"
os.environ["DATABASE_URL"] = DB_URL

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import ProjectLifecycleTransition
from app.services.project_lifecycle import (
    PROJECT_LIFECYCLE_CONFIGURED,
    PROJECT_LIFECYCLE_DRAFT,
    PROJECT_LIFECYCLE_FAILED,
    PROJECT_LIFECYCLE_INGESTED,
    PROJECT_LIFECYCLE_RUNNING,
)


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


def _get_project_transitions(project_id: int) -> list[ProjectLifecycleTransition]:
    session = get_session_factory()()
    try:
        return (
            session.query(ProjectLifecycleTransition)
            .filter(ProjectLifecycleTransition.project_id == project_id)
            .order_by(ProjectLifecycleTransition.id.asc())
            .all()
        )
    finally:
        session.close()


def test_integration_project_lifecycle_transition_history_records_mode_ingest_run() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Lifecycle Transition History Integration"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        mode_resp = client.put(f"/api/projects/{project_id}/mode", json={"mode": "author"})
        assert mode_resp.status_code == 200

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("history.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(f"/api/projects/{project_id}/runs", json={"mode": "author"})
        assert run_resp.status_code == 200

    transitions = _get_project_transitions(project_id)
    assert len(transitions) >= 3
    assert transitions[0].from_state == PROJECT_LIFECYCLE_DRAFT
    assert transitions[0].to_state == PROJECT_LIFECYCLE_CONFIGURED
    assert transitions[1].from_state == PROJECT_LIFECYCLE_CONFIGURED
    assert transitions[1].to_state == PROJECT_LIFECYCLE_INGESTED
    assert any(t.to_state == PROJECT_LIFECYCLE_RUNNING for t in transitions)
    assert all(t.actor.strip() for t in transitions)
    assert all(t.created_at is not None for t in transitions)


def test_e2e_project_lifecycle_transition_history_records_failed_pipeline_path() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Lifecycle Transition History Failure"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        run_resp = client.post(f"/api/projects/{project_id}/runs", json={"mode": "audiobook"})
        assert run_resp.status_code == 400

    transitions = _get_project_transitions(project_id)
    assert len(transitions) >= 2
    assert transitions[0].from_state == PROJECT_LIFECYCLE_DRAFT
    assert transitions[0].to_state == PROJECT_LIFECYCLE_RUNNING
    assert transitions[1].from_state == PROJECT_LIFECYCLE_RUNNING
    assert transitions[1].to_state == PROJECT_LIFECYCLE_FAILED
