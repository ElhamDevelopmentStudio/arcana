import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_acceptance_pronunciation_preview_correctness.db"

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

    db_file = Path("test_nipe_acceptance_pronunciation_preview_correctness.db")
    if db_file.exists():
        db_file.unlink()


def test_acceptance_pronunciation_substitution_preview_correctness() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "ACC-003 Pronunciation Preview"})
        assert project_resp.status_code == 201
        project_id = int(project_resp.json()["id"])

        global_resp = client.put(
            f"/api/projects/{project_id}/pronunciation-dictionary/global",
            json={"entries": [{"term": "Nimble", "verbalized_form": "Nim-ble", "confidence": 1.0}]},
        )
        assert global_resp.status_code == 200

        place_resp = client.put(
            f"/api/projects/{project_id}/pronunciation-dictionary/places",
            json={"entries": [{"term": "Atlantis", "verbalized_form": "At-Lan-tis", "confidence": 1.0}]},
        )
        assert place_resp.status_code == 200

        artifact_resp = client.put(
            f"/api/projects/{project_id}/pronunciation-dictionary/artifacts",
            json={"entries": [{"term": "Aegis", "verbalized_form": "EE-gis", "confidence": 1.0}]},
        )
        assert artifact_resp.status_code == 200

        invented_resp = client.put(
            f"/api/projects/{project_id}/pronunciation-dictionary/invented",
            json={"entries": [{"term": "Avernus", "verbalized_form": "Ah-vernus", "confidence": 1.0}]},
        )
        assert invented_resp.status_code == 200

        character_resp = client.put(
            f"/api/projects/{project_id}/pronunciation-dictionary/character/Alice",
            json={"entries": [{"term": "Alice", "verbalized_form": "Al-iss", "confidence": 1.0}]},
        )
        assert character_resp.status_code == 200

        preview_resp = client.post(
            f"/api/projects/{project_id}/pronunciation-dictionary/preview",
            json={
                "text": "Nimble and Atlantis meet Alice in Aegis and Avernus.",
                "character_name": "Alice",
                "include_global_scope": True,
                "include_character_scope": True,
                "include_place_scope": True,
                "include_artifact_scope": True,
                "include_invented_scope": True,
            },
        )
        assert preview_resp.status_code == 200
        payload = preview_resp.json()

        assert payload["before"] == "Nimble and Atlantis meet Alice in Aegis and Avernus."
        assert payload["after"] == "Nim-ble and At-Lan-tis meet Al-iss in EE-gis and Ah-vernus."
        assert payload["included_scopes"] == ["global", "character", "place", "artifact", "invented"]
        assert payload["warnings"] == []

        replacements = payload["replacements"]
        assert len(replacements) == 5
        by_term = {item["term"]: item for item in replacements}
        assert by_term["Nimble"]["verbalized_form"] == "Nim-ble"
        assert by_term["Nimble"]["scope"] == "global"
        assert by_term["Atlantis"]["verbalized_form"] == "At-Lan-tis"
        assert by_term["Atlantis"]["scope"] == "place"
        assert by_term["Alice"]["verbalized_form"] == "Al-iss"
        assert by_term["Alice"]["scope"] == "character"
        assert by_term["Aegis"]["verbalized_form"] == "EE-gis"
        assert by_term["Aegis"]["scope"] == "artifact"
        assert by_term["Avernus"]["verbalized_form"] == "Ah-vernus"
        assert by_term["Avernus"]["scope"] == "invented"
        assert all(int(item["count"]) == 1 for item in replacements)

