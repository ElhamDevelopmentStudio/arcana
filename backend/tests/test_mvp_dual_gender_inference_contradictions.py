import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_mvp_dual_gender_inference_contradictions.db"

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

    db_file = Path("test_nipe_mvp_dual_gender_inference_contradictions.db")
    if db_file.exists():
        db_file.unlink()


def _sample_txt() -> str:
    return (
        "Chapter 1\n"
        "Nia stepped into the corridor. She tightened her grip on the blade.\n\n"
        "Chapter 2\n"
        "Kai paused, then he nodded toward the gate."
    )


def test_acceptance_dual_gender_system_supports_inference_and_contradiction_flags() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "MVP Dual Gender Inference + Contradictions"})
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
                        "name": "Nia",
                        "verbalized_form": "Nia",
                        "gender": "male",
                        "inferred_gender": "female",
                        "inferred_confidence": 0.94,
                        "aliases": ["N"],
                        "source": "manual",
                        "confidence": 1.0,
                    },
                    {
                        "name": "Kai",
                        "verbalized_form": "Kai",
                        "gender": "male",
                        "inferred_gender": "male",
                        "inferred_confidence": 0.91,
                        "aliases": ["K"],
                        "source": "manual",
                        "confidence": 1.0,
                    },
                ]
            },
        )
        assert save_resp.status_code == 200

        infer_resp = client.post(f"/api/projects/{project_id}/characters/infer")
        assert infer_resp.status_code == 200
        infer_payload = infer_resp.json()
        assert infer_payload["character_map_finalized"] is False
        inferred_rows = {entry["name"]: entry for entry in infer_payload["characters"]}
        assert inferred_rows["Nia"]["gender"] == "male"
        assert isinstance(inferred_rows["Nia"]["inferred_gender"], str)
        assert 0.0 <= float(inferred_rows["Nia"]["inferred_confidence"]) <= 1.0

        comparison_resp = client.get(f"/api/projects/{project_id}/characters/gender-comparison")
        assert comparison_resp.status_code == 200
        comparison_payload = comparison_resp.json()
        assert comparison_payload["comparison_count"] >= 2
        assert comparison_payload["contradiction_count"] >= 0
        assert len(comparison_payload["comparisons"]) == comparison_payload["comparison_count"]

        contradiction_rows = [entry for entry in comparison_payload["comparisons"] if entry["is_contradiction"]]
        assert len(contradiction_rows) == comparison_payload["contradiction_count"]

        by_name = {entry["name"]: entry for entry in comparison_payload["comparisons"]}
        assert by_name["Nia"]["manual_gender"] == "male"
        assert isinstance(by_name["Nia"]["inferred_gender"], str)
        assert isinstance(by_name["Nia"]["is_contradiction"], bool)
        assert isinstance(by_name["Nia"]["requires_review"], bool)
        assert 0.0 <= float(by_name["Nia"]["contradiction_severity"]) <= 1.0
