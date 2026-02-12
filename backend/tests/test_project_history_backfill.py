import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_FILE = "test_nipe_project_history_backfill.db"
DB_URL = f"sqlite:///./{DB_FILE}"
os.environ["DATABASE_URL"] = DB_URL

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import _backfill_project_lifecycle_and_activity_records
from app.models import Project, ProjectActivityEvent, ProjectLifecycleTransition, Run
from app.services.project_lifecycle import PROJECT_LIFECYCLE_COMPLETED


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


def test_integration_project_history_backfill_initializes_legacy_records_idempotently() -> None:
    now = datetime.now(timezone.utc)
    session = get_session_factory()()
    try:
        project = Project(
            title="Legacy Backfill Project",
            lifecycle_state=PROJECT_LIFECYCLE_COMPLETED,
            selected_mode="author",
            selected_modes=["author"],
            ingestion_timestamp=now - timedelta(hours=2),
            last_export_at=now - timedelta(minutes=30),
            created_at=now - timedelta(hours=3),
        )
        session.add(project)
        session.flush()

        run = Run(
            project_id=project.id,
            status="completed",
            started_at=now - timedelta(hours=1),
            finished_at=now - timedelta(minutes=40),
            config_json={
                "mode": "author",
                "pipeline_recovery": {
                    "attempt": 1,
                    "status": "completed",
                },
            },
        )
        session.add(run)
        session.commit()

        assert (
            session.query(ProjectLifecycleTransition)
            .filter(ProjectLifecycleTransition.project_id == project.id)
            .count()
            == 0
        )
        assert (
            session.query(ProjectActivityEvent)
            .filter(ProjectActivityEvent.project_id == project.id)
            .count()
            == 0
        )

        first_backfill = _backfill_project_lifecycle_and_activity_records(session=session)
        session.commit()
        assert first_backfill["transitions_created"] >= 1
        assert first_backfill["events_created"] >= 1

        transitions = (
            session.query(ProjectLifecycleTransition)
            .filter(ProjectLifecycleTransition.project_id == project.id)
            .order_by(ProjectLifecycleTransition.id.asc())
            .all()
        )
        assert len(transitions) == 1
        assert transitions[0].from_state == "draft"
        assert transitions[0].to_state == PROJECT_LIFECYCLE_COMPLETED

        events = (
            session.query(ProjectActivityEvent)
            .filter(ProjectActivityEvent.project_id == project.id)
            .order_by(ProjectActivityEvent.id.asc())
            .all()
        )
        event_types = {event.event_type for event in events}
        assert {"ingest", "mode_change", "run_start", "run_complete", "rerun", "export"} <= event_types

        transition_count_before = len(transitions)
        event_count_before = len(events)
        second_backfill = _backfill_project_lifecycle_and_activity_records(session=session)
        session.commit()
        assert second_backfill["transitions_created"] == 0
        assert second_backfill["events_created"] == 0
        assert (
            session.query(ProjectLifecycleTransition)
            .filter(ProjectLifecycleTransition.project_id == project.id)
            .count()
            == transition_count_before
        )
        assert (
            session.query(ProjectActivityEvent)
            .filter(ProjectActivityEvent.project_id == project.id)
            .count()
            == event_count_before
        )
    finally:
        session.close()
