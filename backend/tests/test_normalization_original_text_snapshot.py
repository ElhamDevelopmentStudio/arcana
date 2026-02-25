import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_norm_original_snapshot.db"

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

    db_file = Path("test_nipe_norm_original_snapshot.db")
    if db_file.exists():
        db_file.unlink()


def test_integration_txt_ingestion_stores_original_text_snapshot_per_chapter() -> None:
    text = (
        "Chapter 1\n"
        "“Welcome”…\u00A0  to the voyage.\n"
    )

    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Original Snapshot Integration"})
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
        assert chapter.original_text_snapshot == "“Welcome”…\u00A0  to the voyage."
        assert chapter.original_text_snapshot == chapter.raw_text
        assert chapter.normalized_text == '"Welcome"... to the voyage.'
    finally:
        session.close()
