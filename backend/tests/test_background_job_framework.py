import io
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_background_job_framework.db"

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.main import app
from app.services.background_jobs import (
    BackgroundJobFrameworkError,
    get_background_job_executor,
    submit_background_job,
)


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_background_job_framework.db")
    if db_file.exists():
        db_file.unlink()


def test_unit_inline_background_job_executor_executes_job() -> None:
    result = submit_background_job(
        job_name="unit_inline_job",
        execute=lambda: {"ok": True, "value": 42},
    )
    assert result == {"ok": True, "value": 42}


def test_unit_background_job_executor_rejects_unknown_executor() -> None:
    with pytest.raises(BackgroundJobFrameworkError, match="Unsupported background job executor"):
        get_background_job_executor("nonexistent-executor")


def test_integration_create_run_submits_pipeline_through_background_job_framework(monkeypatch: object) -> None:
    call_counter = {"count": 0}
    observed_correlation_ids: list[str | None] = []
    expected_correlation_id = "corr-bg-framework-001"

    def _counted_submit_background_job(*, job_name: str, execute, executor_name=None, correlation_id=None):  # noqa: ANN001
        call_counter["count"] += 1
        assert job_name == "pipeline_execute_run"
        assert executor_name is None
        observed_correlation_ids.append(correlation_id)
        return execute()

    monkeypatch.setattr("app.main.submit_background_job", _counted_submit_background_job)

    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "X-003 Background Job Framework"})
        assert project_resp.status_code == 201
        project_id = int(project_resp.json()["id"])

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": (
                    "x003.txt",
                    io.BytesIO(
                        b"Chapter 1\nThe watchlights swept the gate while rain tapped the roof.",
                    ),
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
            headers={"X-Correlation-Id": expected_correlation_id},
        )
        assert run_resp.status_code == 200
        payload = run_resp.json()
        assert payload["status"] == "completed"

    assert call_counter["count"] == 1
    assert observed_correlation_ids == [expected_correlation_id]
