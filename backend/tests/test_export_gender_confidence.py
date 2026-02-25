import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_export_gender_confidence.db"

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
