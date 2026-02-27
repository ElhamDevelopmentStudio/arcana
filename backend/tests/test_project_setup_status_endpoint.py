import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

DB_FILE = "test_nipe_project_setup_status_endpoint.db"
DB_URL = f"sqlite:///./{DB_FILE}"
os.environ["DATABASE_URL"] = DB_URL

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.main import app
from app.schemas import ProjectSetupStatusResponse


def setup_module() -> None:
    os.environ["DATABASE_URL"] = DB_URL
    db_file = Path(DB_FILE)
    if db_file.exists():
        db_file.unlink()
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()
    db_file = Path(DB_FILE)
    if db_file.exists():
        db_file.unlink()


def _sample_txt() -> str:
    return (
        "Chapter 1\n"
        '"Sunny looked around," Sunny said. The cold wind cut through the dark street.\n\n'
        "Chapter 2\n"
        "Nephis smiled. Hope rose with the warm light."
    )


def _setup_steps_by_id(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    return {
        str(step["step_id"]): step
        for step in payload.get("steps", [])
        if isinstance(step, dict) and "step_id" in step
    }


def test_integration_project_setup_status_endpoint_for_draft_project() -> None:
    with TestClient(app) as client:
        create_resp = client.post("/api/projects/drafts", json={"title": "Setup Status Draft"})
        assert create_resp.status_code == 201
        project_id = create_resp.json()["id"]

        setup_status_resp = client.get(f"/api/projects/{project_id}/setup-status")
        assert setup_status_resp.status_code == 200
        payload = setup_status_resp.json()
        parsed = ProjectSetupStatusResponse.model_validate(payload)

    assert parsed.output_schema == "project_setup_status_json"
    assert parsed.project_id == project_id
    assert parsed.lifecycle_state == "draft"
    assert parsed.next_required_action == "ingest"
    assert parsed.is_complete is False

    steps = _setup_steps_by_id(payload)
    assert steps["ingestion"]["ready"] is False
    assert steps["mode_selection"]["ready"] is True
    assert steps["initial_run"]["ready"] is False
    assert steps["character_mapping"]["required"] is False
    assert steps["voice_mapping"]["required"] is False


def test_integration_project_setup_status_endpoint_marks_required_steps_complete_after_first_run() -> None:
    with TestClient(app) as client:
        create_resp = client.post("/api/projects/drafts", json={"title": "Setup Status Completed"})
        assert create_resp.status_code == 201
        project_id = create_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("setup-status.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(f"/api/projects/{project_id}/runs", json={"mode": "author"})
        assert run_resp.status_code == 200

        setup_status_resp = client.get(f"/api/projects/{project_id}/setup-status")
        assert setup_status_resp.status_code == 200
        payload = setup_status_resp.json()
        parsed = ProjectSetupStatusResponse.model_validate(payload)

    assert parsed.lifecycle_state == "completed"
    assert parsed.next_required_action == "export"
    assert parsed.is_complete is True

    steps = _setup_steps_by_id(payload)
    assert steps["ingestion"]["ready"] is True
    assert steps["mode_selection"]["ready"] is True
    assert steps["initial_run"]["ready"] is True


def test_regression_project_setup_status_endpoint_rejects_unknown_project() -> None:
    with TestClient(app) as client:
        setup_status_resp = client.get("/api/projects/999999999/setup-status")

    assert setup_status_resp.status_code == 404
    assert setup_status_resp.json()["detail"] == "Project not found"
