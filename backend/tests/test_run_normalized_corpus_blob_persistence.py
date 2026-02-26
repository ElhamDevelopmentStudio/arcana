import hashlib
import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_normalized_corpus_blob.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Chapter, RunNormalizedCorpusBlob


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_normalized_corpus_blob.db")
    if db_file.exists():
        db_file.unlink()


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _ingest_project_text(project_title: str, source_payload: str) -> int:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": project_title})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("story.txt", io.BytesIO(source_payload.encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

    return project_id


def test_e2e_run_persists_normalized_corpus_blob_with_run_linkage() -> None:
    source_payload = "Chapter 1\nThe lantern burned low.\n\nChapter 2\nRain began."
    project_id = _ingest_project_text(
        project_title="Normalized Corpus TXT",
        source_payload=source_payload,
    )

    with TestClient(app) as client:
        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"mode": "audiobook", "max_segment_chars": 255},
        )
        assert run_resp.status_code == 200
        run_id = int(run_resp.json()["run_id"])

    session = get_session_factory()()
    try:
        blob = (
            session.query(RunNormalizedCorpusBlob)
            .filter(RunNormalizedCorpusBlob.run_id == run_id)
            .one_or_none()
        )
        assert blob is not None
        assert blob.run_id == run_id
        assert blob.source == "pipeline"
        assert blob.source_filename is None

        chapters = (
            session.query(Chapter)
            .filter(Chapter.project_id == project_id)
            .order_by(Chapter.chapter_index.asc())
            .all()
        )
        reconstructed_normalized = "\n\n".join(chapter.normalized_text for chapter in chapters)
        assert blob.normalized_corpus_blob.decode("utf-8") == reconstructed_normalized
        assert blob.corpus_sha256 == _sha256(reconstructed_normalized)
    finally:
        session.close()
