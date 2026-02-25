import io
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


def test_integration_gender_comparison_respects_threshold_setting(monkeypatch) -> None:
    monkeypatch.setenv("CONTRADICTION_REVIEW_THRESHOLD", "0.99")
    clear_settings_cache()

    try:
        with TestClient(app) as client:
            project_resp = client.post("/api/projects", json={"title": "Gender Comparison Threshold Test"})
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
                    ]
                },
            )
            assert upsert_resp.status_code == 200

            compare_resp = client.get(f"/api/projects/{project_id}/characters/gender-comparison")
            assert compare_resp.status_code == 200
            body = compare_resp.json()
            assert body["comparison_count"] == 1
            assert body["comparisons"][0]["is_contradiction"] is True
            assert body["comparisons"][0]["contradiction_severity"] == 0.955
            assert body["comparisons"][0]["requires_review"] is False
            assert body["contradiction_count"] == 1
    finally:
        clear_settings_cache()


def test_integration_export_blocked_when_review_required_by_threshold() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Gender Export Blocked"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("novel.txt", io.BytesIO(b"Chapter 1\nHe entered the hall."), "text/plain")},
        )
        assert ingest_resp.status_code == 200

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
                ],
            },
        )
        assert upsert_resp.status_code == 200

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"allow_unfinalized_character_map": True},
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 409
        detail = export_resp.json()["detail"]
        assert detail["requires_review_count"] == 1
        assert detail["threshold"] == 0.75


def test_integration_export_allowed_when_threshold_not_triggered(monkeypatch) -> None:
    monkeypatch.setenv("CONTRADICTION_REVIEW_THRESHOLD", "0.99")
    clear_settings_cache()

    try:
        with TestClient(app) as client:
            project_resp = client.post("/api/projects", json={"title": "Gender Export Allowed"})
            assert project_resp.status_code == 201
            project_id = project_resp.json()["id"]

            ingest_resp = client.post(
                f"/api/projects/{project_id}/ingest/txt",
                files={"file": ("novel.txt", io.BytesIO(b"Chapter 1\nShe entered the hall."), "text/plain")},
            )
            assert ingest_resp.status_code == 200

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
                    ],
                },
            )
            assert upsert_resp.status_code == 200

            run_resp = client.post(
                f"/api/projects/{project_id}/runs",
                json={"allow_unfinalized_character_map": True},
            )
            assert run_resp.status_code == 200
            run_id = run_resp.json()["run_id"]

            export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
            assert export_resp.status_code == 200
            assert export_resp.json()["run_id"] == run_id
    finally:
        clear_settings_cache()


def test_integration_export_not_blocked_for_unknown_gender_characters() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Gender Export Unknown Allowed"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("novel.txt", io.BytesIO(b"Chapter 1\nShe appeared, then he returned."), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        upsert_resp = client.put(
            f"/api/projects/{project_id}/characters",
            json={
                "characters": [
                    {
                        "name": "Unknown Manual",
                        "verbalized_form": "Unknown Manual",
                        "gender": "unknown",
                        "confidence": 1.0,
                        "inferred_gender": "female",
                        "inferred_confidence": 0.91,
                        "inferred_source_trace": [],
                    },
                    {
                        "name": "Unknown Inferred",
                        "verbalized_form": "Unknown Inferred",
                        "gender": "male",
                        "confidence": 0.7,
                        "inferred_gender": "unknown",
                        "inferred_confidence": 0.0,
                        "inferred_source_trace": [],
                    },
                ],
            },
        )
        assert upsert_resp.status_code == 200

        comparison_resp = client.get(f"/api/projects/{project_id}/characters/gender-comparison")
        assert comparison_resp.status_code == 200
        body = comparison_resp.json()
        assert body["comparison_count"] == 2
        assert body["contradiction_count"] == 0
        assert all(item["requires_review"] is False for item in body["comparisons"])

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"allow_unfinalized_character_map": True},
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200
        payload = export_resp.json()
        assert payload["project_id"] == project_id
        assert payload["run_id"] == run_id


