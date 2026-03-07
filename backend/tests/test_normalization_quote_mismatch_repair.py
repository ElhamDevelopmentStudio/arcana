import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_norm_quote_mismatch.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Chapter, Project
from app.services.normalization import normalize_text_with_warnings, repair_quote_mismatch


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_norm_quote_mismatch.db")
    if db_file.exists():
        db_file.unlink()


def test_unit_repair_quote_mismatch_appends_missing_close_quote() -> None:
    text = 'He said "Hello and waited.'
    repaired = repair_quote_mismatch(text)
    assert repaired == 'He said "Hello and waited."'


def test_unit_repair_quote_mismatch_prepends_missing_open_quote() -> None:
    text = 'He muttered And then he left".'
    repaired = repair_quote_mismatch(text)
    assert repaired == '"He muttered And then he left".'


def test_unit_repair_ignores_apostrophes_in_word_forms() -> None:
    text = "Sunny's courage was tested."
    repaired = repair_quote_mismatch(text)
    assert repaired == "Sunny's courage was tested."


def test_unit_repair_quote_mismatch_appends_low_confidence_warning() -> None:
    repaired, warnings = normalize_text_with_warnings('He said "Hello and waited.', source="txt")
    assert repaired == 'He said "Hello and waited."'
    assert len(warnings) == 1
    warning = warnings[0]
    assert warning["type"] == "quote_repair_confidence_low"
    assert warning["source"] == "txt"
    assert warning["level"] == "warning"
    assert warning["action_count"] == 1


def test_unit_repair_quote_mismatch_without_warning_when_confident() -> None:
    repaired, warnings = normalize_text_with_warnings('He muttered "All is quiet".', source="txt")
    assert repaired == 'He muttered "All is quiet".'
    assert warnings == []


def test_integration_txt_ingestion_normalizes_quote_mismatch_in_normalized_text() -> None:
    text = (
        'Chapter 1\n'
        '"Hello, Sunny said.\n'
        'He added, "Watch the light.\n'
        'The night settled.\n'
    )
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Norm Quote Mismatch Integration"})
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
        assert (
            chapter.normalized_text
            == '"Hello, Sunny said."\nHe added, "Watch the light."\nThe night settled.'
        )
    finally:
        session.close()


def test_integration_txt_ingestion_logs_uncertain_quote_repair_warning() -> None:
    text = 'Chapter 1\nHe said "Take cover on the east side.'
    with TestClient(app) as client:
        project_resp = client.post(
            "/api/projects",
            json={"title": "Norm Quote Repair Warning Integration"},
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
        assert any(item.get("type") == "quote_repair_confidence_low" for item in warnings)
        assert all(item["source"] == "txt" for item in warnings if item.get("type") == "quote_repair_confidence_low")
    finally:
        session.close()
