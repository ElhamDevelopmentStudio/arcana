import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_ingestion_warning_logs.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Project
from app.services.ingestion import build_encoding_warning


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_ingestion_warning_logs.db")
    if db_file.exists():
        db_file.unlink()


def test_unit_build_encoding_warning_only_on_non_utf8_or_low_confidence() -> None:
    assert build_encoding_warning("txt", "utf-8", 0.95) is None

    warning = build_encoding_warning("txt", "cp1252", 0.4)
    assert warning is not None
    assert warning["source"] == "txt"
    assert warning["encoding"] == "cp1252"
    assert warning["level"] == "warning"


def test_integration_txt_ingestion_persists_encoding_warning_on_project_log() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Encoding Warning Integration"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        cp1252_text = "Chapter 1\nCafe café scene."
        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("cp1252.txt", io.BytesIO(cp1252_text.encode("cp1252")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        warnings = project.ingestion_log_json.get("warnings", [])
        assert len(warnings) == 1
        assert warnings[0]["source"] == "txt"
        assert warnings[0]["encoding"] == "cp1252"
    finally:
        session.close()


def test_e2e_run_detail_carries_project_ingestion_warnings() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Encoding Warning E2E"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        files = [
            ("files", ("chapter_1.txt", io.BytesIO("Début".encode("utf-8")), "text/plain")),
            ("files", ("chapter_2.txt", io.BytesIO("café".encode("cp1252")), "text/plain")),
        ]
        ingest_resp = client.post(f"/api/projects/{project_id}/ingest/chapters-dir", files=files)
        assert ingest_resp.status_code == 200

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"mode": "audiobook", "llm_enabled": False},
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        detail_resp = client.get(f"/api/projects/{project_id}/runs/{run_id}")
        assert detail_resp.status_code == 200
        warnings = detail_resp.json()["config"]["ingestion_warnings"]
        assert warnings
        assert any(str(item["source"]).startswith("chapters-dir:") for item in warnings)


def test_regression_utf8_ingestion_keeps_warning_list_empty() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Encoding Warning Regression"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        utf8_text = "Chapter 1\nPlain utf8 content."
        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("utf8.txt", io.BytesIO(utf8_text.encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        warnings = project.ingestion_log_json.get("warnings", [])
        assert warnings == []
    finally:
        session.close()
