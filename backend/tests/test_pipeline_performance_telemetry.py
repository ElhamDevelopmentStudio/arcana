import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_pipeline_performance_telemetry.db"

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

    db_file = Path("test_nipe_pipeline_performance_telemetry.db")
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


def _run_project(project_id: int) -> int:
    with TestClient(app) as client:
        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"mode": "academic", "llm_enabled": False},
        )
        assert run_resp.status_code == 200
        payload = run_resp.json()
        assert payload["segment_count"] > 0
        return int(payload["run_id"])


def test_run_captures_performance_telemetry_in_config_and_changelog() -> None:
    project_id = _ingest_project_text(
        project_title="Pipeline Telemetry Project",
        source_payload=(
            "Chapter 1\n"
            "Nova stepped into the corridor, listening to the soft scrape of boots.\n"
            "She tightened her scarf and moved on.\n"
            'He whispered, "The gate closes at dawn."'
        ),
    )
    run_id = _run_project(project_id=project_id)

    session = get_session_factory()()
    try:
        run = session.query(Run).filter(Run.id == run_id).one()
        telemetry = run.config_json.get("performance_telemetry")
        assert isinstance(telemetry, dict)
        assert isinstance(telemetry.get("total_duration_ms"), int)
        assert telemetry["total_duration_ms"] >= 0

        steps = telemetry.get("steps")
        assert isinstance(steps, list)
        assert steps
        for step in steps:
            assert step.get("name")
            assert step.get("duration_ms") is not None and step["duration_ms"] >= 0
            if step.get("memory_bytes_start") is not None:
                assert isinstance(step["memory_bytes_start"], int)
            if step.get("memory_bytes_end") is not None:
                assert isinstance(step["memory_bytes_end"], int)
            if step.get("memory_bytes_delta") is not None:
                assert isinstance(step["memory_bytes_delta"], int)

        changelog_entries = (
            session.query(RunChangelogEntry)
            .filter(
                RunChangelogEntry.run_id == run.id,
                RunChangelogEntry.event_type == "pipeline_performance_telemetry",
            )
            .order_by(RunChangelogEntry.id.asc())
            .all()
        )
        assert changelog_entries, "expected telemetry changelog entry"
        latest = changelog_entries[-1]
        assert latest.event_message == "Pipeline performance telemetry captured"
        latest_metadata = latest.event_metadata.get("performance_telemetry")
        assert isinstance(latest_metadata, dict)
        assert latest_metadata["total_duration_ms"] == telemetry["total_duration_ms"]
    finally:
        session.close()
