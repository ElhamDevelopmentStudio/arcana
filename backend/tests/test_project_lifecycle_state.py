import io
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_project_lifecycle_state.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Project
from app.services.project_lifecycle import (
    ProjectLifecycleTransitionError,
    PROJECT_LIFECYCLE_COMPLETED,
    PROJECT_LIFECYCLE_CONFIGURED,
    PROJECT_LIFECYCLE_DRAFT,
    PROJECT_LIFECYCLE_FAILED,
    PROJECT_LIFECYCLE_INGESTED,
    PROJECT_LIFECYCLE_RUNNING,
    transition_project_lifecycle_state,
)


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()
    db_file = Path("test_nipe_project_lifecycle_state.db")
    if db_file.exists():
        db_file.unlink()


def _sample_txt() -> str:
    return (
        "Chapter 1\n"
        '"Sunny looked around," Sunny said. The cold wind cut through the dark street.\n\n'
        "Chapter 2\n"
        "Nephis smiled. Hope rose with the warm light."
    )


def _get_project_lifecycle_state(project_id: int) -> str:
    session = get_session_factory()()
    try:
        return session.query(Project).filter(Project.id == project_id).one().lifecycle_state
    finally:
        session.close()


def test_unit_project_lifecycle_rejects_invalid_transition() -> None:
    with pytest.raises(ProjectLifecycleTransitionError):
        transition_project_lifecycle_state(current_state="archived", next_state="running")


def test_integration_project_lifecycle_transitions_for_mode_ingest_run() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Lifecycle Integration"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]
        assert _get_project_lifecycle_state(project_id) == PROJECT_LIFECYCLE_DRAFT

        switch_resp = client.put(f"/api/projects/{project_id}/mode", json={"mode": "author"})
        assert switch_resp.status_code == 200
        assert _get_project_lifecycle_state(project_id) == PROJECT_LIFECYCLE_CONFIGURED

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200
        assert _get_project_lifecycle_state(project_id) == PROJECT_LIFECYCLE_INGESTED

        run_resp = client.post(f"/api/projects/{project_id}/runs", json={"mode": "author"})
        assert run_resp.status_code == 200

    assert _get_project_lifecycle_state(project_id) in {
        PROJECT_LIFECYCLE_RUNNING,
        PROJECT_LIFECYCLE_COMPLETED,
    }


def test_integration_project_lifecycle_moves_to_failed_when_run_errors() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Lifecycle Failure"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        run_resp = client.post(f"/api/projects/{project_id}/runs", json={"mode": "audiobook"})
        assert run_resp.status_code == 400

    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        assert project.lifecycle_state == PROJECT_LIFECYCLE_FAILED
    finally:
        session.close()
