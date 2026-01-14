import io
import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_voice_map_snapshots.db"
os.environ["LLM_PROVIDER_PRIORITY_ORDER"] = '["openrouter", "siliconflow", "groq"]'

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Character, CharacterVoiceMap, Run, VoiceMapSnapshot


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_voice_map_snapshots.db")
    if db_file.exists():
        db_file.unlink()


def _ingest_project_text(project_title: str, source_payload: str) -> int:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": project_title})
        assert project_resp.status_code == 201
        project_id = int(project_resp.json()["id"])

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("story.txt", io.BytesIO(source_payload.encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200
        assert ingest_resp.json()["chapter_count"] == 1
    return project_id


def _set_character_voice_map(*, project_id: int, character_name: str, voice_id: str) -> None:
    session = get_session_factory()()
    try:
        character = (
            session.query(Character)
            .filter(Character.project_id == project_id, Character.name == character_name)
            .one()
        )
        map_entry = (
            session.query(CharacterVoiceMap)
            .filter(
                CharacterVoiceMap.project_id == project_id,
                CharacterVoiceMap.character_id == character.id,
            )
            .one_or_none()
        )
        if map_entry is None:
            session.add(
                CharacterVoiceMap(
                    project_id=project_id,
                    character_id=character.id,
                    voice_id=voice_id,
                )
            )
        else:
            map_entry.voice_id = voice_id
        session.commit()
    finally:
        session.close()


def test_voice_map_snapshots_track_voice_assignments_with_version_and_source() -> None:
    with TestClient(app) as client:
        project_id = _ingest_project_text(
            project_title="Voice Map Snapshot Mutation Project",
            source_payload=(
                "Chapter 1\n"
                "Ada whispered to Beto about routes.\n"
                "Beto answered quietly."
            ),
        )

        import_payload = [
            {
                "name": "Ada",
                "verbalized_form": "Ada",
                "gender": "female",
                "aliases": [],
                "notes": None,
                "source": "manual",
                "confidence": 1.0,
                "inferred_gender": "female",
                "inferred_confidence": 1.0,
                "inferred_source_trace": [],
            },
            {
                "name": "Beto",
                "verbalized_form": "Beto",
                "gender": "male",
                "aliases": [],
                "notes": None,
                "source": "manual",
                "confidence": 1.0,
                "inferred_gender": "male",
                "inferred_confidence": 1.0,
                "inferred_source_trace": [],
            },
        ]
        import_resp = client.post(
            f"/api/projects/{project_id}/characters/import",
            files={"file": ("characters.json", io.BytesIO(json.dumps(import_payload).encode("utf-8")), "application/json")},
        )
        assert import_resp.status_code == 200

        upsert_one_resp = client.put(
            f"/api/projects/{project_id}/characters",
            json={
                "characters": [
                    {
                        "name": "Ada",
                        "verbalized_form": "Ada",
                        "gender": "female",
                        "voice_id": "ada_voice_v1",
                    },
                    {
                        "name": "Beto",
                        "verbalized_form": "Beto",
                        "gender": "male",
                    },
                ]
            },
        )
        assert upsert_one_resp.status_code == 200

        upsert_two_resp = client.put(
            f"/api/projects/{project_id}/characters",
            json={
                "characters": [
                    {
                        "name": "Ada",
                        "verbalized_form": "Ada",
                        "gender": "female",
                        "voice_id": "ada_voice_v2",
                    },
                    {
                        "name": "Beto",
                        "verbalized_form": "Beto",
                        "gender": "male",
                        "voice_id": "beto_voice_v2",
                    },
                ]
            },
        )
        assert upsert_two_resp.status_code == 200

    session = get_session_factory()()
    try:
        snapshots = (
            session.query(VoiceMapSnapshot)
            .filter(VoiceMapSnapshot.project_id == project_id)
            .order_by(VoiceMapSnapshot.version.asc())
            .all()
        )
        assert [snapshot.version for snapshot in snapshots] == [1, 2, 3]
        assert [snapshot.source for snapshot in snapshots] == ["import", "upsert", "upsert"]
        latest = snapshots[-1]
        assert latest.snapshot_json["character_count"] == 2
        assert latest.snapshot_json["explicit_character_voice_map_count"] == 0
        by_name = {
            entry["name"]: entry for entry in latest.snapshot_json["mappings"]
        }
        assert by_name["Ada"]["voice_id"] == "ada_voice_v2"
        assert by_name["Ada"]["voice_source"] == "character_voice_id"
        assert by_name["Beto"]["voice_id"] == "beto_voice_v2"
        assert by_name["Beto"]["voice_source"] == "character_voice_id"
    finally:
        session.close()


def test_run_creation_captures_current_voice_map_snapshot() -> None:
    with TestClient(app) as client:
        project_id = _ingest_project_text(
            project_title="Run Capture Voice Map Project",
            source_payload="Chapter 1\nAda answered softly.",
        )
        upsert_resp = client.put(
            f"/api/projects/{project_id}/characters",
            json={
                "characters": [
                    {
                        "name": "Ada",
                        "verbalized_form": "Ada",
                        "gender": "female",
                        "voice_id": "legacy_ada_voice",
                    }
                ]
            },
        )
        assert upsert_resp.status_code == 200
        _set_character_voice_map(
            project_id=project_id,
            character_name="Ada",
            voice_id="mapped_ada_voice",
        )

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"allow_unfinalized_character_map": True},
        )
        assert run_resp.status_code == 200
        run_id = int(run_resp.json()["run_id"])

    session = get_session_factory()()
    try:
        run = session.query(Run).filter(Run.id == run_id).one()
        snapshot = session.query(VoiceMapSnapshot).filter(
            VoiceMapSnapshot.run_id == run.id
        ).one()

        assert snapshot.source == "run_capture"
        assert run.config_json["voice_map_snapshot_id"] == snapshot.id
        assert run.config_json["voice_map_snapshot_version"] == snapshot.version
        assert run.config_json["voice_map_snapshot_version"] == snapshot.version == 2

        by_name = {entry["name"]: entry for entry in snapshot.snapshot_json["mappings"]}
        assert by_name["Ada"]["voice_id"] == "mapped_ada_voice"
        assert by_name["Ada"]["voice_source"] == "character_voice_map"
    finally:
        session.close()