def test_integration_gender_comparison_flags_blocking_and_export_gating() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Gender Flags and Export Gating"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("novel.txt", io.BytesIO(b'Chapter 1\n"Nia said," Nia said.\n"Kai answered," Kai answered.'), "text/plain")},
        )
        assert ingest_resp.status_code == 200

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
                        "inferred_confidence": 0.94,
                        "inferred_source_trace": [],
                    },
                    {
                        "name": "Kai",
                        "verbalized_form": "Kai",
                        "gender": "female",
                        "confidence": 1.0,
                        "inferred_gender": "female",
                        "inferred_confidence": 0.93,
                        "inferred_source_trace": [],
                    },
                    {
                        "name": "Mia",
                        "verbalized_form": "Mia",
                        "gender": "unknown",
                        "confidence": 0.5,
                        "inferred_gender": "male",
                        "inferred_confidence": 0.92,
                        "inferred_source_trace": [],
                    },
                ]
            },
        )
        assert upsert_resp.status_code == 200

        comparison_resp = client.get(f"/api/projects/{project_id}/characters/gender-comparison")
        assert comparison_resp.status_code == 200
        comparison_body = comparison_resp.json()
        assert comparison_body["comparison_count"] == 3
        assert comparison_body["contradiction_count"] == 1

        by_name = {entry["name"]: entry for entry in comparison_body["comparisons"]}
        assert by_name["Nia"]["is_contradiction"] is True
        assert by_name["Nia"]["requires_review"] is True
        assert by_name["Nia"]["comparison"] == "conflict"
        assert by_name["Kai"]["requires_review"] is False
        assert by_name["Mia"]["is_contradiction"] is False
        assert by_name["Mia"]["requires_review"] is False
        assert by_name["Mia"]["comparison"] == "manual_unknown"

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"allow_unfinalized_character_map": True},
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 409
        detail = export_resp.json()["detail"]
        assert detail["requires_review_count"] == 1
        assert detail["threshold"] == 0.75


def test_integration_export_prefers_manual_gender_when_inferred_conflicts() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Gender Manual Precedence In Export"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("novel.txt", io.BytesIO(b'Chapter 1\n"Hello," Alex said.'), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        upsert_resp = client.put(
            f"/api/projects/{project_id}/characters",
            json={
                "characters": [
                    {
                        "name": "Alex",
                        "verbalized_form": "Alex",
                        "gender": "female",
                        "confidence": 0.42,
                        "source": "manual",
                        "inferred_gender": "male",
                        "inferred_confidence": 0.94,
                        "inferred_source_trace": [],
                    }
                ],
            },
        )
        assert upsert_resp.status_code == 200

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"allow_unfinalized_character_map": True},
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200
        payload = export_resp.json()
        assert payload["run_id"] == run_id
        assert payload["segments"]

        segment = next(segment for segment in payload["segments"] if segment["speaker"] == "Alex")
        assert segment["speaker"] == "Alex"
        assert segment["gender"] == "female"
        assert segment["voice_id"] == "female_default"
        assert segment["confidence"]["gender"] == 0.42


def test_integration_infer_updates_inferred_only_not_manual_gender() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Gender Inference Manual Authority"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("novel.txt", io.BytesIO(b'Chapter 1\nMr. Alex entered the room. "Enough," Alex said.'), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        upsert_resp = client.put(
            f"/api/projects/{project_id}/characters",
            json={
                "characters": [
                    {
                        "name": "Alex",
                        "verbalized_form": "Alex",
                        "gender": "female",
                        "confidence": 0.2,
                        "source": "manual",
                        "inferred_gender": "unknown",
                        "inferred_confidence": 0.0,
                        "inferred_source_trace": [],
                    }
                ],
            },
        )
        assert upsert_resp.status_code == 200

        infer_resp = client.post(f"/api/projects/{project_id}/characters/infer")
        assert infer_resp.status_code == 200
        inferred_map = infer_resp.json()["characters"]
        alex = next(entry for entry in inferred_map if entry["name"] == "Alex")
        assert alex["inferred_gender"] == "male"
        assert alex["gender"] == "female"

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"allow_unfinalized_character_map": True},
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200
        payload = export_resp.json()
        segment = next(segment for segment in payload["segments"] if segment["speaker"] == "Alex")
        assert segment["gender"] == "female"
        assert segment["voice_id"] == "female_default"
        assert segment["confidence"]["gender"] == 0.2
