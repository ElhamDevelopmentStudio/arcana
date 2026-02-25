import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_norm_duplicate_titles.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Project
from app.services.ingestion import detect_duplicate_chapter_titles


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_norm_duplicate_titles.db")
    if db_file.exists():
        db_file.unlink()


def test_unit_detect_duplicate_chapter_titles_detects_case_insensitive_duplicates() -> None:
    duplicates = detect_duplicate_chapter_titles(
        [
            ("Chapter 1", "A"),
            ("chapter 1", "B"),
            ("Chapter 2", "C"),
        ]
    )
    assert len(duplicates) == 1
    assert duplicates[0]["title"] == "Chapter 1"
    assert duplicates[0]["occurrences"] == [1, 2]


def test_integration_txt_ingestion_logs_duplicate_title_warnings() -> None:
    text = (
        "Chapter 1\n"
        "First body.\n\n"
        "Chapter 1\n"
        "Second body.\n"
    )
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Norm Duplicate Title Integration"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("source.txt", io.BytesIO(text.encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        warnings = project.ingestion_log_json.get("warnings", [])
        assert any(item.get("type") == "duplicate_chapter_title" for item in warnings)
    finally:
        session.close()


def test_e2e_append_chapter_logs_duplicate_title_warning_without_blocking() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Norm Duplicate Title E2E"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("chapter_1.txt", io.BytesIO(b"Chapter 1\nOne"), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        append_resp = client.post(
            f"/api/projects/{project_id}/ingest/append-chapter",
            files={"file": ("chapter_1.txt", io.BytesIO(b"Completely different text"), "text/plain")},
        )
        assert append_resp.status_code == 200
        assert append_resp.json()["chapter_count"] == 2

    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        warnings = project.ingestion_log_json.get("warnings", [])
        duplicates = [item for item in warnings if item.get("type") == "duplicate_chapter_title"]
        assert duplicates
    finally:
        session.close()


def test_regression_unique_titles_do_not_emit_duplicate_title_warning() -> None:
    text = (
        "Chapter 1\n"
        "First body.\n\n"
        "Chapter 2\n"
        "Second body.\n"
    )
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Norm Duplicate Title Regression"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("source.txt", io.BytesIO(text.encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        warnings = project.ingestion_log_json.get("warnings", [])
        assert not any(item.get("type") == "duplicate_chapter_title" for item in warnings)
    finally:
        session.close()
