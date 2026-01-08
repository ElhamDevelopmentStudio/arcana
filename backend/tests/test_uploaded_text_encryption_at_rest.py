import io
import os
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_uploaded_text_encryption.db"
os.environ["SAAS_MODE"] = "true"
os.environ["DATA_ENCRYPTION_KEY"] = "nfr5-003-test-key-unit"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Chapter, ProjectRawCorpusBlob


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()
    os.environ.pop("SAAS_MODE", None)
    os.environ.pop("DATA_ENCRYPTION_KEY", None)

    db_file = Path("test_nipe_uploaded_text_encryption.db")
    if db_file.exists():
        db_file.unlink()


def _readable_bytes(value: object) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, memoryview):
        return value.tobytes()
    if value is None:
        return b""
    return bytes(value)


def _seed_sensitive_project() -> tuple[int, str]:
    source = "Chapter 1\nThe archive stores a sensitive phrase: crimson owl."
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Encrypted Text Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("story.txt", io.BytesIO(source.encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

    return project_id, source


def test_uploaded_chapter_text_fields_are_stored_encrypted_in_db() -> None:
    project_id, source = _seed_sensitive_project()

    session = get_session_factory()()
    try:
        chapter = session.query(Chapter).filter(Chapter.project_id == project_id).one()
        assert chapter.raw_text
        assert source.split("\n", 1)[1] in chapter.raw_text
        assert chapter.original_text_snapshot
        assert chapter.normalized_text_snapshot

        raw_rows = session.execute(
            text(
                """
                SELECT raw_text, original_text_snapshot, normalized_text, normalized_text_snapshot
                FROM chapters
                WHERE project_id = :project_id
                """,
            ),
            {"project_id": project_id},
        ).fetchall()
        assert len(raw_rows) == 1
        encrypted_columns = raw_rows[0]
        for payload in encrypted_columns:
            raw_value = _readable_bytes(payload)
            assert raw_value.startswith(b"NIPE_ENC_V1|")
            assert b"sensitive phrase" not in raw_value.lower()
            assert b"crimson owl" not in raw_value.lower()
    finally:
        session.close()


def test_raw_corpus_blob_is_encrypted_and_retrievable() -> None:
    project_id, source = _seed_sensitive_project()
    expected_raw = source.encode("utf-8")

    session = get_session_factory()()
    try:
        blob = session.query(ProjectRawCorpusBlob).filter(ProjectRawCorpusBlob.project_id == project_id).one()
        assert blob.raw_corpus_blob.decode("utf-8") == source

        stored = (
            session.execute(
                text(
                    """
                    SELECT raw_corpus_blob
                    FROM project_raw_corpus_blobs
                    WHERE project_id = :project_id
                    """,
                ),
                {"project_id": project_id},
            )
            .fetchone()[0]
        )
        raw_stored = _readable_bytes(stored)
        assert raw_stored.startswith(b"NIPE_ENC_V1|")
        assert expected_raw not in raw_stored
        assert b"crimson owl" not in raw_stored
    finally:
        session.close()
