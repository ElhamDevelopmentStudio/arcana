import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_acceptance_character_map_edit_fields.db"

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

    db_file = Path("test_nipe_acceptance_character_map_edit_fields.db")
    if db_file.exists():
        db_file.unlink()


def test_acceptance_character_map_edit_supports_name_verbalized_gender_fields() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "ACC-002 Character Map Edit"})
        assert project_resp.status_code == 201
        project_id = int(project_resp.json()["id"])

        initial_upsert_resp = client.put(
            f"/api/projects/{project_id}/characters",
            json={
                "characters": [
                    {
                        "name": "Sunny",
                        "verbalized_form": "Sun-ee",
                        "gender": "male",
                        "aliases": ["Sun"],
                        "source": "manual",
                        "confidence": 1.0,
                    },
                    {
                        "name": "Nephis",
                        "verbalized_form": "Nee-fis",
                        "gender": "female",
                        "aliases": [],
                        "source": "manual",
                        "confidence": 1.0,
                    },
                ]
            },
        )
        assert initial_upsert_resp.status_code == 200

        edited_upsert_resp = client.put(
            f"/api/projects/{project_id}/characters",
            json={
                "characters": [
                    {
                        "name": "Sunny",
                        "verbalized_form": "Sunny",
                        "gender": "female",
                        "aliases": ["Sun"],
                        "source": "manual",
                        "confidence": 1.0,
                    },
                    {
                        "name": "Nephis",
                        "verbalized_form": "Nef-is",
                        "gender": "female",
                        "aliases": [],
                        "source": "manual",
                        "confidence": 1.0,
                    },
                ]
            },
        )
        assert edited_upsert_resp.status_code == 200
        edited_payload = edited_upsert_resp.json()
        assert edited_payload["character_map_finalized"] is False

        sunny_edited = next(
            (character for character in edited_payload["characters"] if character["name"] == "Sunny"),
            None,
        )
        assert sunny_edited is not None
        assert sunny_edited["name"] == "Sunny"
        assert sunny_edited["verbalized_form"] == "Sunny"
        assert sunny_edited["gender"] == "female"

        list_resp = client.get(f"/api/projects/{project_id}/characters")
        assert list_resp.status_code == 200
        list_payload = list_resp.json()
        sunny_listed = next(
            (character for character in list_payload["characters"] if character["name"] == "Sunny"),
            None,
        )
        assert sunny_listed is not None
        assert sunny_listed["name"] == "Sunny"
        assert sunny_listed["verbalized_form"] == "Sunny"
        assert sunny_listed["gender"] == "female"

