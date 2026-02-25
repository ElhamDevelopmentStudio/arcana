import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_norm_unicode_canonical.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Chapter
from app.services.normalization import normalize_unicode_variants


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_norm_unicode_canonical.db")
    if db_file.exists():
        db_file.unlink()


def test_unit_normalize_unicode_variants_applies_nfkc_canonicalization() -> None:
    raw = "Ｆｕｌｌｗｉｄｔｈ ﬁ ligature ①"
    normalized = normalize_unicode_variants(raw)
    assert normalized == "Fullwidth fi ligature 1"


def test_integration_txt_ingestion_persists_canonical_unicode_in_normalized_text() -> None:
    text = (
        "Chapter 1\n"
        "Ｆｕｌｌｗｉｄｔｈ word and ﬁ ligature appear here.\n"
    )
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Norm Unicode Integration"})
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
        assert chapter.normalized_text == "Fullwidth word and fi ligature appear here."
    finally:
        session.close()


def test_e2e_markdown_ingestion_keeps_canonical_forms_for_compatibility_characters() -> None:
    markdown_text = (
        "# Story\n\n"
        "## Chapter 1\n"
        "Measure is ㎏ and index is ①.\n"
    )
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Norm Unicode E2E"})
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
        assert chapter.normalized_text == "Measure is kg and index is 1."
    finally:
        session.close()


def test_regression_ascii_content_remains_unchanged_after_unicode_normalization() -> None:
    raw = "Sunny and Nephis walked into the station."
    normalized = normalize_unicode_variants(raw)
    assert normalized == raw
