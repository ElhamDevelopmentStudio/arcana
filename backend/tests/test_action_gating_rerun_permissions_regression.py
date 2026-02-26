import io
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

DB_FILE = "test_nipe_action_gating_rerun_permissions_regression.db"
DB_URL = f"sqlite:///./{DB_FILE}"
os.environ["DATABASE_URL"] = DB_URL

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Project, Run


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


def _set_project_state(project_id: int, lifecycle_state: str, last_run_status: str | None) -> None:
    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        project.lifecycle_state = lifecycle_state
        project.last_run_status = last_run_status
        session.add(project)
        session.commit()
    finally:
        session.close()


def _set_run_status(run_id: int, status_value: str) -> None:
    session = get_session_factory()()
    try:
        run = session.query(Run).filter(Run.id == run_id).one()
        run.status = status_value
        if status_value in {"queued", "running"}:
            run.finished_at = None
        else:
            run.finished_at = datetime.now(timezone.utc)
        session.add(run)
        session.commit()
    finally:
        session.close()


@pytest.mark.parametrize(
    ("lifecycle_state", "last_run_status", "expected_actions"),
    [
        ("draft", None, ["ingest", "select_mode", "configure", "archive"]),
        ("ingested", None, ["ingest", "select_mode", "configure", "run", "archive"]),
        ("configured", None, ["ingest", "select_mode", "configure", "run", "archive"]),
        ("running", "running", []),
        ("completed", "completed", ["ingest", "select_mode", "configure", "run", "export", "archive"]),
        ("failed", "failed", ["ingest", "select_mode", "configure", "run", "rerun", "archive"]),
        ("archived", None, ["restore"]),
    ],
)
def test_integration_allowed_actions_regression_matrix_by_lifecycle_state(
    lifecycle_state: str,
    last_run_status: str | None,
    expected_actions: list[str],
) -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects/drafts", json={"title": f"Actions Matrix {lifecycle_state}"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

    _set_project_state(project_id, lifecycle_state, last_run_status)

    with TestClient(app) as client:
        actions_resp = client.get(f"/api/projects/{project_id}/actions")
        assert actions_resp.status_code == 200
        actions_payload = actions_resp.json()

    assert actions_payload["lifecycle_state"] == lifecycle_state
    assert actions_payload["last_run_status"] == last_run_status
    assert actions_payload["allowed_actions"] == expected_actions


@pytest.mark.parametrize(
    ("source_status", "expected_status_code"),
    [
        ("queued", 409),
        ("running", 409),
        ("completed", 200),
        ("failed", 200),
        ("cancelled", 200),
        ("interrupted", 200),
    ],
)
def test_integration_rerun_permissions_regression_matrix_by_source_run_status(
    source_status: str,
    expected_status_code: int,
) -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": f"Rerun Matrix {source_status}"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("rerun-matrix.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(f"/api/projects/{project_id}/runs", json={"mode": "author"})
        assert run_resp.status_code == 200
        source_run_id = run_resp.json()["run_id"]

    _set_run_status(source_run_id, source_status)

    with TestClient(app) as client:
        rerun_resp = client.post(f"/api/projects/{project_id}/runs/{source_run_id}/rerun")

    assert rerun_resp.status_code == expected_status_code
    if expected_status_code == 409:
        assert rerun_resp.json()["detail"] == "Only completed, failed, cancelled, or interrupted runs can be rerun from snapshot."
    else:
        rerun_payload = rerun_resp.json()
        assert rerun_payload["run_id"] != source_run_id

