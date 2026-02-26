import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("LLM_PROVIDER_PRIORITY_ORDER", '["openrouter","siliconflow","groq"]')
    with TestClient(app) as test_client:
        yield test_client


def test_run_character_cooccurrence_graph_endpoint_returns_contract_payload(client: TestClient) -> None:
    project_resp = client.post("/api/projects", json={"title": "Character Cooccurrence Graph Project"})
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    ingest_resp = client.post(
        f"/api/projects/{project_id}/ingest/txt",
        files={"file": ("sample.txt", b"Chapter 1\nAlice spoke. Ben replied.", "text/plain")},
    )
    assert ingest_resp.status_code == 200

    run_resp = client.post(
        f"/api/projects/{project_id}/runs",
        json={"max_segment_chars": 120, "llm_enabled": False, "provider_name": "openrouter", "max_calls_per_day": 2, "allow_unfinalized_character_map": True},
    )
    assert run_resp.status_code == 200
    run_id = run_resp.json()["run_id"]

    cooccurrence_graph_response = client.get(
        f"/api/projects/{project_id}/runs/{run_id}/character-cooccurrence-graph",
    )
    assert cooccurrence_graph_response.status_code == 200
    payload = cooccurrence_graph_response.json()

    assert payload["schema_version"] == "1.0.0"
    assert payload["output_schema"] == "graph_json"
    assert payload["output_format"] == "graph_json"
    assert payload["output_id"] == "AO-004"
    assert payload["output_name"] == "character_cooccurrence_graph"
    assert payload["project_id"] == project_id
    assert payload["run_id"] == run_id
    assert payload["run_status"] == "completed"
    assert payload["generated_by"] == "build_run_export_graph_json"
    assert "manifest_snapshot" in payload
    assert isinstance(payload["graph"], dict)
    assert isinstance(payload["graph"]["nodes"], list)
    assert isinstance(payload["graph"]["edges"], list)
    assert isinstance(payload["graph"]["metadata"], dict)
    assert payload["graph"]["metadata"]["node_count"] == len(payload["graph"]["nodes"])
    assert payload["graph"]["metadata"]["edge_count"] == len(payload["graph"]["edges"])
    assert isinstance(payload["character_cooccurrence_centrality"], dict)
    assert isinstance(payload["character_cooccurrence_centrality"]["metrics_table"], list)


def test_run_character_cooccurrence_graph_endpoint_404_for_missing_run(client: TestClient) -> None:
    project_resp = client.post("/api/projects", json={"title": "Missing Run Cooccurrence Project"})
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    response = client.get(f"/api/projects/{project_id}/runs/99999/character-cooccurrence-graph")
    assert response.status_code == 404
