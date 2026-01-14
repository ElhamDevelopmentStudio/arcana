import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_pronunciation_dictionary_snapshots.db"
os.environ["LLM_PROVIDER_PRIORITY_ORDER"] = '["openrouter", "siliconflow", "groq"]'

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import PronunciationDictionarySnapshot, Run


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_pronunciation_dictionary_snapshots.db")
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


def test_pronunciation_dictionary_snapshots_track_mutations_with_version_and_source() -> None:
    with TestClient(app) as client:
        project_id = _ingest_project_text(
            project_title="Pronunciation Snapshot Mutation Project",
            source_payload=(
                "Chapter 1\n"
                "Alice and Nia visited the port."
            ),
        )

        global_resp = client.put(
            f"/api/projects/{project_id}/pronunciation-dictionary/global",
            json={"entries": [{"term": "Aegis", "verbalized_form": "EE-jis", "source": "user", "confidence": 1.0}]},
        )
        assert global_resp.status_code == 200

        place_resp = client.put(
            f"/api/projects/{project_id}/pronunciation-dictionary/places",
            json={"entries": [{"term": "Narnia", "verbalized_form": "Nar-nia", "source": "user", "confidence": 1.0}]},
        )
        assert place_resp.status_code == 200

        character_resp = client.put(
            f"/api/projects/{project_id}/pronunciation-dictionary/character/Alice",
            json={"entries": [{"term": "ship", "verbalized_form": "ship", "source": "user", "confidence": 1.0}]},
        )
        assert character_resp.status_code == 200

    session = get_session_factory()()
    try:
        snapshots = (
            session.query(PronunciationDictionarySnapshot)
            .filter(PronunciationDictionarySnapshot.project_id == project_id)
            .order_by(PronunciationDictionarySnapshot.version.asc())
            .all()
        )
        assert [snapshot.version for snapshot in snapshots] == [1, 2, 3]
        assert [snapshot.source for snapshot in snapshots] == ["global", "place", "character"]
        assert snapshots[-1].snapshot_json["entry_count"] == 3
        assert snapshots[-1].snapshot_json["by_scope"]["global"] == [
            {
                "term": "Aegis",
                "verbalized_form": "EE-jis",
                "source": "user",
                "confidence": 1.0,
            },
        ]
        assert snapshots[-1].snapshot_json["by_scope"]["place"] == [
            {
                "term": "Narnia",
                "verbalized_form": "Nar-nia",
                "source": "user",
                "confidence": 1.0,
            },
        ]
        assert snapshots[-1].snapshot_json["by_scope"]["character"] == [
            {
                "term": "ship",
                "verbalized_form": "ship",
                "source": "user",
                "confidence": 1.0,
                "character_name": "Alice",
            },
        ]
    finally:
        session.close()


def test_run_creation_captures_current_pronunciation_dictionary_snapshot() -> None:
    with TestClient(app) as client:
        project_id = _ingest_project_text(
            project_title="Run Snapshot Pronunciation Project",
            source_payload="Chapter 1\nMara lifted the torch while Jonah watched.",
        )
        client.put(
            f"/api/projects/{project_id}/pronunciation-dictionary/global",
            json={"entries": [{"term": "Aegis", "verbalized_form": "EE-jis", "source": "user", "confidence": 1.0}]},
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
        snapshot = session.query(PronunciationDictionarySnapshot).filter(
            PronunciationDictionarySnapshot.run_id == run.id
        ).one()

        assert snapshot.source == "run_capture"
        assert run.config_json["pronunciation_dictionary_snapshot_id"] == snapshot.id
        assert run.config_json["pronunciation_dictionary_snapshot_version"] == snapshot.version
        assert snapshot.version == 2
    finally:
        session.close()


def test_run_capture_versions_follow_mutations_to_dictionary() -> None:
    with TestClient(app) as client:
        project_id = _ingest_project_text(
            project_title="Run Dictionary Version Growth",
            source_payload="Chapter 1\nNora met Selene by the gate.",
        )
        client.put(
            f"/api/projects/{project_id}/pronunciation-dictionary/global",
            json={"entries": [{"term": "Aegis", "verbalized_form": "EE-jis", "source": "user", "confidence": 1.0}]},
        )

        first_run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"allow_unfinalized_character_map": True},
        )
        assert first_run_resp.status_code == 200
        first_run_id = int(first_run_resp.json()["run_id"])

        client.put(
            f"/api/projects/{project_id}/pronunciation-dictionary/place",
            json={"entries": [{"term": "Narnia", "verbalized_form": "Nar-nia", "source": "user", "confidence": 1.0}]},
        )

        second_run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"allow_unfinalized_character_map": True},
        )
        assert second_run_resp.status_code == 200
        second_run_id = int(second_run_resp.json()["run_id"])

    session = get_session_factory()()
    try:
        first_snapshot = session.query(PronunciationDictionarySnapshot).filter(
            PronunciationDictionarySnapshot.run_id == first_run_id
        ).one()
        second_snapshot = session.query(PronunciationDictionarySnapshot).filter(
            PronunciationDictionarySnapshot.run_id == second_run_id
        ).one()

        assert first_snapshot.version == 2
        assert second_snapshot.version == 3
        assert second_snapshot.version > first_snapshot.version
    finally:
        session.close()
