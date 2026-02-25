import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_norm_copy_artifacts.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Chapter
from app.services.normalization import remove_copy_artifacts


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()
    os.environ.pop("COPY_ARTIFACT_PATTERNS", None)

    db_file = Path("test_nipe_norm_copy_artifacts.db")
    if db_file.exists():
        db_file.unlink()


def _set_copy_artifact_patterns(value: str | None) -> None:
    if value is None:
        os.environ.pop("COPY_ARTIFACT_PATTERNS", None)
    else:
        os.environ["COPY_ARTIFACT_PATTERNS"] = value
    clear_settings_cache()


def test_unit_remove_copy_artifacts_strips_default_artifact_lines() -> None:
    _set_copy_artifact_patterns(None)
    raw = "Scene starts.\nPage 12\n<<< OCR >>>\nAdvertisement\nScene ends."
    normalized = remove_copy_artifacts(raw)
    assert normalized == "Scene starts.\nScene ends."


def test_integration_txt_ingestion_removes_copy_artifacts_from_normalized_text() -> None:
    _set_copy_artifact_patterns(None)
    text = (
        "Chapter 1\n"
        "Scene starts.\n"
        "Page 12\n"
        "Advertisement\n"
        "Scene ends.\n"
    )
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Norm Copy Artifacts Integration"})
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
        assert chapter.normalized_text == "Scene starts.\nScene ends."
    finally:
        session.close()


def test_e2e_markdown_ingestion_removes_ocr_marker_artifacts() -> None:
    _set_copy_artifact_patterns(None)
    markdown_text = (
        "# Story\n\n"
        "## Chapter 1\n"
        "<<< OCR >>>\n"
        "Actual content line.\n"
    )
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Norm Copy Artifacts E2E"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/markdown",
            files={"file": ("source.md", io.BytesIO(markdown_text.encode("utf-8")), "text/markdown")},
        )
        assert ingest_resp.status_code == 200

    session = get_session_factory()()
    try:
        chapter = session.query(Chapter).filter(Chapter.project_id == project_id).one()
        assert chapter.normalized_text == "Actual content line."
    finally:
        session.close()


def test_regression_custom_pattern_set_can_disable_default_removals() -> None:
    _set_copy_artifact_patterns(r"^\s*DO_NOT_KEEP_ME\s*$")
    raw = "Page 12\nDo not strip this line under custom config."
    normalized = remove_copy_artifacts(raw)
    assert normalized == raw
