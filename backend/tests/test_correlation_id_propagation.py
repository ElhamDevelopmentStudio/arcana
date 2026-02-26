import io
import os
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_correlation_id_propagation.db"

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.main import app


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_correlation_id_propagation.db")
    if db_file.exists():
        db_file.unlink()


def _create_project_ingest_and_run(client: TestClient, *, correlation_id: str | None) -> tuple[int, int]:
    project_resp = client.post("/api/projects", json={"title": "Correlation Propagation Project"})
    assert project_resp.status_code == 201
    project_id = int(project_resp.json()["id"])

    ingest_resp = client.post(
        f"/api/projects/{project_id}/ingest/txt",
        files={
            "file": (
                "correlation.txt",
                io.BytesIO(b"Chapter 1\nThe lantern swayed while the corridor hummed."),
                "text/plain",
            )
        },
    )
    assert ingest_resp.status_code == 200

    request_headers = {"X-Correlation-Id": correlation_id} if correlation_id else None
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
        headers=request_headers,
    )
    assert run_resp.status_code == 200
    run_id = int(run_resp.json()["run_id"])
    return project_id, run_id


def test_explicit_correlation_id_header_propagates_to_run_worker_and_export() -> None:
    correlation_id = "corr-propagation-explicit-001"
    with TestClient(app) as client:
        project_id, run_id = _create_project_ingest_and_run(client, correlation_id=correlation_id)

        run_detail_resp = client.get(f"/api/projects/{project_id}/runs/{run_id}")
        assert run_detail_resp.status_code == 200
        run_detail_payload = run_detail_resp.json()
        assert run_detail_payload["config"]["correlation_id"] == correlation_id

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200
        assert export_resp.headers.get("x-correlation-id") == correlation_id
        export_payload = export_resp.json()
        assert export_payload["correlation_id"] == correlation_id
        assert export_payload["manifest"]["correlation_id"] == correlation_id
        assert export_payload["manifest"]["run"]["correlation_id"] == correlation_id
        assert export_payload["manifest"]["academic_export_manifest"]["correlation_id"] == correlation_id


def test_missing_correlation_id_header_generates_and_propagates_id() -> None:
    with TestClient(app) as client:
        project_id, run_id = _create_project_ingest_and_run(client, correlation_id=None)

        run_detail_resp = client.get(f"/api/projects/{project_id}/runs/{run_id}")
        assert run_detail_resp.status_code == 200
        run_detail_payload = run_detail_resp.json()
        generated_correlation_id = str(run_detail_payload["config"]["correlation_id"])
        assert generated_correlation_id
        assert str(UUID(generated_correlation_id)) == generated_correlation_id

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200
        assert export_resp.headers.get("x-correlation-id") == generated_correlation_id
        export_payload = export_resp.json()
        assert export_payload["correlation_id"] == generated_correlation_id
        assert export_payload["manifest"]["correlation_id"] == generated_correlation_id
        assert export_payload["manifest"]["run"]["correlation_id"] == generated_correlation_id
        assert export_payload["manifest"]["academic_export_manifest"]["correlation_id"] == generated_correlation_id
