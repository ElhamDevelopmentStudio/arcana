import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_norm_ambiguous_fallback.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Chapter, Project
from app.services.ingestion import (
    build_ambiguous_chapter_boundary_warning,
    detect_chapters,
    detect_chapters_with_metadata,
    detect_fallback_chapters_for_ambiguous_text,
)


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_norm_ambiguous_fallback.db")
    if db_file.exists():
        db_file.unlink()


def _ambiguous_text_with_scene_breaks() -> str:
    section_one = (
        "Sunny moved through the market while tracking every motion around him. "
        "He noticed the patrol shift at the corner and waited until the lane was clear. "
        "Nothing looked unusual, but his instincts kept warning him to stay alert."
    )
    section_two = (
        "Far above, the towers reflected moonlight as cold wind crossed the district. "
        "Nephis studied the skyline and mapped every path back to the station entrance. "
        "When the signal finally arrived, she moved without a word."
    )
    return f"{section_one}\n\n***\n\n{section_two}"


def test_unit_detect_fallback_chapters_for_ambiguous_text_uses_scene_breaks() -> None:
    chapters = detect_fallback_chapters_for_ambiguous_text(_ambiguous_text_with_scene_breaks())
    assert len(chapters) == 2
    assert chapters[0][0] == "Chapter 1"
    assert chapters[1][0] == "Chapter 2"


def test_unit_detect_chapters_detects_ambiguous_boundary_fallback() -> None:
    chapters, is_ambiguous_boundaries = detect_chapters_with_metadata(_ambiguous_text_with_scene_breaks())
    assert is_ambiguous_boundaries is True
    assert len(chapters) == 2


def test_unit_build_ambiguous_chapter_boundary_warning_payload() -> None:
    warning = build_ambiguous_chapter_boundary_warning("txt", section_count=2)
    assert warning["source"] == "txt"
    assert warning["level"] == "warning"
    assert warning["type"] == "ambiguous_chapter_boundaries"
    assert warning["section_count"] == 2
    assert "fallback split produced 2" in str(warning["message"])


def test_integration_txt_ingestion_applies_ambiguous_fallback_when_headers_absent() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Norm Ambiguous Integration"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("ambiguous.txt", io.BytesIO(_ambiguous_text_with_scene_breaks().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200
        assert ingest_resp.json()["chapter_count"] == 2


def test_integration_txt_ingestion_logs_ambiguous_chapter_boundary_warning() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Norm Ambiguous Warning Integration"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("ambiguous.txt", io.BytesIO(_ambiguous_text_with_scene_breaks().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        warnings = project.ingestion_log_json.get("warnings", [])
        ambiguous_warnings = [item for item in warnings if item.get("type") == "ambiguous_chapter_boundaries"]
        assert len(ambiguous_warnings) == 1
        assert ambiguous_warnings[0]["source"] == "txt"
        assert ambiguous_warnings[0]["section_count"] == 2
    finally:
        session.close()


def test_e2e_ambiguous_fallback_persists_multiple_chapter_rows() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Norm Ambiguous E2E"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("ambiguous.txt", io.BytesIO(_ambiguous_text_with_scene_breaks().encode("utf-8")), "text/plain")},
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
        assert [row.chapter_title for row in rows] == ["Chapter 1", "Chapter 2"]
    finally:
        session.close()


def test_regression_ambiguous_fallback_does_not_split_tiny_sections() -> None:
    tiny_sections = "Tiny block\n\n***\n\nAnother tiny block"
    chapters = detect_chapters(tiny_sections)
    assert len(chapters) == 1
    assert chapters[0][0] == "Chapter 1"

    detected_chapters, is_ambiguous_boundaries = detect_chapters_with_metadata(tiny_sections)
    assert is_ambiguous_boundaries is False
    assert len(detected_chapters) == 1
