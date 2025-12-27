import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_export_voice_resolution_outputs.db"

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

    db_file = Path("test_nipe_export_voice_resolution_outputs.db")
    if db_file.exists():
        db_file.unlink()


def test_export_includes_per_segment_voice_resolution_outputs() -> None:
    with TestClient(app) as client:
        create_resp = client.post("/api/projects", json={"title": "Per-Segment Voice Output"})
        assert create_resp.status_code == 201
        project_id = create_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": (
                    "sample.txt",
                    io.BytesIO(
                        b'Chapter 1\n"Hello there," Ally said.'
                    ),
                    "text/plain",
                )
            },
        )
        assert ingest_resp.status_code == 200

        update_resp = client.put(
            f"/api/projects/{project_id}/characters",
            json={
                "characters": [
                    {
                        "name": "Ally",
                        "verbalized_form": "Ally",
                        "gender": "female",
                        "voice_id": "ally_custom_voice",
                        "aliases": [],
                        "notes": None,
                        "source": "manual",
                        "confidence": 1.0,
                        "inferred_gender": "female",
                        "inferred_confidence": 1.0,
                        "inferred_source_trace": [],
                    }
                ]
            },
        )
        assert update_resp.status_code == 200

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"allow_unfinalized_character_map": True, "max_segment_chars": 100},
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200

        segments = export_resp.json()["segments"]
        assert segments

        for segment in segments:
            assert "voice_id" in segment
            assert "resolved_voice_id" in segment
            assert "speaker_id" in segment
            assert "speaker" in segment
            assert "gender" in segment
            assert isinstance(segment["voice_id"], str)
            assert isinstance(segment["resolved_voice_id"], str)
            assert segment["resolved_voice_id"] == segment["voice_id"]

        resolved_segments = [segment for segment in segments if segment.get("speaker_id") is not None]
        assert resolved_segments
        assert any(segment["speaker_id"] is not None for segment in resolved_segments)
        assert resolved_segments[0]["voice_id"] == "ally_custom_voice"
