import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_modes_endpoint.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.modes import DEFAULT_MODE, MODE_PERSISTENCE_PATHS, MODE_VALUES, get_mode_catalog
from app.models import Project


EXPECTED_MODE_PAYLOAD = {
    "modes": ["audiobook", "academic", "author", "custom"],
    "default_mode": "audiobook",
    "persisted_in": ["projects.selected_mode", "runs.config_json.mode"],
}


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_modes_endpoint.db")
    if db_file.exists():
        db_file.unlink()


def _sample_txt() -> str:
    return (
        "Chapter 1\n"
        '"Mira paused," Mira said. The hall was quiet.\n\n'
        "Chapter 2\n"
        "Dawn came and the city woke."
    )


def test_unit_get_mode_catalog_matches_mode_constants() -> None:
    catalog = get_mode_catalog()
    assert catalog["modes"] == list(MODE_VALUES)
    assert catalog["default_mode"] == DEFAULT_MODE
    assert catalog["persisted_in"] == list(MODE_PERSISTENCE_PATHS)


def test_integration_modes_endpoint_returns_expected_contract() -> None:
    with TestClient(app) as client:
        response = client.get("/api/modes")
    assert response.status_code == 200
    payload = response.json()
    assert payload["modes"] == list(MODE_VALUES)
    assert payload["default_mode"] == DEFAULT_MODE
    assert payload["persisted_in"] == list(MODE_PERSISTENCE_PATHS)


def test_e2e_modes_endpoint_output_can_drive_run_mode_selection() -> None:
    with TestClient(app) as client:
        modes_resp = client.get("/api/modes")
        assert modes_resp.status_code == 200
        selected_mode = modes_resp.json()["modes"][1]  # academic

        project_resp = client.post("/api/projects", json={"title": "Modes Endpoint E2E"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={
                "mode": selected_mode,
                "max_segment_chars": 120,
                "llm_enabled": False,
                "provider_name": "openrouter",
                "max_calls_per_day": 5,
            },
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        run_detail_resp = client.get(f"/api/projects/{project_id}/runs/{run_id}")
        assert run_detail_resp.status_code == 200
        assert run_detail_resp.json()["config"]["mode"] == selected_mode

    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        assert project.selected_mode == selected_mode
    finally:
        session.close()


def test_regression_modes_endpoint_snapshot() -> None:
    with TestClient(app) as client:
        response = client.get("/api/modes")
    assert response.status_code == 200
    assert response.json() == EXPECTED_MODE_PAYLOAD
