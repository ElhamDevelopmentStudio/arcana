import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_run_changelog.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Run, RunChangelogEntry


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_run_changelog.db")
    if db_file.exists():
        db_file.unlink()


def _ingest_project_text(project_title: str, source_payload: str) -> int:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": project_title})
        assert project_resp.status_code == 201
        project_id = int(project_resp.json()["id"])

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("story.txt", io.BytesIO(source_payload.encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        return project_id


def _run_project(project_id: int, payload: dict[str, object] | None = None) -> int:
    with TestClient(app) as client:
        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json=payload or {},
        )
        assert run_resp.status_code == 200
        run_id = int(run_resp.json()["run_id"])

    return run_id


def test_run_creation_records_changelog_entries_with_timestamps() -> None:
    project_id = _ingest_project_text(
        project_title="Run Changelog Project",
        source_payload=(
            "Chapter 1\n"
            "Nova stepped into the corridor, listening for the soft scrape of boots.\n"
            "She tightened her scarf and moved on."
        ),
    )
    run_id = _run_project(
        project_id=project_id,
        payload={"mode": "academic", "llm_enabled": False},
    )

    session = get_session_factory()()
    try:
        changelog_rows = (
            session.query(RunChangelogEntry)
            .filter(RunChangelogEntry.run_id == run_id)
            .order_by(RunChangelogEntry.id.asc())
            .all()
        )
        run = session.query(Run).filter(Run.id == run_id).one()

        event_types = [row.event_type for row in changelog_rows]
        assert "run_created" in event_types
        assert "pipeline_execution_queued" in event_types
        assert "pipeline_execution_started" in event_types
        assert "pipeline_completed" in event_types
        assert "run_configuration_snapshot_created" in event_types
        assert "time_series_snapshot_created" in event_types
        assert all(row.run_id == run.id and row.created_at is not None for row in changelog_rows)
        assert event_types.index("pipeline_execution_queued") < event_types.index("pipeline_execution_started")

        payload = [
            {
                "id": row.id,
                "event_type": row.event_type,
                "event_message": row.event_message,
                "event_metadata": row.event_metadata,
                "created_at": row.created_at,
            }
            for row in changelog_rows
        ]

        assert payload[0]["event_type"] == "run_created"
        assert payload[-1]["event_type"] == "pipeline_completed"
    finally:
        session.close()


def test_failed_run_records_pipeline_failure_changelog() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Run Changelog Failure Project"})
        assert project_resp.status_code == 201
        project_id = int(project_resp.json()["id"])

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"mode": "academic", "llm_enabled": False},
        )
        assert run_resp.status_code == 400

    session = get_session_factory()()
    try:
        run = session.query(Run).filter(Run.project_id == project_id).order_by(Run.id.desc()).first()
        assert run is not None
        assert run.status == "failed"

        changelog_rows = (
            session.query(RunChangelogEntry)
            .filter(RunChangelogEntry.run_id == run.id)
            .order_by(RunChangelogEntry.id.asc())
            .all()
        )

        assert any(row.event_type == "pipeline_failed" for row in changelog_rows)
        assert changelog_rows[-1].event_type == "pipeline_failed"
        assert changelog_rows[-1].event_message == "Pipeline error"
    finally:
        session.close()
