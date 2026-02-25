import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_norm_em_dash.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Chapter
from app.services.normalization import normalize_em_dash_dialogue_style


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_norm_em_dash.db")
    if db_file.exists():
        db_file.unlink()


def test_unit_normalize_em_dash_leader_to_dialogue_hyphen_prefix() -> None:
    raw = "—The lantern dimmed.\n— \"Hold on.\"\nHe paused—thinking further."
    normalized = normalize_em_dash_dialogue_style(raw)
    assert normalized == "- The lantern dimmed.\n- \"Hold on.\"\nHe paused—thinking further."


def test_integration_txt_ingestion_normalizes_em_dash_dialogue_prefix_in_normalized_text() -> None:
    text = (
        "Chapter 1\n"
        "— “Hello,” Sunny said.\n"
        "— “Wait,” Nephis said.\n"
        "He paused—thinking deeper.\n"
    )
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Norm Em Dash Dialogue Integration"})
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
        assert (
            chapter.normalized_text
            == '- "Hello," Sunny said.\n- "Wait," Nephis said.\nHe paused—thinking deeper.'
        )
    finally:
        session.close()
