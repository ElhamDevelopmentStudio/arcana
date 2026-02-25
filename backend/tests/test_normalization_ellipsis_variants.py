import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_norm_ellipsis.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Chapter
from app.services.normalization import normalize_ellipsis_variants


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_norm_ellipsis.db")
    if db_file.exists():
        db_file.unlink()


def test_unit_normalize_ellipsis_variants_unifies_ellipsis_forms() -> None:
    raw = "Wait… what . . . now.... and really……"
    normalized = normalize_ellipsis_variants(raw)
    assert normalized == "Wait... what ... now... and really..."


def test_integration_txt_ingestion_normalizes_ellipsis_variants_in_normalized_text() -> None:
    text = (
        "Chapter 1\n"
        "Wait… what . . . now....\n"
    )
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Norm Ellipsis Integration"})
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
        assert chapter.normalized_text == "Wait... what ... now..."
    finally:
        session.close()


def test_e2e_markdown_ingestion_normalizes_unicode_ellipsis() -> None:
    markdown_text = (
        "# Story\n\n"
        "## Chapter 1\n"
        "He paused…… then continued…\n"
    )
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Norm Ellipsis E2E"})
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
        assert chapter.normalized_text == "He paused... then continued..."
    finally:
        session.close()


def test_regression_decimal_numbers_are_not_modified_by_ellipsis_normalization() -> None:
    raw = "The value is 3.1415 and stable."
    normalized = normalize_ellipsis_variants(raw)
    assert normalized == raw
