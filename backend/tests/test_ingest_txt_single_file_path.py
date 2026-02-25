import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_ingest_txt_single_file.db"

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

    db_file = Path("test_nipe_ingest_txt_single_file.db")
    if db_file.exists():
        db_file.unlink()


def _single_file_text() -> str:
    return (
        "Shadow Slave\n"
        "Chapter 1\n"
        '"Sunny looked around," Sunny said.\n\n'
        "Chapter 2\n"
        "Nephis smiled."
    )


def test_unit_detect_chapters_for_single_txt_input() -> None:
    chapters = detect_chapters(_single_file_text())
    assert len(chapters) == 2
    assert chapters[0][0].lower().startswith("chapter 1")
    assert "Sunny looked around" in chapters[0][1]


def test_integration_ingest_txt_endpoint_accepts_single_file_input() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "TXT Single File Integration"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", io.BytesIO(_single_file_text().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200
        assert ingest_resp.json() == {"project_id": project_id, "chapter_count": 2}


def test_e2e_ingest_txt_single_file_persists_chapter_rows() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "TXT Single File E2E"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("single-file.txt", io.BytesIO(_single_file_text().encode("utf-8")), "text/plain")},
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


def test_regression_ingest_txt_rejects_non_txt_extension() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "TXT Single File Regression"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.md", io.BytesIO(_single_file_text().encode("utf-8")), "text/markdown")},
        )
        assert ingest_resp.status_code == 400
        assert ingest_resp.json()["detail"] == "Only .txt files are supported"
