import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_run_cancellation.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Run


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_run_cancellation.db")
    if db_file.exists():
        db_file.unlink()


def _create_project() -> int:
    with TestClient(app) as client:
        response = client.post("/api/projects", json={"title": "Run Cancellation Project"})
        assert response.status_code == 201
        return int(response.json()["id"])


def _create_run(project_id: int, status: str) -> int:
    session = get_session_factory()()
    try:
        run = Run(
            project_id=project_id,
            status=status,
            config_json={"mode": "author", "pipeline_recovery": {"status": status, "attempt": 1}},
            started_at=datetime.now(timezone.utc),
            finished_at=(datetime.now(timezone.utc) if status == "completed" else None),
        )
        session.add(run)
        session.commit()
        return int(run.id)
    finally:
        session.close()


def test_cancel_endpoint_cancels_running_run() -> None:
    project_id = _create_project()
    run_id = _create_run(project_id=project_id, status="running")

    with TestClient(app) as client:
        cancel_resp = client.post(f"/api/projects/{project_id}/runs/{run_id}/cancel")

    assert cancel_resp.status_code == 200
    payload = cancel_resp.json()
    assert payload["run_id"] == run_id
    assert payload["project_id"] == project_id
    assert payload["status"] == "cancelled"

    with TestClient(app) as client:
        detail_resp = client.get(f"/api/projects/{project_id}/runs/{run_id}")
    assert detail_resp.status_code == 200
    detail_payload = detail_resp.json()
    assert detail_payload["status"] == "cancelled"
    event_types = [entry["event_type"] for entry in detail_payload["changelog_entries"]]
    assert "pipeline_cancel_requested" in event_types


def test_cancel_endpoint_rejects_terminal_run_status() -> None:
    project_id = _create_project()
    run_id = _create_run(project_id=project_id, status="completed")

    with TestClient(app) as client:
        cancel_resp = client.post(f"/api/projects/{project_id}/runs/{run_id}/cancel")

    assert cancel_resp.status_code == 409
    assert cancel_resp.json()["detail"] == "Only queued or running runs can be cancelled."

