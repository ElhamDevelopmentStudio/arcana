import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_norm_file_boundaries.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Chapter
from app.services.ingestion import detect_chapters_from_file_boundaries


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_norm_file_boundaries.db")
    if db_file.exists():
        db_file.unlink()


def test_unit_detect_chapters_from_file_boundaries_maps_filename_to_chapter_title() -> None:
    chapters = detect_chapters_from_file_boundaries(
        [
            ("chapter_1.txt", "First chapter body"),
            ("chapter_2.txt", "Second chapter body"),
        ]
    )
    assert chapters == [
        ("chapter 1", "First chapter body"),
        ("chapter 2", "Second chapter body"),
    ]


def test_integration_chapter_directory_ingestion_uses_file_boundary_detection() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Norm File Boundary Integration"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/chapters-dir",
            files=[
                ("files", ("chapter_2.txt", io.BytesIO(b"Second chapter"), "text/plain")),
                ("files", ("chapter_1.txt", io.BytesIO(b"First chapter"), "text/plain")),
            ],
        )
        assert ingest_resp.status_code == 200
        assert ingest_resp.json()["chapter_count"] == 2


def test_e2e_file_boundary_ingestion_persists_ordered_chapter_rows() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Norm File Boundary E2E"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/chapters-dir",
            files=[
                ("files", ("chapter_3.txt", io.BytesIO(b"Third chapter"), "text/plain")),
                ("files", ("chapter_1.txt", io.BytesIO(b"First chapter"), "text/plain")),
                ("files", ("chapter_2.txt", io.BytesIO(b"Second chapter"), "text/plain")),
            ],
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
        assert [row.chapter_title for row in rows] == ["chapter 1", "chapter 2", "chapter 3"]
        assert [row.raw_text for row in rows] == ["First chapter", "Second chapter", "Third chapter"]
    finally:
        session.close()


def test_regression_file_boundary_detector_ignores_empty_files_and_errors_when_all_empty() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Norm File Boundary Regression"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        single_non_empty_resp = client.post(
            f"/api/projects/{project_id}/ingest/chapters-dir",
            files=[
                ("files", ("chapter_1.txt", io.BytesIO(b""), "text/plain")),
                ("files", ("chapter_2.txt", io.BytesIO(b"Only chapter"), "text/plain")),
            ],
        )
        assert single_non_empty_resp.status_code == 200
        assert single_non_empty_resp.json()["chapter_count"] == 1

        all_empty_resp = client.post(
            f"/api/projects/{project_id}/ingest/chapters-dir",
            files=[
                ("files", ("chapter_1.txt", io.BytesIO(b"   "), "text/plain")),
                ("files", ("chapter_2.txt", io.BytesIO(b"\n\n"), "text/plain")),
            ],
        )
        assert all_empty_resp.status_code == 400
        assert all_empty_resp.headers["x-nipe-error-type"] == "missing_chapters"
