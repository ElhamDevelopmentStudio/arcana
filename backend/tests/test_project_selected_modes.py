import io
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_project_selected_modes.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Project
from app.schemas import ProjectResponse


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_project_selected_modes.db")
    if db_file.exists():
        db_file.unlink()


def _sample_txt() -> str:
    return (
        "Chapter 1\n"
        '"Sunny looked around," Sunny said. The cold wind cut through the dark street.\n\n'
        "Chapter 2\n"
        "Nephis smiled. Hope rose with the warm light."
    )


def test_unit_project_response_includes_selected_modes() -> None:
    payload = ProjectResponse(
        id=1,
        title="Selected Modes Unit",
        selected_mode="author",
        selected_modes=["audiobook", "author"],
        configuration_snapshot_id="project-1-config-initial",
        ingestion_timestamp=None,
        created_at=datetime.now(timezone.utc),
    )
    assert payload.selected_modes == ["audiobook", "author"]


def test_integration_create_project_initializes_selected_modes_with_default() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Selected Modes Integration"})
    assert project_resp.status_code == 201
    payload = project_resp.json()
    assert payload["selected_mode"] == "audiobook"
    assert payload["selected_modes"] == ["audiobook"]
    assert payload["configuration_snapshot_id"] == f"project-{payload['id']}-config-initial"


def test_e2e_mode_switch_and_runs_append_unique_selected_modes() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Selected Modes E2E"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        switch_resp = client.put(f"/api/projects/{project_id}/mode", json={"mode": "author"})
        assert switch_resp.status_code == 200
        assert switch_resp.json()["selected_modes"] == ["audiobook", "author"]

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"mode": "academic"},
        )
        assert run_resp.status_code == 200

    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        assert project.selected_mode == "academic"
        assert project.selected_modes == ["audiobook", "author", "academic"]
    finally:
        session.close()


def test_regression_selected_modes_remains_unique_on_repeated_selection() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Selected Modes Regression"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        for _ in range(3):
            switch_resp = client.put(f"/api/projects/{project_id}/mode", json={"mode": "custom"})
            assert switch_resp.status_code == 200

        payload = switch_resp.json()
        assert payload["selected_modes"] == ["audiobook", "custom"]
