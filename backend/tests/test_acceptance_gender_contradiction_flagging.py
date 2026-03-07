import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_acceptance_gender_contradiction_flagging.db"

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

    db_file = Path("test_nipe_acceptance_gender_contradiction_flagging.db")
    if db_file.exists():
        db_file.unlink()


def test_acceptance_gender_contradiction_detection_and_flagging() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "ACC-007 Gender Contradiction"})
        assert project_resp.status_code == 201
        project_id = int(project_resp.json()["id"])

        upsert_resp = client.put(
            f"/api/projects/{project_id}/characters",
            json={
                "characters": [
                    {
                        "name": "Nia",
                        "verbalized_form": "Nia",
                        "gender": "male",
                        "confidence": 1.0,
                        "inferred_gender": "female",
                        "inferred_confidence": 0.91,
                        "inferred_source_trace": [],
                    },
                    {
                        "name": "Kai",
                        "verbalized_form": "Kai",
                        "gender": "female",
                        "confidence": 1.0,
                        "inferred_gender": "female",
                        "inferred_confidence": 0.89,
                        "inferred_source_trace": [],
                    },
                ]
            },
        )
        assert upsert_resp.status_code == 200

        comparison_resp = client.get(f"/api/projects/{project_id}/characters/gender-comparison")
        assert comparison_resp.status_code == 200
        payload = comparison_resp.json()

        assert payload["comparison_count"] == 2
        assert payload["contradiction_count"] == 1
        assert isinstance(payload.get("warnings"), list)
        assert len(payload["warnings"]) == 1
        warning = payload["warnings"][0]
        assert warning["type"] == "manual_inferred_gender_contradiction"
        assert warning["character_name"] == "Nia"
        assert warning["requires_review"] is True
        assert warning["contradiction_severity"] > 0

        by_name = {entry["name"]: entry for entry in payload["comparisons"]}
        assert by_name["Nia"]["is_contradiction"] is True
        assert by_name["Nia"]["requires_review"] is True
        assert by_name["Nia"]["contradiction_severity"] > 0
        assert by_name["Kai"]["is_contradiction"] is False
        assert by_name["Kai"]["requires_review"] is False

