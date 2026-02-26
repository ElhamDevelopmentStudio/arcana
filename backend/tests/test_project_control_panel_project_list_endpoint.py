import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_project_control_panel_project_list_endpoint.db"

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.main import app


def setup_module() -> None:
    db_file = Path("test_nipe_project_control_panel_project_list_endpoint.db")
    if db_file.exists():
        db_file.unlink()
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()
    db_file = Path("test_nipe_project_control_panel_project_list_endpoint.db")
    if db_file.exists():
        db_file.unlink()


def _sample_txt() -> str:
    return (
        "Chapter 1\n"
        '"Sunny looked around," Sunny said. The cold wind cut through the dark street.\n\n'
        "Chapter 2\n"
        "Nephis smiled. Hope rose with the warm light."
    )


def test_integration_project_control_panel_project_list_empty_state() -> None:
    with TestClient(app) as client:
        response = client.get("/api/dashboard/project-control-panel/projects")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "1.0.0"
    assert payload["output_schema"] == "project_control_panel_project_list_json"
    assert payload["total_items"] == 0
    assert payload["page"] == 1
    assert payload["page_size"] == 20
    assert payload["has_next_page"] is False
    assert payload["items"] == []


def test_e2e_project_control_panel_project_list_supports_filters_and_pagination() -> None:
    with TestClient(app) as client:
        draft_resp = client.post("/api/projects/drafts", json={"title": "Project List Draft"})
        assert draft_resp.status_code == 201
        draft_project_id = draft_resp.json()["id"]

        ingested_resp = client.post("/api/projects/drafts", json={"title": "Project List Ingested"})
        assert ingested_resp.status_code == 201
        ingested_project_id = ingested_resp.json()["id"]
        ingest_resp = client.post(
            f"/api/projects/{ingested_project_id}/ingest/txt",
            files={"file": ("ingested.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        completed_resp = client.post("/api/projects/drafts", json={"title": "Project List Completed"})
        assert completed_resp.status_code == 201
        completed_project_id = completed_resp.json()["id"]
        completed_ingest_resp = client.post(
            f"/api/projects/{completed_project_id}/ingest/txt",
            files={"file": ("completed.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
        )
        assert completed_ingest_resp.status_code == 200
        completed_run_resp = client.post(
            f"/api/projects/{completed_project_id}/runs",
            json={"mode": "audiobook"},
        )
        assert completed_run_resp.status_code == 200

        failed_resp = client.post("/api/projects/drafts", json={"title": "Project List Failed"})
        assert failed_resp.status_code == 201
        failed_project_id = failed_resp.json()["id"]
        failed_run_resp = client.post(
            f"/api/projects/{failed_project_id}/runs",
            json={"mode": "audiobook"},
        )
        assert failed_run_resp.status_code == 400

        all_resp = client.get("/api/dashboard/project-control-panel/projects")
        assert all_resp.status_code == 200
        all_payload = all_resp.json()
        all_project_ids = {item["project_id"] for item in all_payload["items"]}
        assert {draft_project_id, ingested_project_id, completed_project_id, failed_project_id}.issubset(all_project_ids)

        ingest_filter_resp = client.get(
            "/api/dashboard/project-control-panel/projects",
            params={"next_required_action": "ingest"},
        )
        assert ingest_filter_resp.status_code == 200
        ingest_filter_ids = {item["project_id"] for item in ingest_filter_resp.json()["items"]}
        assert draft_project_id in ingest_filter_ids

        failed_status_filter_resp = client.get(
            "/api/dashboard/project-control-panel/projects",
            params={"status": "failed"},
        )
        assert failed_status_filter_resp.status_code == 200
        failed_status_filter_ids = {item["project_id"] for item in failed_status_filter_resp.json()["items"]}
        assert failed_project_id in failed_status_filter_ids

        failed_run_filter_resp = client.get(
            "/api/dashboard/project-control-panel/projects",
            params={"last_run_status": "failed"},
        )
        assert failed_run_filter_resp.status_code == 200
        failed_run_filter_ids = {item["project_id"] for item in failed_run_filter_resp.json()["items"]}
        assert failed_project_id in failed_run_filter_ids

        paged_resp = client.get(
            "/api/dashboard/project-control-panel/projects",
            params={"page": 1, "page_size": 2},
        )
        assert paged_resp.status_code == 200
        paged_payload = paged_resp.json()
        assert paged_payload["total_items"] >= 4
        assert paged_payload["page"] == 1
        assert paged_payload["page_size"] == 2
        assert len(paged_payload["items"]) == 2
        assert paged_payload["has_next_page"] is True


def test_regression_project_control_panel_project_list_rejects_invalid_filters() -> None:
    with TestClient(app) as client:
        invalid_status_resp = client.get(
            "/api/dashboard/project-control-panel/projects",
            params={"status": "unknown"},
        )
        assert invalid_status_resp.status_code == 400

        invalid_action_resp = client.get(
            "/api/dashboard/project-control-panel/projects",
            params={"next_required_action": "launch"},
        )
        assert invalid_action_resp.status_code == 400
