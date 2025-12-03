import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_gender_comparison_api.db"

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

    db_file = Path("test_nipe_gender_comparison_api.db")
    if db_file.exists():
        db_file.unlink()


def test_integration_gender_comparison_endpoint_reports_conflicts() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Gender Comparison Endpoint"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

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
                        "gender": "unknown",
                        "confidence": 1.0,
                        "inferred_gender": "female",
                        "inferred_confidence": 0.76,
                        "inferred_source_trace": [],
                    },
                    {
                        "name": "Rin",
                        "verbalized_form": "Rin",
                        "gender": "custom",
                        "confidence": 1.0,
                        "inferred_gender": "female",
                        "inferred_confidence": 0.61,
                        "inferred_source_trace": [],
                    },
                ]
            },
        )
        assert upsert_resp.status_code == 200

        compare_resp = client.get(f"/api/projects/{project_id}/characters/gender-comparison")
        assert compare_resp.status_code == 200
        body = compare_resp.json()
        assert body["project_id"] == project_id
        assert body["comparison_count"] == 3
        assert body["contradiction_count"] == 1

        by_name = {entry["name"]: entry for entry in body["comparisons"]}
        assert by_name["Nia"]["comparison"] == "conflict"
        assert by_name["Nia"]["is_contradiction"] is True
        assert by_name["Nia"]["contradiction_severity"] == 0.955
        assert by_name["Kai"]["comparison"] == "manual_unknown"
        assert by_name["Rin"]["comparison"] == "manual_custom"

        only_conflicts_resp = client.get(
            f"/api/projects/{project_id}/characters/gender-comparison?include_only_conflicts=true"
        )
        assert only_conflicts_resp.status_code == 200
        only_conflicts_body = only_conflicts_resp.json()
        assert only_conflicts_body["comparison_count"] == 1
        assert only_conflicts_body["contradiction_count"] == 1
        assert [entry["name"] for entry in only_conflicts_body["comparisons"]] == ["Nia"]
