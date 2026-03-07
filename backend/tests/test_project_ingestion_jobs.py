import io
import os

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_project_ingestion_jobs.db"

from pathlib import Path  # noqa: E402

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.main import app
import app.main as app_main


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_project_ingestion_jobs.db")
    if db_file.exists():
        db_file.unlink()


def _create_project(client: TestClient, title: str = "Async Ingestion Project") -> int:
    project_resp = client.post("/api/projects", json={"title": title})
    assert project_resp.status_code == 201
    return int(project_resp.json()["id"])


def test_integration_project_ingestion_job_lifecycle_completes(monkeypatch) -> None:
    def _run_inline(job_id: str):
        app_main.run_project_ingestion_job_by_id(job_id)
        return ("thread", None)

    monkeypatch.setattr(app_main, "_dispatch_project_ingestion_job", _run_inline)

    with TestClient(app) as client:
        project_id = _create_project(client)
        start_resp = client.post(
            f"/api/projects/{project_id}/ingest/jobs",
            data={"source": "txt"},
            files={"file": ("novel.txt", io.BytesIO(b"Chapter 1\nAria said hi."), "text/plain")},
        )
        assert start_resp.status_code == 202
        start_payload = start_resp.json()
        assert start_payload["project_id"] == project_id
        assert start_payload["job_id"]
        assert start_payload["source"] == "txt"

        status_resp = client.get(f"/api/projects/{project_id}/ingest/jobs/{start_payload['job_id']}")
        assert status_resp.status_code == 200
        status_payload = status_resp.json()
        assert status_payload["status"] == "completed"
        assert status_payload["progress"] == 100
        assert status_payload["result"] is not None
        assert status_payload["result"]["chapter_count"] >= 1


def test_integration_project_ingestion_job_status_not_found() -> None:
    with TestClient(app) as client:
        project_id = _create_project(client, title="Missing Ingestion Job")
        status_resp = client.get(f"/api/projects/{project_id}/ingest/jobs/not-a-real-job-id")
        assert status_resp.status_code == 404
        assert status_resp.json()["detail"] == "Project ingestion job not found."


def test_integration_project_ingestion_job_rejects_concurrent_active_job(monkeypatch) -> None:
    monkeypatch.setattr(app_main, "_dispatch_project_ingestion_job", lambda _job_id: ("thread", None))

    with TestClient(app) as client:
        project_id = _create_project(client, title="Concurrent Ingestion Job")
        first_resp = client.post(
            f"/api/projects/{project_id}/ingest/jobs",
            data={"source": "txt"},
            files={"file": ("novel.txt", io.BytesIO(b"Chapter 1\nAria said hi."), "text/plain")},
        )
        assert first_resp.status_code == 202

        second_resp = client.post(
            f"/api/projects/{project_id}/ingest/jobs",
            data={"source": "txt"},
            files={"file": ("novel-2.txt", io.BytesIO(b"Chapter 1\nMira said hi."), "text/plain")},
        )
        assert second_resp.status_code == 409
        assert "Ingestion is already running for this project." in second_resp.json()["detail"]
