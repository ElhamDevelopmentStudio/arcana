import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_norm_quote_style.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Chapter
from app.services.normalization import normalize_quotes


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()
    os.environ.pop("NORMALIZE_QUOTE_STYLE", None)

    db_file = Path("test_nipe_norm_quote_style.db")
    if db_file.exists():
        db_file.unlink()


def _set_quote_style(style: str | None) -> None:
    if style is None:
        os.environ.pop("NORMALIZE_QUOTE_STYLE", None)
    else:
        os.environ["NORMALIZE_QUOTE_STYLE"] = style
    clear_settings_cache()


def test_unit_normalize_quotes_defaults_to_straight_style() -> None:
    _set_quote_style(None)
    normalized = normalize_quotes('“Hello,” she said. ‘Wait.’')
    assert normalized == '"Hello," she said. \'Wait.\''


def test_integration_txt_ingestion_uses_curly_quote_style_when_configured() -> None:
    _set_quote_style("curly")
    text = (
        "Chapter 1\n"
        '"Hello," Sunny said. \'Wait.\' It\'s fine.\n'
    )
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Norm Quote Style Integration"})
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
        assert chapter.normalized_text == "“Hello,” Sunny said. ‘Wait.’ It’s fine."
    finally:
        session.close()


def test_e2e_markdown_ingestion_respects_curly_quote_style_for_mixed_quotes() -> None:
    _set_quote_style("curly")
    markdown_text = (
        "# Story\n\n"
        "## Chapter 1\n"
        'Nephis said, "Move." It\'s time.\n'
    )
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Norm Quote Style E2E"})
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
        assert chapter.normalized_text == "Nephis said, “Move.” It’s time."
    finally:
        session.close()


def test_regression_switching_back_to_straight_style_restores_ascii_quotes() -> None:
    _set_quote_style("straight")
    normalized = normalize_quotes('“Hello,” and ‘world’.')
    assert normalized == '"Hello," and \'world\'.'
