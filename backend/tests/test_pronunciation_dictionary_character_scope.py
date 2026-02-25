import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipg_character_scope.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Segment


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipg_character_scope.db")
    if db_file.exists():
        db_file.unlink()


def test_integration_character_pronunciation_dictionary_set_and_list() -> None:
    entries = [
        {
            "term": "Aegis",
            "verbalized_form": "Ah-jeez",
            "source": "user",
            "confidence": 1.0,
        }
    ]

    with TestClient(app) as client:
        project_resp = client.post(
            "/api/projects", json={"title": "Per-Character Pronunciation Dictionary"}
        )
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        put_resp = client.put(
            f"/api/projects/{project_id}/pronunciation-dictionary/character/Alice",
            json={"entries": entries},
        )
        assert put_resp.status_code == 200
        payload = put_resp.json()
        assert payload["project_id"] == project_id
        assert payload["scope"] == "character"
        assert len(payload["entries"]) == 1

        get_resp = client.get(f"/api/projects/{project_id}/pronunciation-dictionary/character/Alice")
        assert get_resp.status_code == 200
        listed = get_resp.json()
        assert listed["scope"] == "character"
        assert listed["entries"][0]["term"] == "Aegis"


def test_integration_character_pronunciation_dictionary_overrides_global_for_matching_speaker() -> None:
    with TestClient(app) as client:
        project_resp = client.post(
            "/api/projects",
            json={"title": "Per-Character Pronunciation Pipeline"},
        )
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", io.BytesIO(_build_sample_text().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        global_resp = client.put(
            f"/api/projects/{project_id}/pronunciation-dictionary/global",
            json={"entries": [{"term": "Aegis", "verbalized_form": "EE-jis", "confidence": 1.0}]},
        )
        assert global_resp.status_code == 200

        character_resp = client.put(
            f"/api/projects/{project_id}/pronunciation-dictionary/character/Alice",
            json={
                "entries": [
                    {
                        "term": "Aegis",
                        "verbalized_form": "Ah-jeez",
                        "confidence": 0.98,
                    }
                ]
            },
        )
        assert character_resp.status_code == 200

        run_payload = {
            "max_segment_chars": 80,
            "llm_enabled": False,
            "provider_name": "openrouter",
            "max_calls_per_day": 2,
            "allow_unfinalized_character_map": True,
        }
        run_resp = client.post(f"/api/projects/{project_id}/runs", json=run_payload)
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        session = get_session_factory()()
        try:
            segment_rows = session.query(Segment).filter(Segment.run_id == run_id).all()
            voiced_segments = [row for row in segment_rows if row.segment_json.get("speaker") not in {"unknown"}]
            assert len(voiced_segments) == 2

            payloads_by_speaker = {
                row.segment_json["speaker"]: row.segment_json for row in voiced_segments
            }
            assert set(payloads_by_speaker.keys()) == {"Alice", "Bob"}

            alice_payload = payloads_by_speaker["Alice"]
            bob_payload = payloads_by_speaker["Bob"]
            assert "Ah-jeez" in alice_payload["phonetic_text"]
            assert "EE-jis" not in alice_payload["phonetic_text"]
            assert "EE-jis" in bob_payload["phonetic_text"]
            assert "Ah-jeez" not in bob_payload["phonetic_text"]
        finally:
            session.close()


def _build_sample_text() -> str:
    return (
        "The old chronicle started with a single scene.\n"
        "\"Alice heard the Aegis ring in the tower's deep calm,\" Alice said. "
        "\"Bob heard the same Aegis echo through the gate,\" Bob said."
    )
