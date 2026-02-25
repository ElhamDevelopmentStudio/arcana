import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_norm_header_patterns.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Chapter
from app.services.ingestion import detect_chapters


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_norm_header_patterns.db")
    if db_file.exists():
        db_file.unlink()


def test_unit_detect_chapters_matches_multiple_header_patterns() -> None:
    raw_text = (
        "Prologue\n"
        "Dark winds howled.\n\n"
        "Chapter IV\n"
        "Sunny stepped forward.\n\n"
        "Epilogue\n"
        "Silence returned."
    )
    chapters = detect_chapters(raw_text)
    assert [title for title, _ in chapters] == ["Prologue", "Chapter IV", "Epilogue"]


def test_integration_txt_ingestion_supports_roman_and_textual_header_patterns() -> None:
    text = (
        "Chapter One\n"
        "Opening.\n\n"
        "Chapter II\n"
        "Continuation."
    )
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Norm Header Pattern Integration"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("source.txt", io.BytesIO(text.encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200
        assert ingest_resp.json()["chapter_count"] == 2


def test_e2e_header_pattern_detection_persists_expected_titles() -> None:
    text = (
        "Interlude I\n"
        "Pause in conflict.\n\n"
        "Chapter 2\n"
        "Action resumes."
    )
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Norm Header Pattern E2E"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("source.txt", io.BytesIO(text.encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

    session = get_session_factory()()
    try:
        rows = (
            session.query(Chapter)
            .filter(Chapter.project_id == project_id)
            .order_by(Chapter.chapter_index.asc())
            .all()
        )
        assert [row.chapter_title for row in rows] == ["Interlude I", "Chapter 2"]
    finally:
        session.close()


def test_regression_plain_text_without_header_patterns_stays_single_chapter() -> None:
    text = "Sunny walked through the market.\nNo explicit chapter headers exist in this text."
    chapters = detect_chapters(text)
    assert len(chapters) == 1
    assert chapters[0][0] == "Chapter 1"
