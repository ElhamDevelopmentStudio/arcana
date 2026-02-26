import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_project_draft_creation_endpoint.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Chapter, Project
from app.services.project_lifecycle import PROJECT_LIFECYCLE_DRAFT


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()
    db_file = Path("test_nipe_project_draft_creation_endpoint.db")
    if db_file.exists():
        db_file.unlink()


def test_integration_create_project_draft_returns_project_payload() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/projects/drafts",
            json={"title": "Draft Endpoint Integration", "do_not_store_source_text": True},
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["title"] == "Draft Endpoint Integration"
    assert payload["selected_mode"] == "audiobook"
    assert payload["selected_modes"] == ["audiobook"]
    assert payload["do_not_store_source_text"] is True
    assert payload["configuration_snapshot_id"] == f"project-{payload['id']}-config-initial"
    assert payload["ingestion_timestamp"] is None


def test_e2e_create_project_draft_persists_draft_state_without_chapters() -> None:
    with TestClient(app) as client:
        response = client.post("/api/projects/drafts", json={"title": "Draft Endpoint E2E"})
    assert response.status_code == 201
    project_id = response.json()["id"]

    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        chapter_count = session.query(Chapter).filter(Chapter.project_id == project_id).count()
        assert project.lifecycle_state == PROJECT_LIFECYCLE_DRAFT
        assert project.ingestion_timestamp is None
        assert chapter_count == 0
    finally:
        session.close()
