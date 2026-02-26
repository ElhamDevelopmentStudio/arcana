import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_character_map_snapshots.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import CharacterMapSnapshot, Run


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_character_map_snapshots.db")
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


def test_character_map_snapshots_track_mutations_with_version_and_source() -> None:
    with TestClient(app) as client:
        project_id = _ingest_project_text(
            project_title="Snapshot Mutation Project",
            source_payload=(
                "Chapter 1\n"
                "Alice crossed the river.\n"
                "She looked at Bob and said hello."
            ),
        )

        import_resp = client.post(
            f"/api/projects/{project_id}/characters/import",
            files={
                "file": (
                    "characters.json",
                    io.BytesIO(
                        b'['
                        b'{"name":"Alice","verbalized_form":"Alice","gender":"female"},'
                        b'{"name":"Bob","verbalized_form":"Bob","gender":"male"}'
                        b"]"
                    ),
                    "application/json",
                )
            },
        )
        assert import_resp.status_code == 200

        infer_resp = client.post(f"/api/projects/{project_id}/characters/infer")
        assert infer_resp.status_code == 200

        upsert_resp = client.put(
            f"/api/projects/{project_id}/characters",
            json={
                "characters": [
                    {
                        "name": "Alice",
                        "verbalized_form": "Alice",
                        "gender": "female",
                    },
                    {
                        "name": "Cara",
                        "verbalized_form": "Cara",
                        "gender": "female",
                    },
                ]
            },
        )
        assert upsert_resp.status_code == 200

    session = get_session_factory()()
    try:
        snapshots = (
            session.query(CharacterMapSnapshot)
            .filter(CharacterMapSnapshot.project_id == project_id)
            .order_by(CharacterMapSnapshot.version.asc())
            .all()
        )
        assert [snapshot.version for snapshot in snapshots] == [1, 2, 3]
        assert [snapshot.source for snapshot in snapshots] == [
            "import",
            "inferred_gender",
            "upsert",
        ]
        assert snapshots[-1].snapshot_json["character_count"] == 2
    finally:
        session.close()


def test_run_creation_captures_current_character_map_snapshot() -> None:
    with TestClient(app) as client:
        project_id = _ingest_project_text(
            project_title="Run Capture Snapshot Project",
            source_payload=(
                "Chapter 1\n"
                "Mara lifted the torch while Jonah watched."
            ),
        )
        import_resp = client.post(
            f"/api/projects/{project_id}/characters/import",
            files={
                "file": (
                    "characters.json",
                    io.BytesIO(
                        b'{'
                        b'"Mara":{"verbalized_form":"Mara","gender":"female"},'
                        b'"Jonah":{"verbalized_form":"Jonah","gender":"male"}'
                        b'}'
                    ),
                    "application/json",
                )
            },
        )
        assert import_resp.status_code == 200

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"allow_unfinalized_character_map": True},
        )
        assert run_resp.status_code == 200
        run_id = int(run_resp.json()["run_id"])

    session = get_session_factory()()
    try:
        run = session.query(Run).filter(Run.id == run_id).one()
        snapshot = session.query(CharacterMapSnapshot).filter(CharacterMapSnapshot.run_id == run.id).one()

        assert snapshot.source == "run_capture"
        assert run.config_json["character_map_snapshot_id"] == snapshot.id
        assert run.config_json["character_map_snapshot_version"] == snapshot.version
        assert snapshot.version == 2
    finally:
        session.close()


def test_run_capture_snapshots_use_latest_map_version_after_edits() -> None:
    with TestClient(app) as client:
        project_id = _ingest_project_text(
            project_title="Run Snapshot Timeline Project",
            source_payload=(
                "Chapter 1\n"
                "Nora met Selene by the gate."
            ),
        )
        import_resp = client.post(
            f"/api/projects/{project_id}/characters/import",
            files={
                "file": (
                    "characters.json",
                    io.BytesIO(
                        b'{'
                        b'"Nora":{"verbalized_form":"Nora","gender":"female"}'
                        b'}'
                    ),
                    "application/json",
                )
            },
        )
        assert import_resp.status_code == 200

        first_run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"allow_unfinalized_character_map": True},
        )
        assert first_run_resp.status_code == 200
        first_run_id = int(first_run_resp.json()["run_id"])

        upsert_resp = client.put(
            f"/api/projects/{project_id}/characters",
            json={
                "characters": [
                    {
                        "name": "Nora",
                        "verbalized_form": "Nora",
                        "gender": "female",
                    },
                    {
                        "name": "Rin",
                        "verbalized_form": "Rin",
                        "gender": "male",
                    },
                ]
            },
        )
        assert upsert_resp.status_code == 200

        second_run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"allow_unfinalized_character_map": True},
        )
        assert second_run_resp.status_code == 200
        second_run_id = int(second_run_resp.json()["run_id"])

    session = get_session_factory()()
    try:
        first_snapshot = session.query(CharacterMapSnapshot).filter(CharacterMapSnapshot.run_id == first_run_id).one()
        second_snapshot = session.query(CharacterMapSnapshot).filter(CharacterMapSnapshot.run_id == second_run_id).one()

        assert first_snapshot.version == 2
        assert second_snapshot.version == 4
        assert second_snapshot.version > first_snapshot.version
    finally:
        session.close()
