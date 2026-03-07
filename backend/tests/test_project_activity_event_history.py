import io
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

DB_FILE = "test_nipe_project_activity_event_history.db"
DB_URL = f"sqlite:///./{DB_FILE}"
os.environ["DATABASE_URL"] = DB_URL

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import ProjectActivityEvent, Run, TimeSeriesSnapshot


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


def _get_project_activity_events(project_id: int) -> list[ProjectActivityEvent]:
    session = get_session_factory()()
    try:
        return (
            session.query(ProjectActivityEvent)
            .filter(ProjectActivityEvent.project_id == project_id)
            .order_by(ProjectActivityEvent.id.asc())
            .all()
        )
    finally:
        session.close()


def _mark_run_as_stale_running(run_id: int) -> None:
    session = get_session_factory()()
    try:
        run = session.query(Run).filter(Run.id == run_id).one()
        now = datetime.now(timezone.utc)
        run.status = "running"
        run.started_at = now - timedelta(minutes=30)
        run.finished_at = None
        run_config = dict(run.config_json or {})
        run_config["pipeline_recovery"] = {
            "status": "running",
            "attempt": 1,
            "updated_at": (now - timedelta(minutes=30)).isoformat(),
            "reason": "test_forced_stale",
        }
        session.query(TimeSeriesSnapshot).filter(TimeSeriesSnapshot.run_id == run_id).delete()
        run.config_json = run_config
        session.add(run)
        session.commit()
    finally:
        session.close()


def test_integration_project_activity_events_capture_core_timeline_actions() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Project Activity Event Timeline"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        metadata_resp = client.patch(
            f"/api/projects/{project_id}/metadata",
            json={
                "description": "Updated description",
                "tags": ["timeline", "history"],
            },
        )
        assert metadata_resp.status_code == 200

        mode_resp = client.put(f"/api/projects/{project_id}/mode", json={"mode": "author"})
        assert mode_resp.status_code == 200

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("history.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(f"/api/projects/{project_id}/runs", json={"mode": "author"})
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200

    activity_events = _get_project_activity_events(project_id)
    observed_event_types = {event.event_type for event in activity_events}
    assert {"manual_edit", "mode_change", "ingest", "run_start", "run_complete", "export"} <= observed_event_types

    run_start_events = [event for event in activity_events if event.event_type == "run_start"]
    assert run_start_events
    assert run_start_events[-1].run_id == run_id
    assert run_start_events[-1].event_metadata.get("mode") == "author"

    run_complete_events = [event for event in activity_events if event.event_type == "run_complete"]
    assert run_complete_events
    assert run_complete_events[-1].run_id == run_id
    assert run_complete_events[-1].event_metadata.get("status") == "completed"

    export_events = [event for event in activity_events if event.event_type == "export"]
    assert export_events
    assert export_events[-1].event_metadata.get("output_format") == "json"


def test_integration_project_activity_events_capture_rerun_event() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Project Activity Event Rerun"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("rerun.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(f"/api/projects/{project_id}/runs", json={"mode": "author"})
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        _mark_run_as_stale_running(run_id)

        recover_resp = client.post(f"/api/projects/{project_id}/runs/{run_id}/recover")
        assert recover_resp.status_code == 200

    activity_events = _get_project_activity_events(project_id)
    rerun_events = [event for event in activity_events if event.event_type == "rerun"]
    assert rerun_events
    assert rerun_events[-1].run_id == run_id
    run_complete_events = [event for event in activity_events if event.event_type == "run_complete"]
    assert len(run_complete_events) >= 2
