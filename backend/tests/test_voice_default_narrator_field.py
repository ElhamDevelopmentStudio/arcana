import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipc_voice_default_narrator.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Project
from app.services.voice import DEFAULT_VOICE_CONFIG, build_effective_voice_config


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipc_voice_default_narrator.db")
    if db_file.exists():
        db_file.unlink()


def test_project_has_default_narrator_voice_field_after_creation() -> None:
    with TestClient(app) as client:
        create_resp = client.post("/api/projects", json={"title": "Narrator Field Project"})
        assert create_resp.status_code == 201
        project_id = create_resp.json()["id"]

    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        assert project.default_narrator_voice == DEFAULT_VOICE_CONFIG["narrator_voice"]
        assert project.voice_config_json["narrator_voice"] == DEFAULT_VOICE_CONFIG["narrator_voice"]
    finally:
        session.close()


def test_project_has_all_default_voice_fields_after_creation() -> None:
    with TestClient(app) as client:
        create_resp = client.post("/api/projects", json={"title": "All Voice Defaults Project"})
        assert create_resp.status_code == 201
        project_id = create_resp.json()["id"]

    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        assert project.default_narrator_voice == DEFAULT_VOICE_CONFIG["narrator_voice"]
        assert project.default_male_voice == DEFAULT_VOICE_CONFIG["male_default_voice"]
        assert project.default_female_voice == DEFAULT_VOICE_CONFIG["female_default_voice"]
        assert project.default_neutral_voice == DEFAULT_VOICE_CONFIG["neutral_default_voice"]
        assert project.default_unknown_voice == DEFAULT_VOICE_CONFIG["unknown_default_voice"]
        assert project.voice_config_json == DEFAULT_VOICE_CONFIG
    finally:
        session.close()


def test_updating_voice_config_updates_default_narrator_voice_field() -> None:
    with TestClient(app) as client:
        create_resp = client.post("/api/projects", json={"title": "Narrator Update Project"})
        assert create_resp.status_code == 201
        project_id = create_resp.json()["id"]

        voices_payload = {
            "narrator_voice": "project_narrator_voice",
            "male_default_voice": "male_default_voice",
            "female_default_voice": "female_default_voice",
            "neutral_default_voice": "neutral_default_voice",
            "unknown_default_voice": "unknown_default_voice",
        }
        update_resp = client.put(f"/api/projects/{project_id}/voices", json=voices_payload)
        assert update_resp.status_code == 200
        assert update_resp.json()["voice_config"]["narrator_voice"] == "project_narrator_voice"

    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        assert project.default_narrator_voice == "project_narrator_voice"
        assert project.voice_config_json["narrator_voice"] == "project_narrator_voice"
    finally:
        session.close()


def test_updating_voice_config_updates_all_project_default_voice_fields() -> None:
    with TestClient(app) as client:
        create_resp = client.post("/api/projects", json={"title": "Update All Voice Defaults"})
        assert create_resp.status_code == 201
        project_id = create_resp.json()["id"]

        voices_payload = {
            "narrator_voice": "project_narrator_voice",
            "male_default_voice": "project_male_voice",
            "female_default_voice": "project_female_voice",
            "neutral_default_voice": "project_neutral_voice",
            "unknown_default_voice": "project_unknown_voice",
        }
        update_resp = client.put(f"/api/projects/{project_id}/voices", json=voices_payload)
        assert update_resp.status_code == 200
        assert update_resp.json()["voice_config"] == voices_payload

    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        assert project.default_narrator_voice == "project_narrator_voice"
        assert project.default_male_voice == "project_male_voice"
        assert project.default_female_voice == "project_female_voice"
        assert project.default_neutral_voice == "project_neutral_voice"
        assert project.default_unknown_voice == "project_unknown_voice"
    finally:
        session.close()


def test_build_effective_voice_config_prefers_project_default_voice_fields() -> None:
    effective_voice_config = build_effective_voice_config(
        {
            "narrator_voice": "legacy_narrator",
            "male_default_voice": "legacy_male",
            "female_default_voice": "legacy_female",
        },
        default_narrator_voice="project_narrator_voice",
        default_male_voice="project_male_voice",
        default_female_voice="project_female_voice",
        default_neutral_voice="project_neutral_voice",
        default_unknown_voice="project_unknown_voice",
    )

    assert effective_voice_config["narrator_voice"] == "project_narrator_voice"
    assert effective_voice_config["male_default_voice"] == "project_male_voice"
    assert effective_voice_config["female_default_voice"] == "project_female_voice"
    assert effective_voice_config["neutral_default_voice"] == "project_neutral_voice"
    assert effective_voice_config["unknown_default_voice"] == "project_unknown_voice"


def test_pipeline_uses_project_default_narrator_voice_field_for_narration_segments() -> None:
    with TestClient(app) as client:
        create_resp = client.post("/api/projects", json={"title": "Narrator Field Runtime"})
        assert create_resp.status_code == 201
        project_id = create_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": (
                    "novel.txt",
                    io.BytesIO("Chapter 1\nThe night wind moved quietly through the hall.".encode("utf-8")),
                    "text/plain",
                )
            },
        )
        assert ingest_resp.status_code == 200

    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        project.default_narrator_voice = "custom_runtime_narrator"
        session.commit()
    finally:
        session.close()

    with TestClient(app) as client:
        run_resp = client.post(f"/api/projects/{project_id}/runs", json={"max_segment_chars": 120})
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200

        export_payload = export_resp.json()
        assert export_payload["segments"]
        assert all(segment["voice_id"] == "custom_runtime_narrator" for segment in export_payload["segments"])
