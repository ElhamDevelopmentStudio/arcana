import io
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_project_ingestion_timestamp.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Project
from app.schemas import ProjectResponse


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_project_ingestion_timestamp.db")
    if db_file.exists():
        db_file.unlink()


def _sample_txt() -> str:
    return (
        "Chapter 1\n"
        '"Sunny looked around," Sunny said. The cold wind cut through the dark street.\n\n'
        "Chapter 2\n"
        "Nephis smiled. Hope rose with the warm light."
    )


def test_unit_project_response_supports_optional_ingestion_timestamp() -> None:
    payload = ProjectResponse(
        id=1,
        title="Ingestion Timestamp Unit",
        selected_mode="audiobook",
        selected_modes=["audiobook"],
        ingestion_timestamp=None,
        created_at=datetime.now(timezone.utc),
    )
    assert payload.ingestion_timestamp is None
    assert payload.selected_modes == ["audiobook"]


def test_integration_create_project_returns_null_ingestion_timestamp() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Ingestion Timestamp Integration"})
    assert project_resp.status_code == 201
    payload = project_resp.json()
    assert payload["ingestion_timestamp"] is None
    assert payload["selected_modes"] == ["audiobook"]


def test_e2e_txt_ingestion_sets_project_ingestion_timestamp() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Ingestion Timestamp E2E"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        assert project.ingestion_timestamp is not None
    finally:
        session.close()


def test_regression_project_payload_contains_ingestion_timestamp_field() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Ingestion Timestamp Regression"})
    assert project_resp.status_code == 201
    payload = project_resp.json()
    assert "ingestion_timestamp" in payload
    assert payload["ingestion_timestamp"] is None
