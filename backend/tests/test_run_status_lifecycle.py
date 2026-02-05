import io
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_run_status_lifecycle.db"

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.main import app
from app.schemas import RunDetailResponse, RunResponse
from app.services.run_status import RUN_STATUS_VALUES


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_run_status_lifecycle.db")
    if db_file.exists():
        db_file.unlink()


def test_unit_run_schemas_accept_defined_status_lifecycle_values() -> None:
    now = datetime.now(timezone.utc)
    for status in RUN_STATUS_VALUES:
        response_payload = RunResponse(
            run_id=1,
            project_id=1,
            status=status,
            segment_count=0,
        )
        assert response_payload.status == status

        detail_payload = RunDetailResponse(
            run_id=1,
            project_id=1,
            status=status,
            config={"mode": "author"},
            started_at=now,
            finished_at=None,
            segment_count=0,
            llm_calls=[],
            llm_cache_metrics={},
        )
        assert detail_payload.status == status


def test_integration_run_lifecycle_records_queue_running_and_completed_events() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "X-004 Run Status Lifecycle"})
        assert project_resp.status_code == 201
        project_id = int(project_resp.json()["id"])

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": (
                    "x004-source.txt",
                    io.BytesIO(b"Chapter 1\nRain hammered the towers while the wardens waited."),
                    "text/plain",
                )
            },
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={
                "mode": "author",
                "max_segment_chars": 120,
                "llm_enabled": False,
                "provider_name": "openrouter",
                "max_calls_per_day": 5,
                "allow_unfinalized_character_map": True,
            },
        )
        assert run_resp.status_code == 200
        run_payload = run_resp.json()
        assert run_payload["status"] == "completed"
        run_id = int(run_payload["run_id"])

        detail_resp = client.get(f"/api/projects/{project_id}/runs/{run_id}")
        assert detail_resp.status_code == 200
        detail_payload = detail_resp.json()
        assert detail_payload["status"] == "completed"

        event_types = [entry["event_type"] for entry in detail_payload["changelog_entries"]]
        assert "pipeline_execution_queued" in event_types
        assert "pipeline_execution_started" in event_types
        assert "pipeline_completed" in event_types
        assert event_types.index("pipeline_execution_queued") < event_types.index("pipeline_execution_started")
        assert event_types.index("pipeline_execution_started") < event_types.index("pipeline_completed")

