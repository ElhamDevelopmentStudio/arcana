import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_export_phonetic_text.db"

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

    db_file = Path("test_nipe_export_phonetic_text.db")
    if db_file.exists():
        db_file.unlink()


def _create_project(client: TestClient) -> int:
    response = client.post("/api/projects", json={"title": "Export Phonetic Text Project"})
    assert response.status_code == 201
    return response.json()["id"]


def _run_and_export(project_id: int, client: TestClient) -> dict:
    run_resp = client.post(f"/api/projects/{project_id}/runs", json={"allow_unfinalized_character_map": True})
    assert run_resp.status_code == 200
    run_id = run_resp.json()["run_id"]

    export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
    assert export_resp.status_code == 200
    return export_resp.json()


def test_export_includes_phonetic_ready_text_for_all_segments() -> None:
    with TestClient(app) as client:
        project_id = _create_project(client)

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": (
                    "novel.txt",
                    io.BytesIO(
                        b'Chapter 1\nThe Aegis stood above the tower, and the crew cheered.',
                    ),
                    "text/plain",
                )
            },
        )
        assert ingest_resp.status_code == 200

        dict_resp = client.put(
            f"/api/projects/{project_id}/pronunciation-dictionary/global",
            json={"entries": [{"term": "Aegis", "verbalized_form": "EE-gis", "confidence": 1.0}]},
        )
        assert dict_resp.status_code == 200

        payload = _run_and_export(project_id=project_id, client=client)

        segments = payload["segments"]
        assert payload["status"] == "completed"
        assert len(segments) >= 1

        for segment in segments:
            assert isinstance(segment.get("phonetic_text"), str)
            assert segment["phonetic_text"].strip() != ""
            assert "phonetic_text" in segment

        matching_segments = [
            segment for segment in segments if "Aegis" in str(segment.get("original_text", ""))
        ]
        assert matching_segments
        assert "EE-gis" in matching_segments[0]["phonetic_text"]
