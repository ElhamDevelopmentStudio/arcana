import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_acceptance_shadow_slave_ingest_chapterize.db"

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.main import app


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_acceptance_shadow_slave_ingest_chapterize.db")
    if db_file.exists():
        db_file.unlink()


def test_acceptance_shadow_slave_corpus_ingests_and_chapterizes_cleanly() -> None:
    shadow_slave_corpus = (
        "Shadow Slave\n\n"
        "Chapter 1\n"
        "Sunny stood at the edge of the ruined courtyard while rain struck old stone.\n\n"
        "Chapter 2\n"
        "Nephis watched the horizon and counted each distant flare in the night.\n\n"
        "Chapter 3\n"
        "The gate opened and their steps echoed through the drowned corridor."
    )

    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "ACC-001 Shadow Slave Corpus"})
        assert project_resp.status_code == 201
        project_id = int(project_resp.json()["id"])

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": (
                    "shadow-slave-corpus.txt",
                    io.BytesIO(shadow_slave_corpus.encode("utf-8")),
                    "text/plain",
                )
            },
        )
        assert ingest_resp.status_code == 200
        assert int(ingest_resp.json()["chapter_count"]) == 3

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={
                "mode": "audiobook",
                "max_segment_chars": 120,
                "allow_unfinalized_character_map": True,
                "llm_enabled": False,
                "provider_name": "openrouter",
                "max_calls_per_day": 2,
            },
        )
        assert run_resp.status_code == 200
        run_id = int(run_resp.json()["run_id"])

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200
        payload = export_resp.json()
        assert payload["status"] == "completed"
        segments = payload["segments"]
        assert segments

        chapter_ids = sorted({int(segment["chapter_id"]) for segment in segments})
        assert chapter_ids == [1, 2, 3]

