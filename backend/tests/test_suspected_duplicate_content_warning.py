import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_duplicate_content_warning.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Project
from app.services.ingestion import (
    build_suspected_duplicate_content_warnings,
    detect_suspected_duplicate_content,
)


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_duplicate_content_warning.db")
    if db_file.exists():
        db_file.unlink()


def test_unit_detect_suspected_duplicate_content_detects_repeated_blocks() -> None:
    chapters = [
        ("Chapter 1", "The lantern drifted above the marsh as fog swallowed the bridge at dawn. " * 4),
        ("Chapter 2", "The lantern drifted above the marsh as fog swallowed the bridge at dawn. " * 4),
    ]

    suspicious = detect_suspected_duplicate_content(chapters, minimum_chars=120, similarity_threshold=0.95)
    assert len(suspected := suspicious) == 1
    assert suspected[0]["chapter_index_a"] == 1
    assert suspected[0]["chapter_index_b"] == 2
    assert suspected[0]["similarity"] == 1.0


def test_unit_build_suspected_duplicate_content_warnings_payload() -> None:
    suspicious = [
        {
            "chapter_index_a": 1,
            "chapter_index_b": 2,
            "chapter_title_a": "Chapter 1",
            "chapter_title_b": "Chapter 2",
            "similarity": 0.98,
        }
    ]
    warnings = build_suspected_duplicate_content_warnings("txt", suspicious)

    assert len(warnings) == 1
    warning = warnings[0]
    assert warning["source"] == "txt"
    assert warning["type"] == "suspected_duplicate_content"
    assert warning["level"] == "warning"
    assert warning["chapter_indices"] == [1, 2]
    assert warning["similarity"] == 0.98


def test_integration_txt_ingestion_logs_suspected_duplicate_content_warning() -> None:
    long_line = (
        "The lantern drifted above the marsh as fog swallowed the bridge at dawn. "
        "Its light shook once, then held steady as the bells rang twice across the river. "
        "Every stone seemed to remember every footstep that had passed this way for years. "
    ) * 3
    text = f"Chapter 1\n{long_line}\n\nChapter 2\n{long_line}\n"

    with TestClient(app) as client:
        project_resp = client.post(
            "/api/projects",
            json={"title": "Suspected Duplicate Content Integration"},
        )
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("source.txt", io.BytesIO(text.encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        warnings = project.ingestion_log_json.get("warnings", [])
        duplicate_warnings = [
            item
            for item in warnings
            if item.get("type") == "suspected_duplicate_content" and item.get("source") == "txt"
        ]
        assert duplicate_warnings
        assert duplicate_warnings[0]["similarity"] >= 0.95
    finally:
        session.close()
