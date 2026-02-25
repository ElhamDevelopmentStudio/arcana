import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_ingestion_affected_range.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Project
from app.services.ingestion import calculate_delta_affected_range


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_ingestion_affected_range.db")
    if db_file.exists():
        db_file.unlink()


def test_unit_calculate_delta_affected_range_handles_lookback() -> None:
    affected = calculate_delta_affected_range(
        changed_chapter_indices=[5],
        total_chapter_count=8,
        context_lookback=2,
    )
    assert affected == {"start_chapter_index": 3, "end_chapter_index": 5}


def test_integration_append_chapter_persists_affected_range_in_project_log() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Affected Range Integration"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("source.txt", io.BytesIO(b"Chapter 1\nOne"), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        append_resp = client.post(
            f"/api/projects/{project_id}/ingest/append-chapter",
            files={"file": ("chapter_2.txt", io.BytesIO(b"Chapter 2\nTwo"), "text/plain")},
        )
        assert append_resp.status_code == 200

    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        assert project.ingestion_log_json["affected_range"] == {
            "start_chapter_index": 2,
            "end_chapter_index": 2,
        }
    finally:
        session.close()


def test_e2e_affected_range_tracks_latest_appended_chapter_index() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Affected Range E2E"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("source.txt", io.BytesIO(b"Chapter 1\nOne\n\nChapter 2\nTwo"), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        append_resp = client.post(
            f"/api/projects/{project_id}/ingest/append-chapter",
            files={"file": ("chapter_3.txt", io.BytesIO(b"Chapter 3\nThree"), "text/plain")},
        )
        assert append_resp.status_code == 200
        assert append_resp.json()["chapter_count"] == 3

    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        assert project.ingestion_log_json["affected_range"] == {
            "start_chapter_index": 3,
            "end_chapter_index": 3,
        }
    finally:
        session.close()


def test_regression_calculate_delta_affected_range_ignores_invalid_indices() -> None:
    affected = calculate_delta_affected_range(
        changed_chapter_indices=[0, -1],
        total_chapter_count=3,
        context_lookback=1,
    )
    assert affected is None
