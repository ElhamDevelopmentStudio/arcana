import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_voice_map_precedence.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Character, CharacterVoiceMap


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_voice_map_precedence.db")
    if db_file.exists():
        db_file.unlink()


def _create_project_with_dialogue_and_character(client: TestClient, character_name: str) -> int:
    create_resp = client.post("/api/projects", json={"title": "Character Voice Map Precedence"})
    assert create_resp.status_code == 201
    project_id = create_resp.json()["id"]

    ingest_resp = client.post(
        f"/api/projects/{project_id}/ingest/txt",
        files={
            "file": (
                "novel.txt",
                io.BytesIO(f'Chapter 1\n"Hello, there," {character_name} said.'.encode("utf-8")),
                "text/plain",
            )
        },
    )
    assert ingest_resp.status_code == 200

    upsert_resp = client.put(
        f"/api/projects/{project_id}/characters",
        json={
            "characters": [
                {
                    "name": character_name,
                    "verbalized_form": character_name,
                    "gender": "male",
                    "aliases": [],
                    "notes": None,
                    "source": "manual",
                    "confidence": 1.0,
                    "inferred_gender": "male",
                    "inferred_confidence": 1.0,
                    "inferred_source_trace": [],
                }
            ]
        },
    )
    assert upsert_resp.status_code == 200
    return project_id


def _set_character_voice(
    *,
    project_id: int,
    character_name: str,
    legacy_voice: str,
    map_voice: str | None = None,
) -> None:
    session = get_session_factory()()
    try:
        character = (
            session.query(Character)
            .filter(Character.project_id == project_id, Character.name == character_name)
            .one()
        )
        character.voice_id = legacy_voice

        if map_voice is not None:
            session.add(
                CharacterVoiceMap(
                    project_id=project_id,
                    character_id=character.id,
                    voice_id=map_voice,
                )
            )

        session.commit()
    finally:
        session.close()


def _run_and_get_voice_ids(project_id: int, client: TestClient) -> list[str]:
    run_resp = client.post(
        f"/api/projects/{project_id}/runs",
        json={"allow_unfinalized_character_map": True},
    )
    assert run_resp.status_code == 200
    run_id = run_resp.json()["run_id"]

    export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
    assert export_resp.status_code == 200

    return [segment["voice_id"] for segment in export_resp.json()["segments"]]


def _run_and_get_segment_payloads(project_id: int, client: TestClient) -> list[dict]:
    run_resp = client.post(
        f"/api/projects/{project_id}/runs",
        json={"allow_unfinalized_character_map": True},
    )
    assert run_resp.status_code == 200
    run_id = run_resp.json()["run_id"]

    export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
    assert export_resp.status_code == 200

    return export_resp.json()["segments"]


def test_integration_run_prefers_voice_map_voice_id_over_legacy_field() -> None:
    with TestClient(app) as client:
        project_id = _create_project_with_dialogue_and_character(client=client, character_name="Lena")
        _set_character_voice(
            project_id=project_id,
            character_name="Lena",
            legacy_voice="legacy_lena_voice",
            map_voice="mapped_lena_voice",
        )

        segment_voice_ids = _run_and_get_voice_ids(project_id=project_id, client=client)

        assert segment_voice_ids
        assert any(voice_id == "mapped_lena_voice" for voice_id in segment_voice_ids)


def test_integration_run_uses_legacy_voice_id_when_no_voice_map_exists() -> None:
    with TestClient(app) as client:
        project_id = _create_project_with_dialogue_and_character(client=client, character_name="Orin")
        _set_character_voice(
            project_id=project_id,
            character_name="Orin",
            legacy_voice="legacy_orin_voice",
            map_voice=None,
        )

        segment_voice_ids = _run_and_get_voice_ids(project_id=project_id, client=client)

        assert segment_voice_ids
        assert any(voice_id == "legacy_orin_voice" for voice_id in segment_voice_ids)


def test_integration_run_uses_character_map_voice_override_field() -> None:
    expected_voice = " inline_override_voice "
    with TestClient(app) as client:
        project_id = _create_project_with_dialogue_and_character(client=client, character_name="Vera")
        upsert_resp = client.put(
            f"/api/projects/{project_id}/characters",
            json={
                "characters": [
                    {
                        "name": "Vera",
                        "verbalized_form": "Vera",
                        "gender": "female",
                        "voice_id": expected_voice,
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
        assert upsert_resp.status_code == 200
        assert upsert_resp.json()["characters"][0]["voice_id"] == expected_voice.strip()

        list_resp = client.get(f"/api/projects/{project_id}/characters")
        assert list_resp.status_code == 200
        assert list_resp.json()["characters"][0]["voice_id"] == expected_voice.strip()

        segment_voice_ids = _run_and_get_voice_ids(project_id=project_id, client=client)

    assert segment_voice_ids
    assert any(voice_id == expected_voice.strip() for voice_id in segment_voice_ids)


def test_integration_dialogue_segments_emit_resolved_voice_output() -> None:
    resolved_voice = "resolved_voice_for_test"
    with TestClient(app) as client:
        project_id = _create_project_with_dialogue_and_character(client=client, character_name="Iris")
        _set_character_voice(
            project_id=project_id,
            character_name="Iris",
            legacy_voice="legacy_iris_voice",
            map_voice=resolved_voice,
        )

        segments = _run_and_get_segment_payloads(project_id=project_id, client=client)
        assert all("resolved_voice_id" in segment for segment in segments)

        dialogue_segments = [segment for segment in segments if segment["type"] == "dialogue"]
        assert dialogue_segments

        first_dialogue = dialogue_segments[0]
        assert first_dialogue["voice_id"] == resolved_voice
        assert first_dialogue["resolved_voice_id"] == resolved_voice
        assert first_dialogue["resolved_voice_id"] == first_dialogue["voice_id"]
        assert isinstance(first_dialogue["speaker_id"], int)
        assert first_dialogue["speaker_id"] > 0
        assert first_dialogue["gender"] == "male"
