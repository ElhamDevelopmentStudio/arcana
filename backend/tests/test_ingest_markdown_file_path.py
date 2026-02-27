import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_ingest_markdown_file.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Chapter
from app.services.ingestion import normalize_markdown_for_ingestion


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_ingest_markdown_file.db")
    if db_file.exists():
        db_file.unlink()


def _sample_markdown() -> str:
    return (
        "# Shadow Slave\n\n"
        "## Chapter 1\n"
        "Sunny looked around.\n\n"
        "## Chapter 2\n"
        "Nephis smiled.\n"
    )


def test_unit_normalize_markdown_for_ingestion_strips_basic_md_syntax() -> None:
    raw = "# Title\n\n**Bold** [link](https://example.com)\n"
    normalized = normalize_markdown_for_ingestion(raw)
    assert "Title" in normalized
    assert "Bold" in normalized
    assert "link" in normalized
    assert "#" not in normalized


def test_integration_ingest_markdown_endpoint_accepts_md_file() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Markdown Ingest Integration"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/markdown",
            files={"file": ("sample.md", io.BytesIO(_sample_markdown().encode("utf-8")), "text/markdown")},
        )
        assert ingest_resp.status_code == 200
        payload = ingest_resp.json()
        assert payload["project_id"] == project_id
        assert payload["chapter_count"] == 2
        assert isinstance(payload["warnings"], list)
        assert isinstance(payload["normalization_report"], dict)


def test_e2e_markdown_ingestion_persists_chapter_rows() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Markdown Ingest E2E"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/markdown",
            files={"file": ("novel.markdown", io.BytesIO(_sample_markdown().encode("utf-8")), "text/markdown")},
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
        assert len(rows) == 2
        assert rows[0].chapter_title.lower().startswith("chapter 1")
        assert rows[1].chapter_title.lower().startswith("chapter 2")
    finally:
        session.close()


def test_regression_ingest_markdown_rejects_non_markdown_extension() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Markdown Ingest Regression"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/markdown",
            files={"file": ("sample.txt", io.BytesIO(_sample_markdown().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 400
        assert ingest_resp.json()["detail"] == "Only .md or .markdown files are supported"
