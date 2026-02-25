import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_ingestion_path_matrix.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Chapter


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_ingestion_path_matrix.db")
    if db_file.exists():
        db_file.unlink()


def _create_project(client: TestClient, title: str) -> int:
    project_resp = client.post("/api/projects", json={"title": title})
    assert project_resp.status_code == 201
    return project_resp.json()["id"]


def test_unit_ingestion_path_matrix_contract() -> None:
    endpoints = {
        "txt": "/api/projects/{project_id}/ingest/txt",
        "directory": "/api/projects/{project_id}/ingest/chapters-dir",
        "markdown": "/api/projects/{project_id}/ingest/markdown",
        "append": "/api/projects/{project_id}/ingest/append-chapter",
    }
    assert set(endpoints.keys()) == {"txt", "directory", "markdown", "append"}
    assert all(path.startswith("/api/projects/{project_id}/ingest/") for path in endpoints.values())


def test_integration_txt_and_append_paths_share_project_state() -> None:
    with TestClient(app) as client:
        project_id = _create_project(client, "Path Matrix Integration")

        txt_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("source.txt", io.BytesIO(b"Chapter 1\nOne"), "text/plain")},
        )
        assert txt_resp.status_code == 200
        assert txt_resp.json()["chapter_count"] == 1

        append_resp = client.post(
            f"/api/projects/{project_id}/ingest/append-chapter",
            files={"file": ("chapter_2.txt", io.BytesIO(b"Chapter 2\nTwo"), "text/plain")},
        )
        assert append_resp.status_code == 200
        assert append_resp.json()["chapter_count"] == 2


def test_e2e_directory_and_markdown_paths_persist_expected_rows() -> None:
    with TestClient(app) as client:
        directory_project = _create_project(client, "Path Matrix Directory")
        directory_resp = client.post(
            f"/api/projects/{directory_project}/ingest/chapters-dir",
            files=[
                ("files", ("chapter_2.txt", io.BytesIO(b"Second"), "text/plain")),
                ("files", ("chapter_1.txt", io.BytesIO(b"First"), "text/plain")),
            ],
        )
        assert directory_resp.status_code == 200
        assert directory_resp.json()["chapter_count"] == 2

        markdown_project = _create_project(client, "Path Matrix Markdown")
        markdown_payload = (
            "# Story\n\n"
            "## Chapter 1\n"
            "First block\n\n"
            "## Chapter 2\n"
            "Second block\n"
        )
        markdown_resp = client.post(
            f"/api/projects/{markdown_project}/ingest/markdown",
            files={"file": ("source.md", io.BytesIO(markdown_payload.encode("utf-8")), "text/markdown")},
        )
        assert markdown_resp.status_code == 200
        assert markdown_resp.json()["chapter_count"] == 2

    session = get_session_factory()()
    try:
        directory_count = session.query(Chapter).filter(Chapter.project_id == directory_project).count()
        markdown_count = session.query(Chapter).filter(Chapter.project_id == markdown_project).count()
        assert directory_count == 2
        assert markdown_count == 2
    finally:
        session.close()


def test_regression_encoding_paths_cover_supported_and_rejected_inputs() -> None:
    with TestClient(app) as client:
        supported_project = _create_project(client, "Path Matrix Supported Encoding")
        cp1252_resp = client.post(
            f"/api/projects/{supported_project}/ingest/txt",
            files={"file": ("cp1252.txt", io.BytesIO("Chapter 1\ncafé".encode("cp1252")), "text/plain")},
        )
        assert cp1252_resp.status_code == 200
        assert cp1252_resp.json()["chapter_count"] == 1

        rejected_project = _create_project(client, "Path Matrix Unsupported Encoding")
        utf16_without_bom = ("Chapter 1\n" + ("bad " * 30)).encode("utf-16-le")
        rejected_resp = client.post(
            f"/api/projects/{rejected_project}/ingest/txt",
            files={"file": ("broken.txt", io.BytesIO(utf16_without_bom), "text/plain")},
        )
        assert rejected_resp.status_code == 400
        assert rejected_resp.headers["x-nipe-error-type"] == "unsupported_encoding"
