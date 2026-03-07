import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("LLM_PROVIDER_PRIORITY_ORDER", '["openrouter","siliconflow","groq"]')
    with TestClient(app) as test_client:
        yield test_client


def test_pipeline_stage_durations_dashboard_endpoint_returns_contract_payload(client: TestClient) -> None:
    sample_text = (
        "Chapter 1\n"
        "The engine room rattled while glass lights hummed.\n"
        '"Hold position," Jara said.\n\n'
        "Chapter 2\n"
        "A warning bell echoed down the corridor."
    )
    project_resp = client.post("/api/projects", json={"title": "Pipeline Stage Durations Dashboard Project"})
    assert project_resp.status_code == 201
    project_id = int(project_resp.json()["id"])

    ingest_resp = client.post(
        f"/api/projects/{project_id}/ingest/txt",
        files={"file": ("sample.txt", sample_text.encode("utf-8"), "text/plain")},
    )
    assert ingest_resp.status_code == 200

    run_resp = client.post(
        f"/api/projects/{project_id}/runs",
        json={
            "max_segment_chars": 120,
            "llm_enabled": False,
            "provider_name": "openrouter",
            "max_calls_per_day": 2,
            "allow_unfinalized_character_map": True,
        },
    )
    assert run_resp.status_code == 200
    run_id = int(run_resp.json()["run_id"])

    dashboard_resp = client.get(f"/api/projects/{project_id}/runs/{run_id}/pipeline-stage-durations-dashboard")
    assert dashboard_resp.status_code == 200
    payload = dashboard_resp.json()

    assert payload["schema_version"] == "1.0.0"
    assert payload["output_schema"] == "pipeline_stage_durations_dashboard_json"
    assert payload["output_format"] == "json"
    assert payload["output_id"] == "OBS-001"
    assert payload["output_name"] == "pipeline_stage_durations_dashboard"
    assert payload["project_id"] == project_id
    assert payload["run_id"] == run_id
    assert payload["run_status"] == "completed"
    assert isinstance(payload["generated_at"], str)

    assert isinstance(payload["total_duration_ms"], int)
    assert payload["total_duration_ms"] >= 0
    assert isinstance(payload["stage_count"], int)
    assert payload["stage_count"] >= 1
    assert isinstance(payload["stages"], list)
    assert len(payload["stages"]) == payload["stage_count"]

    stage_names = [str(stage["stage_name"]) for stage in payload["stages"]]
    assert "load_and_validate_source_data" in stage_names
    assert "finalize_run_and_build_export" in stage_names

    max_duration = 0
    for stage in payload["stages"]:
        assert isinstance(stage["stage_name"], str)
        assert isinstance(stage["duration_ms"], int)
        assert stage["duration_ms"] >= 0
        assert isinstance(stage["share_of_total"], (float, int))
        assert float(stage["share_of_total"]) >= 0
        assert float(stage["share_of_total"]) <= 1
        if stage["duration_ms"] > max_duration:
            max_duration = stage["duration_ms"]

    assert payload["total_duration_ms"] >= max_duration
    assert isinstance(payload["slowest_stage_name"], str)
    assert payload["slowest_stage_name"] in stage_names
    assert isinstance(payload["slowest_stage_duration_ms"], int)
    assert payload["slowest_stage_duration_ms"] >= 0


def test_pipeline_stage_durations_dashboard_endpoint_404_for_missing_run(client: TestClient) -> None:
    project_resp = client.post("/api/projects", json={"title": "Missing Run Pipeline Stage Duration Dashboard Project"})
    assert project_resp.status_code == 201
    project_id = int(project_resp.json()["id"])

    response = client.get(f"/api/projects/{project_id}/runs/99999/pipeline-stage-durations-dashboard")
    assert response.status_code == 404
