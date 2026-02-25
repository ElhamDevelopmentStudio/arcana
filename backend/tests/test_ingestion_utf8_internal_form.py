import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_ingestion_utf8_internal.db"

from app import main as main_module
from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Chapter
from app.services.ingestion import to_internal_utf8


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()
    os.environ.pop("ENABLE_EPUB_INGESTION", None)

    db_file = Path("test_nipe_ingestion_utf8_internal.db")
    if db_file.exists():
        db_file.unlink()


def _assert_project_chapters_are_utf8_safe(project_id: int) -> None:
    session = get_session_factory()()
    try:
        rows = session.query(Chapter).filter(Chapter.project_id == project_id).all()
        assert rows
        for row in rows:
            row.chapter_title.encode("utf-8", errors="strict")
            row.raw_text.encode("utf-8", errors="strict")
            assert not any(0xD800 <= ord(ch) <= 0xDFFF for ch in row.chapter_title)
            assert not any(0xD800 <= ord(ch) <= 0xDFFF for ch in row.raw_text)
    finally:
        session.close()


def test_unit_to_internal_utf8_removes_surrogate_codepoints() -> None:
    unsafe = "Shadow\udcffSlave"
    normalized = to_internal_utf8(unsafe)
    normalized.encode("utf-8", errors="strict")
    assert normalized != unsafe
    assert not any(0xD800 <= ord(ch) <= 0xDFFF for ch in normalized)


def test_integration_txt_ingestion_persists_utf8_safe_content() -> None:
    with TestClient(app) as client:
        create_resp = client.post("/api/projects", json={"title": "UTF8 TXT Integration"})
        assert create_resp.status_code == 201
        project_id = create_resp.json()["id"]

        cp1252_payload = "Chapter 1\nCafe café scene.".encode("cp1252")
        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("utf8.txt", io.BytesIO(cp1252_payload), "text/plain")},
        )
        assert ingest_resp.status_code == 200

    _assert_project_chapters_are_utf8_safe(project_id)


def test_e2e_markdown_and_directory_ingestion_persist_utf8_safe_content() -> None:
    with TestClient(app) as client:
        markdown_project_resp = client.post("/api/projects", json={"title": "UTF8 Markdown E2E"})
        assert markdown_project_resp.status_code == 201
        markdown_project_id = markdown_project_resp.json()["id"]

        markdown_content = (
            "# Chronicle\n\n"
            "## Chapter 1\n"
            "Line with café and déjà vu.\n\n"
            "## Chapter 2\n"
            "Line with façade.\n"
        )
        markdown_ingest_resp = client.post(
            f"/api/projects/{markdown_project_id}/ingest/markdown",
            files={"file": ("chronicle.md", io.BytesIO(markdown_content.encode("utf-8")), "text/markdown")},
        )
        assert markdown_ingest_resp.status_code == 200

        directory_project_resp = client.post("/api/projects", json={"title": "UTF8 Directory E2E"})
        assert directory_project_resp.status_code == 201
        directory_project_id = directory_project_resp.json()["id"]

        directory_files = [
            ("files", ("chapter_1.txt", io.BytesIO("Début".encode("utf-8")), "text/plain")),
            ("files", ("chapter_2.txt", io.BytesIO("Crème brûlée".encode("utf-8")), "text/plain")),
        ]
        directory_ingest_resp = client.post(
            f"/api/projects/{directory_project_id}/ingest/chapters-dir",
            files=directory_files,
        )
        assert directory_ingest_resp.status_code == 200

    _assert_project_chapters_are_utf8_safe(markdown_project_id)
    _assert_project_chapters_are_utf8_safe(directory_project_id)


def test_regression_epub_ingestion_sanitizes_parser_output_to_utf8(monkeypatch) -> None:
    os.environ["ENABLE_EPUB_INGESTION"] = "true"
    clear_settings_cache()

    def _fake_extract_epub_chapters(_payload: bytes) -> list[tuple[str, str]]:
        return [("Chapter\udcff One", "Body with bad surrogate \udcff text.")]

    monkeypatch.setattr(main_module, "extract_epub_chapters", _fake_extract_epub_chapters)

    with TestClient(app) as client:
        create_resp = client.post("/api/projects", json={"title": "UTF8 EPUB Regression"})
        assert create_resp.status_code == 201
        project_id = create_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/epub",
            files={"file": ("novel.epub", io.BytesIO(b"epub-bytes"), "application/epub+zip")},
        )
        assert ingest_resp.status_code == 200
        assert ingest_resp.json()["chapter_count"] == 1

    _assert_project_chapters_are_utf8_safe(project_id)
