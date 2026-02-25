import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_norm_whitespace.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Chapter
from app.services.normalization import normalize_whitespace


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_norm_whitespace.db")
    if db_file.exists():
        db_file.unlink()


def test_unit_normalize_whitespace_collapses_unicode_and_horizontal_whitespace() -> None:
    raw = "  Sunny\t\twalked\u00A0\u202Fhome. \n\n  Nephis\u2007 waited.  "
    normalized = normalize_whitespace(raw)
    assert normalized == "Sunny walked home.\n\nNephis waited."


def test_integration_txt_ingestion_stores_consistently_normalized_whitespace() -> None:
    text = (
        "Chapter 1\n"
        "Sunny\t\twalked\u00A0home.   \n\n"
        "Nephis    waited.\n"
    )
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Norm Whitespace Integration"})
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
        assert chapter.normalized_text == "Sunny walked home.\n\nNephis waited."
    finally:
        session.close()


def test_e2e_markdown_ingestion_applies_same_whitespace_normalization() -> None:
    markdown_text = (
        "# Story\n\n"
        "## Chapter 1\n"
        "Line with\t\t tabs.\n\n\n\n"
        "Line with   extra spaces.\n"
    )
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Norm Whitespace E2E"})
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
        assert chapter.normalized_text == "Line with tabs.\n\nLine with extra spaces."
    finally:
        session.close()


def test_regression_normalize_whitespace_keeps_two_newline_paragraph_breaks() -> None:
    raw = "First paragraph.\n\n\n\nSecond paragraph."
    normalized = normalize_whitespace(raw)
    assert normalized == "First paragraph.\n\nSecond paragraph."
