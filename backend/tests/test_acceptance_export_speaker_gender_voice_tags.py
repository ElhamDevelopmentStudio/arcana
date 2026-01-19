import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_acceptance_export_speaker_gender_voice_tags.db"

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

    db_file = Path("test_nipe_acceptance_export_speaker_gender_voice_tags.db")
    if db_file.exists():
        db_file.unlink()


def test_acceptance_export_contains_speaker_gender_voice_tags_where_applicable() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "ACC-005 Speaker Gender Voice Tags"})
        assert project_resp.status_code == 201
        project_id = int(project_resp.json()["id"])

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": (
                    "speaker-gender-voice.txt",
                    io.BytesIO(
                        (
                            "Chapter 1\n"
                            '"Come closer," Alice said.\n'
                            "\n"
                            "The lantern cracked in the rain."
                        ).encode("utf-8")
                    ),
                    "text/plain",
                )
            },
        )
        assert ingest_resp.status_code == 200

        voice_resp = client.put(
            f"/api/projects/{project_id}/voices",
            json={
                "narrator_voice": "acc005_narrator",
                "male_default_voice": "acc005_male_default",
                "female_default_voice": "acc005_female_default",
                "neutral_default_voice": "acc005_neutral_default",
                "unknown_default_voice": "acc005_unknown_default",
            },
        )
        assert voice_resp.status_code == 200

        upsert_resp = client.put(
            f"/api/projects/{project_id}/characters",
            json={
                "characters": [
                    {
                        "name": "Alice",
                        "verbalized_form": "Alice",
                        "gender": "female",
                        "voice_id": "acc005_alice_voice",
                        "aliases": ["Al"],
                        "source": "manual",
                        "confidence": 1.0,
                    }
                ]
            },
        )
        assert upsert_resp.status_code == 200

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={
                "mode": "author",
                "max_segment_chars": 120,
                "llm_enabled": False,
                "provider_name": "openrouter",
                "max_calls_per_day": 2,
                "allow_unfinalized_character_map": True,
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

        assert all("speaker" in segment for segment in segments)
        assert all("gender" in segment for segment in segments)
        assert all("voice_id" in segment for segment in segments)
        assert all("resolved_voice_id" in segment for segment in segments)

        attributable_segments = [segment for segment in segments if segment.get("speaker_id") is not None]
        assert attributable_segments
        assert all(str(segment["speaker"]).strip() and str(segment["speaker"]).lower() != "unknown" for segment in attributable_segments)
        assert all(str(segment["gender"]).strip() and str(segment["gender"]).lower() != "unknown" for segment in attributable_segments)
        assert all(str(segment["voice_id"]).strip() for segment in attributable_segments)
        assert all(str(segment["resolved_voice_id"]).strip() for segment in attributable_segments)

        alice_segment = next((segment for segment in attributable_segments if str(segment.get("speaker", "")).lower() == "alice"), None)
        assert alice_segment is not None
        assert str(alice_segment["gender"]).lower() == "female"
        assert alice_segment["voice_id"] == "acc005_alice_voice"
        assert alice_segment["resolved_voice_id"] == "acc005_alice_voice"
