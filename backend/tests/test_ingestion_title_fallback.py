import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_ingestion_title_fallback.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Project
from app.services.ingestion import DEFAULT_INGESTION_TITLE, detect_title_with_fallback


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_ingestion_title_fallback.db")
    if db_file.exists():
        db_file.unlink()


def test_unit_detect_title_uses_first_valid_non_chapter_line() -> None:
    raw_text = (
        "\n"
        "Shadow Slave\n"
        "Chapter 1\n"
        "A frail-looking young man sat on a rusty bench."
    )
    assert detect_title_with_fallback(raw_text, filename="ignored.txt") == "Shadow Slave"


def test_integration_ingestion_updates_placeholder_title_from_text() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Untitled Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        source = (
            "Shadow Slave\n\n"
            "Chapter 1\n"
            "A frail-looking young man sat on a rusty bench."
        )
        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("shadow-slave.txt", io.BytesIO(source.encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        assert project.title == "Shadow Slave"
    finally:
        session.close()


def test_e2e_ingestion_uses_filename_fallback_when_no_detectable_title() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Untitled Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        source = (
            "\n\n"
            "Chapter 1\n"
            "The first line is chapter metadata and should be ignored."
        )
        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("novel_extra_chapter_0.txt", io.BytesIO(source.encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        assert project.title == "novel extra chapter 0"
    finally:
        session.close()


def test_regression_title_fallback_default_constant() -> None:
    assert detect_title_with_fallback("\n\n", filename=None) == DEFAULT_INGESTION_TITLE
