import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_ingest_chapter_directory.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Chapter
from app.services.ingestion import chapter_filename_sort_key


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_ingest_chapter_directory.db")
    if db_file.exists():
        db_file.unlink()


def test_unit_chapter_filename_sort_key_uses_natural_order() -> None:
    names = ["chapter_10.txt", "chapter_2.txt", "chapter_1.txt"]
    assert sorted(names, key=chapter_filename_sort_key) == ["chapter_1.txt", "chapter_2.txt", "chapter_10.txt"]


def test_integration_ingest_chapter_directory_endpoint_accepts_txt_files() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Directory Ingest Integration"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        files = [
            ("files", ("chapter_2.txt", io.BytesIO(b"Second chapter content"), "text/plain")),
            ("files", ("chapter_1.txt", io.BytesIO(b"First chapter content"), "text/plain")),
        ]
        ingest_resp = client.post(f"/api/projects/{project_id}/ingest/chapters-dir", files=files)
        assert ingest_resp.status_code == 200
        assert ingest_resp.json() == {"project_id": project_id, "chapter_count": 2}


def test_e2e_chapter_directory_ingestion_persists_ordered_rows() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Directory Ingest E2E"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        files = [
            ("files", ("chapter_3.txt", io.BytesIO(b"Third chapter content"), "text/plain")),
            ("files", ("chapter_1.txt", io.BytesIO(b"First chapter content"), "text/plain")),
            ("files", ("chapter_2.txt", io.BytesIO(b"Second chapter content"), "text/plain")),
        ]
        ingest_resp = client.post(f"/api/projects/{project_id}/ingest/chapters-dir", files=files)
        assert ingest_resp.status_code == 200

    session = get_session_factory()()
    try:
        rows = (
            session.query(Chapter)
            .filter(Chapter.project_id == project_id)
            .order_by(Chapter.chapter_index.asc())
            .all()
        )
        assert [row.chapter_title for row in rows] == ["chapter 1", "chapter 2", "chapter 3"]
        assert [row.raw_text for row in rows] == [
            "First chapter content",
            "Second chapter content",
            "Third chapter content",
        ]
    finally:
        session.close()


def test_regression_chapter_directory_rejects_non_txt_files() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Directory Ingest Regression"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        files = [
            ("files", ("chapter_1.md", io.BytesIO(b"Markdown content"), "text/markdown")),
        ]
        ingest_resp = client.post(f"/api/projects/{project_id}/ingest/chapters-dir", files=files)
        assert ingest_resp.status_code == 400
        assert ingest_resp.json()["detail"] == "Chapter directory only supports .txt files"