def test_run_capture_versions_follow_edits_to_voice_map() -> None:
    with TestClient(app) as client:
        project_id = _ingest_project_text(
            project_title="Run Capture Voice Map Timeline",
            source_payload="Chapter 1\nNora and Ada met under dusk.",
        )

        client.put(
            f"/api/projects/{project_id}/characters",
            json={
                "characters": [
                    {
                        "name": "Nora",
                        "verbalized_form": "Nora",
                        "gender": "female",
                        "voice_id": "nora_voice_v1",
                    }
                ]
            },
        )
        first_run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"allow_unfinalized_character_map": True},
        )
        assert first_run_resp.status_code == 200
        first_run_id = int(first_run_resp.json()["run_id"])

        client.put(
            f"/api/projects/{project_id}/characters",
            json={
                "characters": [
                    {
                        "name": "Nora",
                        "verbalized_form": "Nora",
                        "gender": "female",
                        "voice_id": "nora_voice_v2",
                    }
                ]
            },
        )
        second_run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"allow_unfinalized_character_map": True},
        )
        assert second_run_resp.status_code == 200
        second_run_id = int(second_run_resp.json()["run_id"])

    session = get_session_factory()()
    try:
        first_snapshot = session.query(VoiceMapSnapshot).filter(
            VoiceMapSnapshot.run_id == first_run_id
        ).one()
        second_snapshot = session.query(VoiceMapSnapshot).filter(
            VoiceMapSnapshot.run_id == second_run_id
        ).one()

        assert second_snapshot.version > first_snapshot.version
        assert second_snapshot.version == first_snapshot.version + 2
    finally:
        session.close()
