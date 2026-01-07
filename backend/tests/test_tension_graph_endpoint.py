import pytest
from fastapi.testclient import TestClient

from app.chart_contracts import build_tension_graph_contract
from app.main import app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("LLM_PROVIDER_PRIORITY_ORDER", '["openrouter","siliconflow","groq"]')
    with TestClient(app) as test_client:
        yield test_client


def test_run_tension_graph_endpoint_returns_contract_payload(client: TestClient) -> None:
    sample_text = (
        "Chapter 1\n"
        "The wind settled over the valley as the storm began.\n"
        '"Where are we going?" Mira asked.\n\n'
        "Chapter 2\n"
        "The answer came in a whisper.\n"
    )
    project_resp = client.post("/api/projects", json={"title": "Tension Graph Endpoint Project"})
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

    export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
    assert export_resp.status_code == 200
    academic_reports = export_resp.json()["manifest"]["academic_reports"]

    graph_resp = client.get(
        f"/api/projects/{project_id}/runs/{run_id}/tension-graph",
    )
    assert graph_resp.status_code == 200
    payload = graph_resp.json()

    expected_payload = build_tension_graph_contract(academic_reports).dict()
    assert payload == expected_payload

    assert payload["metric_id"] == "smoothed_tension_curve"
    assert payload["value_key"] == "smoothed_tension"
    assert payload["source_path"] == ["smoothed_tension_curve", "tension_curve"]
    assert payload["points"]
    assert payload["points"][0]["position"] == 1
    assert isinstance(payload["metadata"]["smoothed_window_size"], int)
    assert 1 <= payload["metadata"]["smoothed_window_size"]


def test_run_tension_graph_endpoint_404_for_missing_run(client: TestClient) -> None:
    project_resp = client.post(
        "/api/projects",
        json={"title": "Tension Graph 404 Project"},
    )
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    response = client.get(f"/api/projects/{project_id}/runs/99999/tension-graph")
    assert response.status_code == 404
