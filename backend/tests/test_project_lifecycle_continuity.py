import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_project_lifecycle_continuity.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Chapter, Project
from app.services.project_lifecycle import PROJECT_LIFECYCLE_INGESTED


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()
    db_file = Path("test_nipe_project_lifecycle_continuity.db")
    if db_file.exists():
        db_file.unlink()


def _sample_txt() -> str:
    return (
        "Chapter 1\n"
        '"Sunny looked around," Sunny said. The cold wind cut through the dark street.\n\n'
        "Chapter 2\n"
        "Nephis smiled. Hope rose with the warm light."
    )


def _read_project_snapshot(project_id: int) -> tuple[Project, int]:
    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        chapter_count = session.query(Chapter).filter(Chapter.project_id == project_id).count()
        return project, chapter_count
    finally:
        session.close()


def test_integration_lifecycle_continuity_for_draft_ingest_metadata_edit() -> None:
    with TestClient(app) as client:
        draft_resp = client.post("/api/projects/drafts", json={"title": "Lifecycle Continuity Integration"})
        assert draft_resp.status_code == 201
        project_id = draft_resp.json()["id"]

        source_resp = client.post(
            f"/api/projects/{project_id}/ingest/source",
            json={"source": "txt", "source_filename": "continuity.txt"},
        )
        assert source_resp.status_code == 200
        assert source_resp.json()["project_id"] == project_id

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("continuity.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200
        assert ingest_resp.json()["project_id"] == project_id
        assert ingest_resp.json()["chapter_count"] == 2

        metadata_resp = client.patch(
            f"/api/projects/{project_id}/metadata",
            json={
                "title": "Lifecycle Continuity Updated",
                "description": "Updated metadata after ingestion",
                "tags": ["continuity", "ingested"],
            },
        )
        assert metadata_resp.status_code == 200
        metadata_payload = metadata_resp.json()
        assert metadata_payload["project_id"] == project_id
        assert metadata_payload["title"] == "Lifecycle Continuity Updated"
        assert metadata_payload["description"] == "Updated metadata after ingestion"
        assert metadata_payload["tags"] == ["continuity", "ingested"]

    project, chapter_count = _read_project_snapshot(project_id)
    assert project.id == project_id
    assert project.lifecycle_state == PROJECT_LIFECYCLE_INGESTED
    assert project.ingestion_timestamp is not None
    assert project.title == "Lifecycle Continuity Updated"
    assert project.description == "Updated metadata after ingestion"
    assert project.tags == ["continuity", "ingested"]
    assert chapter_count == 2
    assert project.ingestion_log_json.get("first_source") == "txt"
    assert project.ingestion_log_json.get("source") == "txt"


def test_e2e_lifecycle_continuity_keeps_chapter_rows_after_multiple_metadata_edits() -> None:
    with TestClient(app) as client:
        draft_resp = client.post("/api/projects/drafts", json={"title": "Lifecycle Continuity E2E"})
        assert draft_resp.status_code == 201
        project_id = draft_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("continuity-e2e.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200
        assert ingest_resp.json()["project_id"] == project_id

        first_update = client.patch(
            f"/api/projects/{project_id}/metadata",
            json={"description": "first edit", "tags": ["first"]},
        )
        assert first_update.status_code == 200
        assert first_update.json()["project_id"] == project_id

        second_update = client.patch(
            f"/api/projects/{project_id}/metadata",
            json={"title": "Lifecycle Continuity E2E Updated", "tags": ["first", "second"]},
        )
        assert second_update.status_code == 200
        assert second_update.json()["project_id"] == project_id
        assert second_update.json()["title"] == "Lifecycle Continuity E2E Updated"
        assert second_update.json()["tags"] == ["first", "second"]

    project, chapter_count = _read_project_snapshot(project_id)
    assert project.id == project_id
    assert project.lifecycle_state == PROJECT_LIFECYCLE_INGESTED
    assert project.title == "Lifecycle Continuity E2E Updated"
    assert project.tags == ["first", "second"]
    assert chapter_count == 2
