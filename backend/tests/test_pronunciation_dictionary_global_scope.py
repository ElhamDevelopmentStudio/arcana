import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipg_global_scope.db"

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

    db_file = Path("test_nipg_global_scope.db")
    if db_file.exists():
        db_file.unlink()


def test_integration_global_pronunciation_dictionary_set_and_list() -> None:
    sample_entries = [
        {
            "term": "Aegis",
            "verbalized_form": "EE-jis",
            "source": "user",
            "confidence": 1.0,
        },
        {"term": "Rook", "verbalized_form": "Rūk", "confidence": 0.9},
    ]

    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Global Pronunciation Dictionary"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        put_resp = client.put(
            f"/api/projects/{project_id}/pronunciation-dictionary/global",
            json={"entries": sample_entries},
        )
        assert put_resp.status_code == 200
        payload = put_resp.json()
        assert payload["project_id"] == project_id
        assert payload["scope"] == "global"
        assert len(payload["entries"]) == 2

        get_resp = client.get(f"/api/projects/{project_id}/pronunciation-dictionary/global")
        assert get_resp.status_code == 200
        listed = get_resp.json()
        assert listed["scope"] == "global"
        terms = {item["term"] for item in listed["entries"]}
        assert terms == {"Aegis", "Rook"}


def test_integration_place_pronunciation_dictionary_set_and_list() -> None:
    sample_entries = [
        {
            "term": "Narnia",
            "verbalized_form": "Nar-nia",
            "source": "user",
            "confidence": 1.0,
        },
    ]

    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Place Pronunciation Dictionary"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        put_resp = client.put(
            f"/api/projects/{project_id}/pronunciation-dictionary/places",
            json={"entries": sample_entries},
        )
        assert put_resp.status_code == 200
        payload = put_resp.json()
        assert payload["project_id"] == project_id
        assert payload["scope"] == "place"
        assert len(payload["entries"]) == 1

        get_resp = client.get(f"/api/projects/{project_id}/pronunciation-dictionary/places")
        assert get_resp.status_code == 200
        listed = get_resp.json()
        assert listed["scope"] == "place"
        assert listed["entries"][0]["term"] == "Narnia"


def test_integration_artifact_pronunciation_dictionary_set_and_list() -> None:
    sample_entries = [
        {
            "term": "phylactery",
            "verbalized_form": "artefact-phrase",
            "source": "user",
            "confidence": 1.0,
        },
    ]

    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Artifact Pronunciation Dictionary"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        put_resp = client.put(
            f"/api/projects/{project_id}/pronunciation-dictionary/artifacts",
            json={"entries": sample_entries},
        )
        assert put_resp.status_code == 200
        payload = put_resp.json()
        assert payload["project_id"] == project_id
        assert payload["scope"] == "artifact"
        assert len(payload["entries"]) == 1

        get_resp = client.get(f"/api/projects/{project_id}/pronunciation-dictionary/artifacts")
        assert get_resp.status_code == 200
        listed = get_resp.json()
        assert listed["scope"] == "artifact"
        assert listed["entries"][0]["term"] == "phylactery"


def test_integration_global_pronunciation_dictionary_applies_to_pipeline() -> None:
    text_payload = b"Chapter 1\nThe Aegis hung in the sky, and the crew praised it."

    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Global Pronunciation Pipeline"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": ("sample.txt", io.BytesIO(text_payload), "text/plain"),
            },
        )
        assert ingest_resp.status_code == 200

        dict_resp = client.put(
            f"/api/projects/{project_id}/pronunciation-dictionary/global",
            json={"entries": [{"term": "Aegis", "verbalized_form": "EE-jis", "confidence": 1.0}]},
        )
        assert dict_resp.status_code == 200

        run_payload = {
            "max_segment_chars": 255,
            "llm_enabled": False,
            "provider_name": "openrouter",
            "max_calls_per_day": 2,
        }
        run_resp = client.post(f"/api/projects/{project_id}/runs", json=run_payload)
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        session = get_session_factory()()
        try:
            segment_rows = (
                session.query(Segment).filter(Segment.run_id == run_id).all()
            )
            assert len(segment_rows) >= 1
            segment_payloads = [row.segment_json for row in segment_rows]
            assert any("EE-jis" in payload["phonetic_text"] for payload in segment_payloads)
            assert all("Aegis" in payload["original_text"] for payload in segment_payloads)
        finally:
            session.close()


def test_integration_place_pronunciation_dictionary_applies_to_pipeline() -> None:
    text_payload = b"Chapter 1\nWe traveled to Narnia and crossed the moonlit border."

    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Place Pronunciation Pipeline"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", io.BytesIO(text_payload), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        dict_resp = client.put(
            f"/api/projects/{project_id}/pronunciation-dictionary/places",
            json={"entries": [{"term": "Narnia", "verbalized_form": "Nar-nia", "confidence": 1.0}]},
        )
        assert dict_resp.status_code == 200

        run_payload = {
            "max_segment_chars": 255,
            "llm_enabled": False,
            "provider_name": "openrouter",
            "max_calls_per_day": 2,
        }
        run_resp = client.post(f"/api/projects/{project_id}/runs", json=run_payload)
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        session = get_session_factory()()
        try:
            segment_rows = session.query(Segment).filter(Segment.run_id == run_id).all()
            segment_payloads = [row.segment_json for row in segment_rows]
            assert any("Nar-nia" in payload["phonetic_text"] for payload in segment_payloads)
            assert all("Narnia" in payload["original_text"] for payload in segment_payloads)
        finally:
            session.close()


def test_integration_artifact_pronunciation_dictionary_applies_to_pipeline() -> None:
    text_payload = b"Chapter 1\nA phylactery hummed beside the altar."

    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Artifact Pronunciation Pipeline"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", io.BytesIO(text_payload), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        dict_resp = client.put(
            f"/api/projects/{project_id}/pronunciation-dictionary/artifacts",
            json={"entries": [{"term": "phylactery", "verbalized_form": "artefact-phrase", "confidence": 1.0}]},
        )
        assert dict_resp.status_code == 200

        run_payload = {
            "max_segment_chars": 255,
            "llm_enabled": False,
            "provider_name": "openrouter",
            "max_calls_per_day": 2,
        }
        run_resp = client.post(f"/api/projects/{project_id}/runs", json=run_payload)
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        session = get_session_factory()()
        try:
            segment_rows = session.query(Segment).filter(Segment.run_id == run_id).all()
            segment_payloads = [row.segment_json for row in segment_rows]
            assert any("artefact-phrase" in payload["phonetic_text"] for payload in segment_payloads)
            assert all("phylactery" in payload["original_text"] for payload in segment_payloads)
        finally:
            session.close()
