import pytest
from fastapi.testclient import TestClient

from app.chart_contracts import build_polarity_graph_contract
from app.main import app
from app.services.export import _build_rolling_emotional_curves


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("LLM_PROVIDER_PRIORITY_ORDER", '["openrouter","siliconflow","groq"]')
    with TestClient(app) as test_client:
        yield test_client


def test_run_polarity_graph_endpoint_returns_contract_payload(client: TestClient) -> None:
    sample_text = (
        "Chapter 1\n"
        "The wind settled over the valley as the storm began.\n"
        '"Where are we going?" Mira asked.\n\n'
        "Chapter 2\n"
        "The answer came in a whisper.\n"
    )
    project_resp = client.post("/api/projects", json={"title": "Polarity Graph Endpoint Project"})
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
    export_payload = export_resp.json()
    academic_reports = export_payload["manifest"]["academic_reports"]
    time_series = export_payload["time_series"]

    graph_resp = client.get(
        f"/api/projects/{project_id}/runs/{run_id}/polarity-graph",
    )
    assert graph_resp.status_code == 200
    payload = graph_resp.json()

    expected_payload = build_polarity_graph_contract(academic_reports, time_series).dict()
    assert payload == expected_payload

    assert payload["metric_id"] == "rolling_emotional_polarity"
    assert payload["value_key"] == "rolling_mean_valence"
    assert payload["source_path"] == ["rolling_window_emotional_curves", "valence_curve"]
    assert payload["points"]
    assert payload["points"][0]["position"] == 1
    assert payload["metadata"]["rolling_window_size"] == 5
    assert payload["metadata"]["volatility_markers_count"] >= 0


def test_run_polarity_graph_endpoint_supports_rolling_window_control(client: TestClient) -> None:
    sample_text = (
        "Chapter 1\n"
        "The wind settled over the valley as the storm began.\n"
        '"Where are we going?" Mira asked.\n\n'
        "Chapter 2\n"
        "The answer came in a whisper.\n"
    )
    project_resp = client.post("/api/projects", json={"title": "Polarity Graph Rolling Window Project"})
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

    export_payload = client.get(f"/api/projects/{project_id}/exports/{run_id}.json").json()
    academic_reports = export_payload["manifest"]["academic_reports"]
    time_series = export_payload["time_series"]
    segments = export_payload["segments"]

    graph_resp = client.get(
        f"/api/projects/{project_id}/runs/{run_id}/polarity-graph",
        params={"window_size": 3},
    )
    assert graph_resp.status_code == 200
    payload = graph_resp.json()

    rerun_reports = dict(academic_reports)
    rerun_reports["rolling_window_emotional_curves"] = _build_rolling_emotional_curves(
        segments=segments,
        window_size=3,
    )
    expected_payload = build_polarity_graph_contract(rerun_reports, time_series).dict()
    assert payload == expected_payload
    assert payload["metadata"]["rolling_window_size"] == 3


def test_run_polarity_graph_endpoint_404_for_missing_run(client: TestClient) -> None:
    project_resp = client.post(
        "/api/projects",
        json={"title": "Polarity Graph 404 Project"},
    )
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    response = client.get(f"/api/projects/{project_id}/runs/99999/polarity-graph")
    assert response.status_code == 404
