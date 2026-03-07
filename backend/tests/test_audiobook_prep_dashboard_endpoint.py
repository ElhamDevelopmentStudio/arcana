import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("LLM_PROVIDER_PRIORITY_ORDER", '["openrouter","siliconflow","groq"]')
    with TestClient(app) as test_client:
        yield test_client


def test_run_audiobook_prep_dashboard_endpoint_returns_contract_payload(client: TestClient) -> None:
    sample_text = (
        "Chapter 1\n"
        "The wind settled over the valley as the storm began.\n"
        '"Where are we going?" Mira asked.\n\n'
        "Chapter 2\n"
        "The answer came in a whisper."
    )
    project_resp = client.post("/api/projects", json={"title": "Audiobook Prep Dashboard Endpoint Project"})
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

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
    run_id = run_resp.json()["run_id"]

    dashboard_resp = client.get(f"/api/projects/{project_id}/runs/{run_id}/audiobook-prep-dashboard")
    assert dashboard_resp.status_code == 200
    payload = dashboard_resp.json()

    assert payload["schema_version"] == "1.0.0"
    assert payload["output_schema"] == "audiobook_prep_dashboard_json"
    assert payload["output_format"] == "json"
    assert payload["output_id"] == "AB-001"
    assert payload["output_name"] == "audiobook_prep_dashboard"
    assert payload["project_id"] == project_id
    assert payload["run_id"] == run_id
    assert payload["run_status"] == "completed"
    assert isinstance(payload["generated_at"], str)
    assert isinstance(payload["unresolved_speaker_count"], int)
    assert payload["unresolved_speaker_count"] >= 0
    assert isinstance(payload["unresolved_voice_mapping_count"], int)
    assert payload["unresolved_voice_mapping_count"] >= 0
    assert isinstance(payload["low_confidence_region_count"], int)
    assert payload["low_confidence_region_count"] >= 0
    assert isinstance(payload["export_readiness"], dict)
    assert isinstance(payload["export_readiness"]["is_ready"], bool)
    assert isinstance(payload["export_readiness"]["blocking_reasons"], list)
    assert isinstance(payload["export_readiness"]["warning_reasons"], list)


def test_run_audiobook_prep_dashboard_endpoint_404_for_missing_run(client: TestClient) -> None:
    project_resp = client.post("/api/projects", json={"title": "Missing Run Audiobook Dashboard Project"})
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    response = client.get(f"/api/projects/{project_id}/runs/99999/audiobook-prep-dashboard")
    assert response.status_code == 404
