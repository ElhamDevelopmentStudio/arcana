import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_acceptance_export_phonetic_ready_text.db"

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

    db_file = Path("test_nipe_acceptance_export_phonetic_ready_text.db")
    if db_file.exists():
        db_file.unlink()


def test_acceptance_export_contains_phonetic_ready_text() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "ACC-004 Phonetic Export"})
        assert project_resp.status_code == 201
        project_id = int(project_resp.json()["id"])

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": (
                    "novel.txt",
                    io.BytesIO(
                        b"Chapter 1\nThe Aegis stood above the tower while the crew watched in silence.",
                    ),
                    "text/plain",
                )
            },
        )
        assert ingest_resp.status_code == 200

        dict_resp = client.put(
            f"/api/projects/{project_id}/pronunciation-dictionary/global",
            json={
                "entries": [
                    {
                        "term": "Aegis",
                        "verbalized_form": "EE-gis",
                        "confidence": 1.0,
                    }
                ]
            },
        )
        assert dict_resp.status_code == 200

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"allow_unfinalized_character_map": True, "llm_enabled": False},
        )
        assert run_resp.status_code == 200
        run_id = int(run_resp.json()["run_id"])

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200
        payload = export_resp.json()
        assert payload["status"] == "completed"
        segments = payload["segments"]
        assert segments

        assert all(isinstance(segment.get("phonetic_text"), str) and segment["phonetic_text"].strip() for segment in segments)
        assert any("EE-gis" in str(segment.get("phonetic_text", "")) for segment in segments)

