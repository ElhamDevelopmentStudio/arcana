import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_norm_line_breaks.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Chapter
from app.services.normalization import normalize_line_breaks_and_paragraph_separators


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_norm_line_breaks.db")
    if db_file.exists():
        db_file.unlink()


def test_unit_normalize_line_breaks_and_paragraph_separators_standardizes_breaks() -> None:
    raw = "Line 1\r\nLine 2\rLine 3\u2028Line 4\u2029Line 5\u0085Line 6"
    normalized = normalize_line_breaks_and_paragraph_separators(raw)
    assert normalized == "Line 1\nLine 2\nLine 3\nLine 4\nLine 5\nLine 6"


def test_integration_txt_ingestion_converts_separator_lines_to_paragraph_break() -> None:
    text = (
        "Chapter 1\r\n"
        "First paragraph.\r\n"
        "***\r\n"
        "Second paragraph.\r\n"
    )
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Norm Line Break Integration"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("source.txt", io.BytesIO(text.encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

    session = get_session_factory()()
    try:
        chapter = session.query(Chapter).filter(Chapter.project_id == project_id).one()
        assert chapter.normalized_text == "First paragraph.\n\nSecond paragraph."
    finally:
        session.close()


def test_e2e_markdown_ingestion_handles_unicode_line_separators() -> None:
    markdown_text = (
        "# Story\n\n"
        "## Chapter 1\n"
        "Line A\u2028Line B\u2029Line C\n"
    )
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Norm Line Break E2E"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/markdown",
            files={"file": ("source.md", io.BytesIO(markdown_text.encode("utf-8")), "text/markdown")},
        )
        assert ingest_resp.status_code == 200

    session = get_session_factory()()
    try:
        chapter = session.query(Chapter).filter(Chapter.project_id == project_id).one()
        assert chapter.normalized_text == "Line A\nLine B\nLine C"
    finally:
        session.close()


def test_regression_plain_newlines_remain_stable_when_no_separators_present() -> None:
    raw = "Alpha\nBeta\nGamma"
    normalized = normalize_line_breaks_and_paragraph_separators(raw)
    assert normalized == raw
