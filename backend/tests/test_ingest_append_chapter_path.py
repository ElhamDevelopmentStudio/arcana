import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_ingest_append_chapter.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Chapter
from app.services.ingestion import extract_single_append_chapter


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_ingest_append_chapter.db")
    if db_file.exists():
        db_file.unlink()


def _initial_text() -> str:
    return "Chapter 1\nInitial chapter one."


def test_unit_extract_single_append_chapter_rejects_multi_chapter_payload() -> None:
    chapters = [("Chapter 1", "One"), ("Chapter 2", "Two")]
    try:
        extract_single_append_chapter(chapters, fallback_title="Chapter X")
    except ValueError as exc:
        assert "requires exactly one non-empty chapter" in str(exc)
    else:
        raise AssertionError("Expected ValueError for multi-chapter append payload")


def test_integration_append_chapter_endpoint_increments_chapter_count() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Append Integration"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("source.txt", io.BytesIO(_initial_text().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200
        assert ingest_resp.json()["chapter_count"] == 1

        append_resp = client.post(
            f"/api/projects/{project_id}/ingest/append-chapter",
            files={"file": ("chapter_2.txt", io.BytesIO(b"Chapter 2\nAppended content"), "text/plain")},
        )
        assert append_resp.status_code == 200
        payload = append_resp.json()
        assert payload["project_id"] == project_id
        assert payload["chapter_count"] == 2
        assert isinstance(payload["warnings"], list)
        assert isinstance(payload["normalization_report"], dict)


def test_e2e_append_chapter_uses_filename_title_fallback_for_plain_text_payload() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Append E2E"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("source.txt", io.BytesIO(_initial_text().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        append_resp = client.post(
            f"/api/projects/{project_id}/ingest/append-chapter",
            files={"file": ("chapter_2_bonus.txt", io.BytesIO(b"Unheaded appended chapter body"), "text/plain")},
        )
        assert append_resp.status_code == 200

    session = get_session_factory()()
    try:
        rows = (
            session.query(Chapter)
            .filter(Chapter.project_id == project_id)
            .order_by(Chapter.chapter_index.asc())
            .all()
        )
        assert len(rows) == 2
        assert rows[1].chapter_index == 2
        assert rows[1].chapter_title == "chapter 2 bonus"
        assert rows[1].raw_text == "Unheaded appended chapter body"
    finally:
        session.close()


def test_regression_append_chapter_rejects_non_txt_file_extension() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Append Regression"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        append_resp = client.post(
            f"/api/projects/{project_id}/ingest/append-chapter",
            files={"file": ("chapter_2.md", io.BytesIO(b"## Chapter 2"), "text/markdown")},
        )
        assert append_resp.status_code == 400
        assert append_resp.json()["detail"] == "Append chapter only supports .txt files"
