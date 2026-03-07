import hashlib
import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_raw_corpus_blob.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import ProjectRawCorpusBlob


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_raw_corpus_blob.db")
    if db_file.exists():
        db_file.unlink()


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def test_e2e_txt_ingest_persists_raw_corpus_blob() -> None:
    source_payload = "Chapter 1\nThe lantern burned low.\n\nChapter 2\nRain began."

    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Raw Blob TXT"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("story.txt", io.BytesIO(source_payload.encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

    session = get_session_factory()()
    try:
        blobs = session.query(ProjectRawCorpusBlob).filter(ProjectRawCorpusBlob.project_id == project_id).all()
        assert len(blobs) == 1
        assert blobs[0].source == "txt"
        assert blobs[0].source_filename == "story.txt"
        assert blobs[0].raw_corpus_blob.decode("utf-8") == source_payload
        assert blobs[0].blob_sha256 == _sha256(source_payload)
    finally:
        session.close()


def test_e2e_markdown_ingest_persists_raw_corpus_blob() -> None:
    source_payload = (
        "# Intro\n\n"
        "## Chapter 1\n"
        "Shadows moved down the wall.\n\n"
        "## Chapter 2\n"
        "The tower rang with wind."
    )

    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Raw Blob Markdown"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/markdown",
            files={"file": ("story.md", io.BytesIO(source_payload.encode("utf-8")), "text/markdown")},
        )
        assert ingest_resp.status_code == 200

    session = get_session_factory()()
    try:
        blobs = session.query(ProjectRawCorpusBlob).filter(ProjectRawCorpusBlob.project_id == project_id).all()
        assert len(blobs) == 1
        assert blobs[0].source == "markdown"
        assert blobs[0].source_filename == "story.md"
        assert blobs[0].raw_corpus_blob.decode("utf-8") == source_payload
        assert blobs[0].blob_sha256 == _sha256(source_payload)
    finally:
        session.close()


def test_e2e_chapters_dir_ingest_persists_raw_corpus_blob() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Raw Blob Directory"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/chapters-dir",
            files=[
                ("files", ("chapter_1.txt", io.BytesIO(b"Chapter 1\nFirst wave"), "text/plain")),
                ("files", ("chapter_2.txt", io.BytesIO(b"Chapter 2\nSecond tide"), "text/plain")),
            ],
        )
        assert ingest_resp.status_code == 200
        assert ingest_resp.json()["chapter_count"] == 2

    expected_blob = "Chapter 1\nFirst wave\n\nChapter 2\nSecond tide"
    session = get_session_factory()()
    try:
        blobs = session.query(ProjectRawCorpusBlob).filter(ProjectRawCorpusBlob.project_id == project_id).all()
        assert len(blobs) == 1
        assert blobs[0].source == "chapters-dir"
        assert blobs[0].source_filename is None
        assert blobs[0].raw_corpus_blob.decode("utf-8") == expected_blob
        assert blobs[0].blob_sha256 == _sha256(expected_blob)
    finally:
        session.close()


def test_e2e_append_chapter_creates_new_raw_corpus_snapshot() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Raw Blob Append"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("seed.txt", io.BytesIO(b"Chapter 1\nFirst wave"), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        append_resp = client.post(
            f"/api/projects/{project_id}/ingest/append-chapter",
            files={"file": ("chapter_2.txt", io.BytesIO(b"Chapter 2\nSecond tide"), "text/plain")},
        )
        assert append_resp.status_code == 200

    expected_full_raw_corpus = "First wave\n\nSecond tide"
    session = get_session_factory()()
    try:
        blobs = (
            session.query(ProjectRawCorpusBlob)
            .filter(ProjectRawCorpusBlob.project_id == project_id)
            .order_by(ProjectRawCorpusBlob.id.asc())
            .all()
        )
        assert len(blobs) == 2
        assert blobs[1].source == "append-chapter"
        assert blobs[1].source_filename == "chapter_2.txt"
        assert blobs[1].raw_corpus_blob.decode("utf-8") == expected_full_raw_corpus
        assert blobs[1].blob_sha256 == _sha256(expected_full_raw_corpus)
    finally:
        session.close()
