import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

DB_FILE = "test_nipe_project_activity_timeline_endpoint.db"
DB_URL = f"sqlite:///./{DB_FILE}"
os.environ["DATABASE_URL"] = DB_URL

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.main import app
from app.schemas import ProjectActivityTimelineResponse


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


def test_integration_project_activity_timeline_endpoint_empty_state() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Timeline Empty State"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        timeline_resp = client.get(f"/api/projects/{project_id}/timeline")
        assert timeline_resp.status_code == 200
        payload = timeline_resp.json()
        parsed = ProjectActivityTimelineResponse.model_validate(payload)
        assert parsed.output_schema == "project_activity_timeline_json"
        assert parsed.project_id == project_id
        assert parsed.total_items == 0
        assert parsed.items == []


def test_integration_project_activity_timeline_endpoint_returns_descending_paginated_events() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Timeline Full State"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        metadata_resp = client.patch(
            f"/api/projects/{project_id}/metadata",
            json={"description": "Timeline detail", "tags": ["timeline"]},
        )
        assert metadata_resp.status_code == 200

        mode_resp = client.put(f"/api/projects/{project_id}/mode", json={"mode": "author"})
        assert mode_resp.status_code == 200

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("timeline.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(f"/api/projects/{project_id}/runs", json={"mode": "author"})
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200

        timeline_page_one_resp = client.get(
            f"/api/projects/{project_id}/timeline",
            params={"page": 1, "page_size": 3},
        )
        assert timeline_page_one_resp.status_code == 200
        page_one_payload = timeline_page_one_resp.json()
        parsed_page_one = ProjectActivityTimelineResponse.model_validate(page_one_payload)
        assert parsed_page_one.total_items >= 6
        assert parsed_page_one.page == 1
        assert parsed_page_one.page_size == 3
        assert parsed_page_one.has_next_page is True
        assert len(parsed_page_one.items) == 3
        page_one_event_ids = [item.event_id for item in parsed_page_one.items]
        assert page_one_event_ids == sorted(page_one_event_ids, reverse=True)
        observed_event_types = {item.event_type for item in parsed_page_one.items}
        assert observed_event_types & {"export", "run_complete", "run_start"}

        timeline_page_two_resp = client.get(
            f"/api/projects/{project_id}/timeline",
            params={"page": 2, "page_size": 3},
        )
        assert timeline_page_two_resp.status_code == 200
        parsed_page_two = ProjectActivityTimelineResponse.model_validate(timeline_page_two_resp.json())
        page_two_event_ids = [item.event_id for item in parsed_page_two.items]
        assert not set(page_one_event_ids).intersection(page_two_event_ids)
