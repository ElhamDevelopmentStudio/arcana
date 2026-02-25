import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_ingest_epub_toggle.db"

from app.config import clear_settings_cache, get_settings
from app.database import init_db, reset_engine
from app.main import app


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()
    os.environ.pop("ENABLE_EPUB_INGESTION", None)

    db_file = Path("test_nipe_ingest_epub_toggle.db")
    if db_file.exists():
        db_file.unlink()


def _set_epub_toggle(enabled: bool) -> None:
    os.environ["ENABLE_EPUB_INGESTION"] = "true" if enabled else "false"
    clear_settings_cache()


def test_unit_epub_toggle_defaults_to_disabled() -> None:
    os.environ.pop("ENABLE_EPUB_INGESTION", None)
    clear_settings_cache()
    assert get_settings().enable_epub_ingestion is False


def test_integration_epub_ingestion_rejected_when_toggle_disabled() -> None:
    _set_epub_toggle(False)
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "EPUB Toggle Integration"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/epub",
            files={"file": ("novel.epub", io.BytesIO(b"binary"), "application/epub+zip")},
        )
        assert ingest_resp.status_code == 501
        assert ingest_resp.json()["detail"] == "EPUB ingestion is disabled by configuration"


def test_e2e_epub_toggle_enabled_uses_pluggable_parser_stub() -> None:
    _set_epub_toggle(True)
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "EPUB Toggle E2E"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/epub",
            files={"file": ("novel.epub", io.BytesIO(b"binary"), "application/epub+zip")},
        )
        assert ingest_resp.status_code == 501
        assert "EPUB parser is not implemented yet" in ingest_resp.json()["detail"]


def test_regression_epub_endpoint_validates_extension_when_enabled() -> None:
    _set_epub_toggle(True)
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "EPUB Toggle Regression"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/epub",
            files={"file": ("novel.txt", io.BytesIO(b"not epub"), "text/plain")},
        )
        assert ingest_resp.status_code == 400
        assert ingest_resp.json()["detail"] == "Only .epub files are supported"
