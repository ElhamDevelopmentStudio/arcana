import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

DB_FILE = "test_nipe_run_rerun_endpoint.db"
DB_URL = f"sqlite:///./{DB_FILE}"
os.environ["DATABASE_URL"] = DB_URL

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import ProjectActivityEvent, Run


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


def test_integration_rerun_endpoint_clones_source_snapshot_and_writes_lineage() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Rerun Snapshot Clone"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("rerun.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={
                "mode": "author",
                "max_segment_chars": 120,
                "llm_enabled": False,
                "provider_name": "openrouter",
                "max_calls_per_day": 25,
            },
        )
        assert run_resp.status_code == 200
        source_run_id = run_resp.json()["run_id"]

        source_run_detail_resp = client.get(f"/api/projects/{project_id}/runs/{source_run_id}")
        assert source_run_detail_resp.status_code == 200
        source_run_detail_payload = source_run_detail_resp.json()

        rerun_resp = client.post(f"/api/projects/{project_id}/runs/{source_run_id}/rerun")
        assert rerun_resp.status_code == 200
        rerun_payload = rerun_resp.json()
        rerun_run_id = rerun_payload["run_id"]
        assert rerun_run_id != source_run_id

        rerun_detail_resp = client.get(f"/api/projects/{project_id}/runs/{rerun_run_id}")
        assert rerun_detail_resp.status_code == 200
        rerun_detail_payload = rerun_detail_resp.json()

    rerun_config = rerun_detail_payload["config"]
    source_config = source_run_detail_payload["config"]
    assert rerun_config["mode"] == source_config["mode"]
    assert rerun_config["max_segment_chars"] == source_config["max_segment_chars"]
    assert rerun_config["provider_name"] == source_config["provider_name"]
    assert rerun_config["llm_enabled"] == source_config["llm_enabled"]
    assert rerun_config["rerun_source_run_id"] == source_run_id
    assert rerun_config["rerun_source_configuration_snapshot_id"] is not None
    assert rerun_config["rerun_source_configuration_snapshot_version"] is not None
    assert rerun_config["rerun_source_status"] == "completed"
    assert rerun_config["rerun_lineage_type"] == "snapshot_clone"
    assert isinstance(rerun_config["rerun_requested_at"], str)

    session = get_session_factory()()
    try:
        rerun_events = (
            session.query(ProjectActivityEvent)
            .filter(
                ProjectActivityEvent.project_id == project_id,
                ProjectActivityEvent.run_id == rerun_run_id,
                ProjectActivityEvent.event_type == "rerun",
            )
            .all()
        )
        assert len(rerun_events) == 1
        assert rerun_events[0].event_metadata.get("source_run_id") == source_run_id
    finally:
        session.close()


def test_integration_rerun_endpoint_rejects_running_source_run() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Rerun Running Source Rejected"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("running-rerun.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(f"/api/projects/{project_id}/runs", json={"mode": "author"})
        assert run_resp.status_code == 200
        source_run_id = run_resp.json()["run_id"]

    session = get_session_factory()()
    try:
        source_run = session.query(Run).filter(Run.id == source_run_id).one()
        source_run.status = "running"
        source_run.finished_at = None
        session.add(source_run)
        session.commit()
    finally:
        session.close()

    with TestClient(app) as client:
        rerun_resp = client.post(f"/api/projects/{project_id}/runs/{source_run_id}/rerun")
        assert rerun_resp.status_code == 409
        assert "can be rerun from snapshot" in rerun_resp.json()["detail"]
