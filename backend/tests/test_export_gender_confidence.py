import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_export_gender_confidence.db"

from app.config import clear_settings_cache
from app.database import get_session_factory
from app.database import init_db, reset_engine
from app.models import Character
from app.main import app


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_export_gender_confidence.db")
    if db_file.exists():
        db_file.unlink()


def _build_project_payload(
    client: TestClient,
    title: str,
    character_name: str,
    gender: str,
    confidence: float,
) -> int:
    project_resp = client.post("/api/projects", json={"title": title})
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    ingest_resp = client.post(
        f"/api/projects/{project_id}/ingest/txt",
        files={
            "file": (
                "novel.txt",
                io.BytesIO(f'Chapter 1\n"{character_name} spoke to you," {character_name} said.'.encode("utf-8")),
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
                    "gender": gender,
                    "confidence": confidence,
                    "inferred_gender": gender,
                    "inferred_confidence": confidence,
                    "inferred_source_trace": [],
                },
            ],
        },
    )
    assert upsert_resp.status_code == 200
    return project_id


def _run_and_export(project_id: int, client: TestClient) -> dict:
    run_resp = client.post(
        f"/api/projects/{project_id}/runs",
        json={"allow_unfinalized_character_map": True},
    )
    assert run_resp.status_code == 200
    run_id = run_resp.json()["run_id"]

    export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
    assert export_resp.status_code == 200

    return export_resp.json()


def _get_character_id(project_id: int, character_name: str) -> int:
    session = get_session_factory()()
    try:
        row = (
            session.query(Character)
            .filter(Character.project_id == project_id, Character.name == character_name)
            .one_or_none()
        )
        assert row is not None
        return row.id
    finally:
        session.close()


def _build_project_with_dialogue(
    client: TestClient,
    title: str,
    name: str,
    gender: str,
    confidence: float,
    dialogue_speaker: str,
) -> int:
    project_id = _build_project_payload(
        client=client,
        title=title,
        character_name=name,
        gender=gender,
        confidence=confidence,
    )

    update_resp = client.put(
        f"/api/projects/{project_id}/characters",
        json={
            "characters": [
                {
                    "name": name,
                    "verbalized_form": name,
                    "gender": gender,
                    "confidence": confidence,
                    "aliases": [dialogue_speaker] if dialogue_speaker != name else [],
                    "inferred_gender": gender,
                    "inferred_confidence": confidence,
                    "inferred_source_trace": [],
                },
            ],
        },
    )
    assert update_resp.status_code == 200

    ingest_resp = client.post(
        f"/api/projects/{project_id}/ingest/txt",
        files={
            "file": (
                "novel.txt",
                io.BytesIO(f'Chapter 1\n"{dialogue_speaker} called out," {dialogue_speaker} said.'.encode("utf-8")),
                "text/plain",
            )
        },
    )
    assert ingest_resp.status_code == 200

    return project_id


def test_export_includes_low_gender_confidence_for_unknown_gender() -> None:
    with TestClient(app) as client:
        project_id = _build_project_payload(
            client=client,
            title="Unknown Gender Export",
            character_name="Alex",
            gender="unknown",
            confidence=0.94,
        )

        payload = _run_and_export(project_id=project_id, client=client)

        assert payload["run_id"] is not None
        assert len(payload["segments"]) == 1
        assert payload["segments"][0]["speaker"] == "Alex"
        assert payload["segments"][0]["gender"] == "unknown"
        assert payload["segments"][0]["confidence"]["gender"] == 0.0


def test_export_includes_low_gender_confidence_for_neutral_gender() -> None:
    with TestClient(app) as client:
        project_id = _build_project_payload(
            client=client,
            title="Neutral Gender Export",
            character_name="Nia",
            gender="neutral",
            confidence=0.91,
        )

        payload = _run_and_export(project_id=project_id, client=client)

        assert payload["run_id"] is not None
        assert len(payload["segments"]) == 1
        assert payload["segments"][0]["speaker"] == "Nia"
        assert payload["segments"][0]["gender"] == "neutral"
        assert payload["segments"][0]["confidence"]["gender"] == 0.0


def test_export_includes_speaker_id_when_speaker_resolves() -> None:
    with TestClient(app) as client:
        project_id = _build_project_with_dialogue(
            client=client,
            title="Speaker ID Resolution Export",
            name="Alice",
            gender="female",
            confidence=0.93,
            dialogue_speaker="Ally",
        )
        payload = _run_and_export(project_id=project_id, client=client)

        export_segment = payload["segments"][0]
        assert export_segment["speaker"] == "Ally"
        assert isinstance(export_segment["speaker_id"], int)
        assert export_segment["speaker_id"] == _get_character_id(project_id=project_id, character_name="Alice")
        assert isinstance(export_segment["confidence"]["speaker"], (float, int))
        assert 0.0 <= float(export_segment["confidence"]["speaker"]) <= 1.0


def test_export_speaker_id_is_null_for_unresolved_speaker() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Unresolved Speaker Export"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": (
                    "novel.txt",
                    io.BytesIO('Chapter 1\n"Stay back," Echo spoke.'.encode("utf-8")),
                    "text/plain",
                )
            },
        )
        assert ingest_resp.status_code == 200

        payload = _run_and_export(project_id=project_id, client=client)

        assert payload["run_id"] is not None
        assert len(payload["segments"]) >= 1
        assert any(segment["speaker_id"] is None for segment in payload["segments"])
        for segment in payload["segments"]:
            if segment["speaker_id"] is None:
                assert "confidence" in segment
                assert "speaker" in segment["confidence"]
