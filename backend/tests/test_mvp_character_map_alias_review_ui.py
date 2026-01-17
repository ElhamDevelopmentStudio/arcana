import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_mvp_character_map_alias_review_ui.db"

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

    db_file = Path("test_nipe_mvp_character_map_alias_review_ui.db")
    if db_file.exists():
        db_file.unlink()


def _sample_txt() -> str:
    return (
        "Chapter 1\n"
        "Alice watched the harbor lights.\n\n"
        "Chapter 2\n"
        "Bob opened the old gate."
    )


def test_acceptance_character_map_supports_aliases_and_review_workflow() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "MVP Character Map Aliases + Review"})
        assert project_resp.status_code == 201
        project_id = int(project_resp.json()["id"])

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("novel.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        save_resp = client.put(
            f"/api/projects/{project_id}/characters",
            json={
                "characters": [
                    {
                        "name": "Alice",
                        "verbalized_form": "Alice",
                        "gender": "female",
                        "aliases": ["Al", "Ace"],
                        "notes": "Lead role",
                        "source": "manual",
                        "confidence": 1.0,
                    },
                    {
                        "name": "Bob",
                        "verbalized_form": "Bob",
                        "gender": "male",
                        "aliases": ["Bobby"],
                        "notes": None,
                        "source": "manual",
                        "confidence": 1.0,
                    },
                ]
            },
        )
        assert save_resp.status_code == 200
        save_payload = save_resp.json()
        assert save_payload["character_map_finalized"] is False
        by_name = {entry["name"]: entry for entry in save_payload["characters"]}
        assert set(by_name["Alice"]["aliases"]) == {"Al", "Ace"}
        assert set(by_name["Bob"]["aliases"]) == {"Bobby"}

        lookup_resp = client.post(
            f"/api/projects/{project_id}/characters/lookup-alias",
            json={"alias": "Ace"},
        )
        assert lookup_resp.status_code == 200
        lookup_payload = lookup_resp.json()
        assert lookup_payload["canonical_name"] == "Alice"

        finalize_resp = client.post(f"/api/projects/{project_id}/characters/finalize")
        assert finalize_resp.status_code == 200
        assert finalize_resp.json()["character_map_finalized"] is True

        character_map_resp = client.get(f"/api/projects/{project_id}/characters")
        assert character_map_resp.status_code == 200
        assert character_map_resp.json()["character_map_finalized"] is True
