import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

DB_FILE = "test_nipe_project_control_panel_summary_endpoint.db"
DB_URL = f"sqlite:///./{DB_FILE}"
os.environ["DATABASE_URL"] = DB_URL

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.main import app


def setup_module() -> None:
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


def test_integration_project_control_panel_summary_empty_state() -> None:
    with TestClient(app) as client:
        summary_resp = client.get("/api/dashboard/project-control-panel/summary")
    assert summary_resp.status_code == 200
    payload = summary_resp.json()
    assert payload["schema_version"] == "1.0.0"
    assert payload["output_schema"] == "project_control_panel_summary_json"
    assert payload["total_projects"] == 0
    assert payload["active_run_count"] == 0
    assert payload["blocked_export_project_count"] == 0
    assert payload["blocked_export_run_count"] == 0
    assert payload["recent_failure_count"] == 0
    assert payload["recent_failures"] == []


def test_e2e_project_control_panel_summary_aggregates_project_and_run_signals() -> None:
    with TestClient(app) as client:
        draft_resp = client.post("/api/projects/drafts", json={"title": "Control Panel Draft"})
        assert draft_resp.status_code == 201

        ingested_resp = client.post("/api/projects/drafts", json={"title": "Control Panel Ingested"})
        assert ingested_resp.status_code == 201
        ingested_project_id = ingested_resp.json()["id"]
        ingest_resp = client.post(
            f"/api/projects/{ingested_project_id}/ingest/txt",
            files={"file": ("summary.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        failed_resp = client.post("/api/projects/drafts", json={"title": "Control Panel Failed"})
        assert failed_resp.status_code == 201
        failed_project_id = failed_resp.json()["id"]
        failed_run_resp = client.post(
            f"/api/projects/{failed_project_id}/runs",
            json={"mode": "audiobook"},
        )
        assert failed_run_resp.status_code == 400

        summary_resp = client.get("/api/dashboard/project-control-panel/summary")
        assert summary_resp.status_code == 200
        payload = summary_resp.json()

    assert payload["total_projects"] >= 3
    counts_by_state = {
        item["lifecycle_state"]: item["project_count"]
        for item in payload["project_counts_by_state"]
    }
    assert counts_by_state["draft"] >= 1
    assert counts_by_state["ingested"] >= 1
    assert counts_by_state["failed"] >= 1
    assert payload["blocked_export_project_count"] >= 2
    assert payload["blocked_export_run_count"] >= 1
    assert payload["recent_failure_count"] >= 1
    assert any(entry["project_id"] == failed_project_id for entry in payload["recent_failures"])
