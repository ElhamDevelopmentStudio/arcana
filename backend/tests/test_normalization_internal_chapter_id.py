import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_norm_internal_chapter_id.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Chapter
from app.services.ingestion import build_internal_chapter_id


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_norm_internal_chapter_id.db")
    if db_file.exists():
        db_file.unlink()


def test_unit_build_internal_chapter_id_is_stable_and_index_based() -> None:
    assert build_internal_chapter_id(1) == "ch-0001"
    assert build_internal_chapter_id(12) == "ch-0012"
    assert build_internal_chapter_id(1234) == "ch-1234"


def test_integration_ingestion_assigns_unique_internal_ids_while_preserving_titles() -> None:
    text = (
        "Chapter 1\n"
        "First body.\n\n"
        "Chapter 1\n"
        "Second body.\n"
    )
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Norm Internal ID Integration"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("source.txt", io.BytesIO(text.encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200
        assert ingest_resp.json()["chapter_count"] == 2

    session = get_session_factory()()
    try:
        rows = (
            session.query(Chapter)
            .filter(Chapter.project_id == project_id)
            .order_by(Chapter.chapter_index.asc())
            .all()
        )
        assert [row.chapter_title for row in rows] == ["Chapter 1", "Chapter 1"]
        assert [row.chapter_internal_id for row in rows] == ["ch-0001", "ch-0002"]
    finally:
        session.close()


def test_e2e_append_assigns_next_internal_chapter_id() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Norm Internal ID E2E"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("chapter_1.txt", io.BytesIO(b"Chapter 1\nOne"), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        append_resp = client.post(
            f"/api/projects/{project_id}/ingest/append-chapter",
            files={"file": ("chapter_2.txt", io.BytesIO(b"Chapter 2\nTwo"), "text/plain")},
        )
        assert append_resp.status_code == 200
        assert append_resp.json()["chapter_count"] == 2

    session = get_session_factory()()
    try:
        rows = (
            session.query(Chapter)
            .filter(Chapter.project_id == project_id)
            .order_by(Chapter.chapter_index.asc())
            .all()
        )
        assert [row.chapter_internal_id for row in rows] == ["ch-0001", "ch-0002"]
    finally:
        session.close()


def test_regression_reingestion_reassigns_internal_ids_without_mutating_titles() -> None:
    first_text = (
        "Chapter 1\n"
        "One.\n\n"
        "Chapter 2\n"
        "Two.\n"
    )
    second_text = (
        "Prologue\n"
        "Opening.\n\n"
        "Epilogue\n"
        "Ending.\n"
    )

    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Norm Internal ID Regression"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        first_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("first.txt", io.BytesIO(first_text.encode("utf-8")), "text/plain")},
        )
        assert first_resp.status_code == 200

        second_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("second.txt", io.BytesIO(second_text.encode("utf-8")), "text/plain")},
        )
        assert second_resp.status_code == 200

    session = get_session_factory()()
    try:
        rows = (
            session.query(Chapter)
            .filter(Chapter.project_id == project_id)
            .order_by(Chapter.chapter_index.asc())
            .all()
        )
        assert [row.chapter_title for row in rows] == ["Prologue", "Epilogue"]
        assert [row.chapter_internal_id for row in rows] == ["ch-0001", "ch-0002"]
    finally:
        session.close()
