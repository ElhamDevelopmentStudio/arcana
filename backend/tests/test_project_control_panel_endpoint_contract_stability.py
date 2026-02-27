import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

DB_FILE = "test_nipe_project_control_panel_endpoint_contract_stability.db"
DB_URL = f"sqlite:///./{DB_FILE}"
os.environ["DATABASE_URL"] = DB_URL

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.main import app
from app.schemas import (
    ProjectActivityTimelineResponse,
    ProjectControlPanelProjectListResponse,
    ProjectControlPanelSummaryResponse,
    ProjectDetailResponse,
    ProjectLifecycleStateChangeResponse,
)


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


def _seed_control_panel_data(client: TestClient) -> None:
    draft_resp = client.post("/api/projects/drafts", json={"title": "Contract Stability Draft"})
    assert draft_resp.status_code == 201

    ingested_resp = client.post("/api/projects/drafts", json={"title": "Contract Stability Ingested"})
    assert ingested_resp.status_code == 201
    ingested_project_id = ingested_resp.json()["id"]
    ingest_resp = client.post(
        f"/api/projects/{ingested_project_id}/ingest/txt",
        files={"file": ("contract-ingested.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
    )
    assert ingest_resp.status_code == 200

    completed_resp = client.post("/api/projects/drafts", json={"title": "Contract Stability Completed"})
    assert completed_resp.status_code == 201
    completed_project_id = completed_resp.json()["id"]
    completed_ingest_resp = client.post(
        f"/api/projects/{completed_project_id}/ingest/txt",
        files={"file": ("contract-completed.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
    )
    assert completed_ingest_resp.status_code == 200
    completed_run_resp = client.post(
        f"/api/projects/{completed_project_id}/runs",
        json={"mode": "audiobook"},
    )
    assert completed_run_resp.status_code == 200

    failed_resp = client.post("/api/projects/drafts", json={"title": "Contract Stability Failed"})
    assert failed_resp.status_code == 201
    failed_project_id = failed_resp.json()["id"]
    failed_run_resp = client.post(
        f"/api/projects/{failed_project_id}/runs",
        json={"mode": "audiobook"},
    )
    assert failed_run_resp.status_code == 400


def test_integration_project_control_panel_summary_contract_stability() -> None:
    with TestClient(app) as client:
        _seed_control_panel_data(client)
        response = client.get("/api/dashboard/project-control-panel/summary")

    assert response.status_code == 200
    payload = response.json()
    parsed = ProjectControlPanelSummaryResponse.model_validate(payload)
    assert parsed.output_schema == "project_control_panel_summary_json"

    assert set(payload.keys()) == {
        "schema_version",
        "output_schema",
        "output_format",
        "output_id",
        "output_name",
        "generated_at",
        "generated_by",
        "total_projects",
        "project_counts_by_state",
        "active_run_count",
        "blocked_export_project_count",
        "blocked_export_run_count",
        "recent_failure_count",
        "recent_failures",
    }
    assert [item["lifecycle_state"] for item in payload["project_counts_by_state"]] == [
        "draft",
        "ingested",
        "configured",
        "running",
        "completed",
        "failed",
        "archived",
    ]
    assert all(set(item.keys()) == {"lifecycle_state", "project_count"} for item in payload["project_counts_by_state"])
    if payload["recent_failures"]:
        assert set(payload["recent_failures"][0].keys()) == {
            "project_id",
            "project_title",
            "run_id",
            "failed_at",
            "error_code",
            "error_message",
        }


def test_integration_project_control_panel_project_list_contract_stability() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/api/dashboard/project-control-panel/projects",
            params={"page": 1, "page_size": 50},
        )

    assert response.status_code == 200
    payload = response.json()
    parsed = ProjectControlPanelProjectListResponse.model_validate(payload)
    assert parsed.output_schema == "project_control_panel_project_list_json"

    assert set(payload.keys()) == {
        "schema_version",
        "output_schema",
        "output_format",
        "output_id",
        "output_name",
        "generated_at",
        "generated_by",
        "total_items",
        "page",
        "page_size",
        "has_next_page",
        "items",
    }
    if payload["items"]:
        assert set(payload["items"][0].keys()) == {
            "project_id",
            "status",
            "selected_mode",
            "last_run_status",
            "updated_at",
            "next_required_action",
        }


def test_integration_project_activity_timeline_contract_stability() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects/drafts", json={"title": "Contract Stability Timeline"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]
        metadata_resp = client.patch(
            f"/api/projects/{project_id}/metadata",
            json={"description": "timeline contract"},
        )
        assert metadata_resp.status_code == 200
        response = client.get(f"/api/projects/{project_id}/timeline", params={"page": 1, "page_size": 20})

    assert response.status_code == 200
    payload = response.json()
    parsed = ProjectActivityTimelineResponse.model_validate(payload)
    assert parsed.output_schema == "project_activity_timeline_json"
    assert set(payload.keys()) == {
        "schema_version",
        "output_schema",
        "output_format",
        "output_id",
        "output_name",
        "generated_at",
        "generated_by",
        "project_id",
        "total_items",
        "page",
        "page_size",
        "has_next_page",
        "items",
    }
    if payload["items"]:
        assert set(payload["items"][0].keys()) == {
            "event_id",
            "event_type",
            "actor",
            "run_id",
            "created_at",
            "event_metadata",
        }


def test_integration_project_detail_contract_stability() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects/drafts", json={"title": "Contract Stability Project Detail"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]
        response = client.get(f"/api/projects/{project_id}")

    assert response.status_code == 200
    payload = response.json()
    parsed = ProjectDetailResponse.model_validate(payload)
    assert parsed.output_schema == "project_detail_json"
    assert set(payload.keys()) == {
        "schema_version",
        "output_schema",
        "output_format",
        "output_id",
        "output_name",
        "generated_at",
        "generated_by",
        "project_id",
        "title",
        "description",
        "tags",
        "lifecycle_state",
        "last_run_status",
        "next_required_action",
        "allowed_actions",
        "selected_mode",
        "selected_modes",
        "llm_enabled",
        "do_not_store_source_text",
        "character_map_finalized",
        "configuration_snapshot_id",
        "ingestion_timestamp",
        "last_export_at",
        "created_at",
        "updated_at",
    }


def test_integration_project_lifecycle_state_change_contract_stability() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects/drafts", json={"title": "Contract Stability Lifecycle Change"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        archive_resp = client.post(f"/api/projects/{project_id}/archive")
        assert archive_resp.status_code == 200
        archive_payload = archive_resp.json()
        archive_parsed = ProjectLifecycleStateChangeResponse.model_validate(archive_payload)
        assert archive_parsed.action == "archive"
        assert set(archive_payload.keys()) == {
            "schema_version",
            "output_schema",
            "output_format",
            "output_id",
            "output_name",
            "generated_at",
            "generated_by",
            "project_id",
            "action",
            "previous_lifecycle_state",
            "lifecycle_state",
            "last_run_status",
            "next_required_action",
            "allowed_actions",
        }

        restore_resp = client.post(f"/api/projects/{project_id}/restore")
        assert restore_resp.status_code == 200
        restore_payload = restore_resp.json()
        restore_parsed = ProjectLifecycleStateChangeResponse.model_validate(restore_payload)
        assert restore_parsed.action == "restore"
        assert set(restore_payload.keys()) == set(archive_payload.keys())
