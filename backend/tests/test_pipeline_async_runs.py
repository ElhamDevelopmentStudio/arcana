import io
import os

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_pipeline_async_runs.db"

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

    db_file = Path("test_nipe_pipeline_async_runs.db")
    if db_file.exists():
        db_file.unlink()


def _create_project_with_ingestion(client: TestClient, title: str) -> int:
    project_resp = client.post("/api/projects", json={"title": title})
    assert project_resp.status_code == 201
    project_id = int(project_resp.json()["id"])

    ingest_resp = client.post(
        f"/api/projects/{project_id}/ingest/txt",
        files={
            "file": (
                "novel.txt",
                io.BytesIO(b"Chapter 1\nAria said hi.\n\nChapter 2\nNora replied."),
                "text/plain",
            )
        },
    )
    assert ingest_resp.status_code == 200
    return project_id


def _dispatch_pipeline_inline(*, run_id: int, principal_type: str | None, principal_id: str | None):
    app_main.run_pipeline_run_by_id(
        run_id,
        principal_type=principal_type,
        principal_id=principal_id,
    )
    return ("thread", None)


def test_integration_run_endpoint_async_flag_dispatches_pipeline(monkeypatch) -> None:
    monkeypatch.setattr(app_main, "_dispatch_pipeline_run_execution", _dispatch_pipeline_inline)

    with TestClient(app) as client:
        project_id = _create_project_with_ingestion(client, "Async Run Endpoint")
        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            params={"async": "true"},
            json={"mode": "author", "llm_enabled": False},
        )
        assert run_resp.status_code == 200
        run_payload = run_resp.json()
        run_id = int(run_payload["run_id"])
        assert run_payload["project_id"] == project_id
        assert run_payload["segment_count"] >= 0
        assert run_payload["status"] in {"queued", "running", "completed"}

        detail_resp = client.get(f"/api/projects/{project_id}/runs/{run_id}")
        assert detail_resp.status_code == 200
        detail_payload = detail_resp.json()
        assert detail_payload["status"] == "completed"
        assert detail_payload["segment_count"] > 0


def test_integration_rerun_endpoint_async_flag_dispatches_pipeline(monkeypatch) -> None:
    monkeypatch.setattr(app_main, "_dispatch_pipeline_run_execution", _dispatch_pipeline_inline)

    with TestClient(app) as client:
        project_id = _create_project_with_ingestion(client, "Async Rerun Endpoint")
        base_run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"mode": "author", "llm_enabled": False},
        )
        assert base_run_resp.status_code == 200
        base_run_id = int(base_run_resp.json()["run_id"])

        rerun_resp = client.post(
            f"/api/projects/{project_id}/runs/{base_run_id}/rerun",
            params={"async": "true"},
        )
        assert rerun_resp.status_code == 200
        rerun_payload = rerun_resp.json()
        rerun_run_id = int(rerun_payload["run_id"])
        assert rerun_run_id != base_run_id
        assert rerun_payload["segment_count"] >= 0
        assert rerun_payload["status"] in {"queued", "running", "completed"}

        detail_resp = client.get(f"/api/projects/{project_id}/runs/{rerun_run_id}")
        assert detail_resp.status_code == 200
        detail_payload = detail_resp.json()
        assert detail_payload["status"] == "completed"
        assert detail_payload["segment_count"] > 0
