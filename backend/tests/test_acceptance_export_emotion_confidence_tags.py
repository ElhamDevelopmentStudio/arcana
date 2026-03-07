import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_acceptance_export_emotion_confidence_tags.db"

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

    db_file = Path("test_nipe_acceptance_export_emotion_confidence_tags.db")
    if db_file.exists():
        db_file.unlink()


def test_acceptance_export_contains_emotion_and_confidence_tags() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "ACC-006 Emotion Confidence Tags"})
        assert project_resp.status_code == 201
        project_id = int(project_resp.json()["id"])

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": (
                    "emotion-confidence.txt",
                    io.BytesIO(
                        (
                            "Chapter 1\n"
                            "Cold rain fell on a ruined gate while the scouts held their breath.\n\n"
                            "Chapter 2\n"
                            "By dawn, the tension eased and a fragile hope returned."
                        ).encode("utf-8")
                    ),
                    "text/plain",
                )
            },
        )
        assert ingest_resp.status_code == 200

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

        for segment in segments:
            assert isinstance(segment.get("emotion_valence"), (int, float))
            assert isinstance(segment.get("emotion_intensity"), (int, float))
            assert -1.0 <= float(segment["emotion_valence"]) <= 1.0
            assert 0.0 <= float(segment["emotion_intensity"]) <= 1.0
            assert isinstance(segment.get("emotion_primary_label"), str)
            assert segment["emotion_primary_label"].strip() != ""
            assert isinstance(segment.get("emotion_secondary_label"), str)
            assert segment["emotion_secondary_label"].strip() != ""

            confidence = segment.get("confidence")
            assert isinstance(confidence, dict)
            assert isinstance(confidence.get("emotion"), (int, float))
            assert 0.0 <= float(confidence["emotion"]) <= 1.0

