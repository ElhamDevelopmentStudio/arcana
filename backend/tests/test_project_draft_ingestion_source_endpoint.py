import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_project_draft_ingestion_source_endpoint.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Project


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()
    db_file = Path("test_nipe_project_draft_ingestion_source_endpoint.db")
    if db_file.exists():
        db_file.unlink()


def _sample_txt() -> str:
    return (
        "Chapter 1\n"
        '"Sunny looked around," Sunny said. The cold wind cut through the dark street.\n\n'
        "Chapter 2\n"
        "Nephis smiled. Hope rose with the warm light."
    )


def _get_project_ingestion_log(project_id: int) -> dict:
    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        return dict(project.ingestion_log_json or {})
    finally:
        session.close()


def test_integration_attach_first_ingestion_source_to_draft_project() -> None:
    with TestClient(app) as client:
        create_resp = client.post("/api/projects/drafts", json={"title": "Draft Source Attach Integration"})
        assert create_resp.status_code == 201
        project_id = create_resp.json()["id"]

        attach_resp = client.post(
            f"/api/projects/{project_id}/ingest/source",
            json={"source": " TXT ", "source_filename": "  book.txt  "},
        )
        assert attach_resp.status_code == 200
        payload = attach_resp.json()
        assert payload["project_id"] == project_id
        assert payload["source"] == "txt"
        assert payload["source_filename"] == "book.txt"
        assert isinstance(payload["attached_at"], str)

    ingestion_log = _get_project_ingestion_log(project_id)
    assert ingestion_log["first_source"] == "txt"
    assert ingestion_log["first_source_filename"] == "book.txt"
    assert isinstance(ingestion_log["first_source_attached_at"], str)


def test_integration_attach_first_ingestion_source_rejects_second_attachment() -> None:
    with TestClient(app) as client:
        create_resp = client.post("/api/projects/drafts", json={"title": "Draft Source Attach Rejection"})
        assert create_resp.status_code == 201
        project_id = create_resp.json()["id"]

        first_attach = client.post(f"/api/projects/{project_id}/ingest/source", json={"source": "markdown"})
        assert first_attach.status_code == 200

        second_attach = client.post(f"/api/projects/{project_id}/ingest/source", json={"source": "txt"})
        assert second_attach.status_code == 409
        assert "already attached" in second_attach.json()["detail"].lower()


def test_e2e_attach_source_then_ingest_txt_preserves_first_source_marker() -> None:
    with TestClient(app) as client:
        create_resp = client.post("/api/projects/drafts", json={"title": "Draft Source Attach E2E"})
        assert create_resp.status_code == 201
        project_id = create_resp.json()["id"]

        attach_resp = client.post(f"/api/projects/{project_id}/ingest/source", json={"source": "txt"})
        assert attach_resp.status_code == 200

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200
        assert ingest_resp.json()["chapter_count"] == 2

    ingestion_log = _get_project_ingestion_log(project_id)
    assert ingestion_log["first_source"] == "txt"
    assert ingestion_log["source"] == "txt"
