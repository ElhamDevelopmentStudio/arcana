import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_project_metadata_update_endpoint.db"

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
    db_file = Path("test_nipe_project_metadata_update_endpoint.db")
    if db_file.exists():
        db_file.unlink()


def _sample_txt() -> str:
    return (
        "Chapter 1\n"
        '"Sunny looked around," Sunny said. The cold wind cut through the dark street.\n\n'
        "Chapter 2\n"
        "Nephis smiled. Hope rose with the warm light."
    )


def test_integration_update_project_metadata_title_description_tags() -> None:
    with TestClient(app) as client:
        create_resp = client.post("/api/projects/drafts", json={"title": "Metadata Project"})
        assert create_resp.status_code == 201
        project_id = create_resp.json()["id"]

        update_resp = client.patch(
            f"/api/projects/{project_id}/metadata",
            json={
                "title": "  Metadata Project Updated  ",
                "description": "  Draft metadata details.  ",
                "tags": [" Arc ", "Research", "arc"],
            },
        )
        assert update_resp.status_code == 200
        payload = update_resp.json()
        assert payload["project_id"] == project_id
        assert payload["title"] == "Metadata Project Updated"
        assert payload["description"] == "Draft metadata details."
        assert payload["tags"] == ["Arc", "Research"]

    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        assert project.title == "Metadata Project Updated"
        assert project.description == "Draft metadata details."
        assert project.tags == ["Arc", "Research"]
    finally:
        session.close()


def test_integration_update_project_metadata_rejects_empty_payload() -> None:
    with TestClient(app) as client:
        create_resp = client.post("/api/projects/drafts", json={"title": "Metadata Empty Payload"})
        assert create_resp.status_code == 201
        project_id = create_resp.json()["id"]

        update_resp = client.patch(f"/api/projects/{project_id}/metadata", json={})
        assert update_resp.status_code == 422


def test_e2e_update_project_metadata_does_not_reingest_chapters() -> None:
    with TestClient(app) as client:
        create_resp = client.post("/api/projects/drafts", json={"title": "Metadata No Reingest"})
        assert create_resp.status_code == 201
        project_id = create_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200
        assert ingest_resp.json()["chapter_count"] == 2

    session = get_session_factory()()
    try:
        before_project = session.query(Project).filter(Project.id == project_id).one()
        before_ingestion_timestamp = before_project.ingestion_timestamp
        before_chapter_count = session.query(Chapter).filter(Chapter.project_id == project_id).count()
    finally:
        session.close()

    with TestClient(app) as client:
        update_resp = client.patch(
            f"/api/projects/{project_id}/metadata",
            json={"description": "Revised summary", "tags": ["analysis"]},
        )
        assert update_resp.status_code == 200

    session = get_session_factory()()
    try:
        after_project = session.query(Project).filter(Project.id == project_id).one()
        after_chapter_count = session.query(Chapter).filter(Chapter.project_id == project_id).count()
        assert after_project.description == "Revised summary"
        assert after_project.tags == ["analysis"]
        assert before_ingestion_timestamp == after_project.ingestion_timestamp
        assert before_chapter_count == after_chapter_count
    finally:
        session.close()
