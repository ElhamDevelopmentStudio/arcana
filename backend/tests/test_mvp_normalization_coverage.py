import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_mvp_normalization_coverage.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Chapter, Project


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_mvp_normalization_coverage.db")
    if db_file.exists():
        db_file.unlink()


def test_acceptance_normalization_includes_chapters_dedupe_quote_repair_and_reports() -> None:
    source_text = (
        "Chapter 1\n"
        'He said "Hold the east gate.\n\n'
        "Chapter 1\n"
        'She replied “Move now.\n'
    )

    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "MVP Normalization Coverage"})
        assert project_resp.status_code == 201
        project_id = int(project_resp.json()["id"])

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("source.txt", io.BytesIO(source_text.encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200
        assert int(ingest_resp.json()["chapter_count"]) == 2

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"mode": "audiobook", "llm_enabled": False},
        )
        assert run_resp.status_code == 200
        run_id = int(run_resp.json()["run_id"])

        run_detail_resp = client.get(f"/api/projects/{project_id}/runs/{run_id}")
        assert run_detail_resp.status_code == 200
        normalization_report = run_detail_resp.json()["config"]["normalization_report"]
        assert normalization_report["source"] == "txt"
        assert int(normalization_report["counts"]["chapters_detected"]) == 2
        assert int(normalization_report["counts"]["suspected_duplicates"]) >= 1
        assert int(normalization_report["counts"]["quote_repair_count"]) >= 1
        assert normalization_report["lossy_transform_flags"]["quote_repair_applied"] is True

    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        dedup_actions = project.ingestion_log_json.get("dedup_actions", [])
        warnings = project.ingestion_log_json.get("warnings", [])
        assert any(action.get("type") == "chapter_title_dedup_action" for action in dedup_actions)
        assert any(warning.get("type") == "duplicate_chapter_title" for warning in warnings)

        chapters = (
            session.query(Chapter)
            .filter(Chapter.project_id == project_id)
            .order_by(Chapter.chapter_index.asc())
            .all()
        )
        assert len(chapters) == 2
        assert all(chapter.chapter_title.strip().lower() == "chapter 1" for chapter in chapters)
        assert all(chapter.normalized_text.count('"') % 2 == 0 for chapter in chapters)
    finally:
        session.close()
