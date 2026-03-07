import io
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_project_mode_persistence.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Project, Run
from app.schemas import ProjectResponse


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_project_mode_persistence.db")
    if db_file.exists():
        db_file.unlink()


def _sample_txt() -> str:
    return (
        "Chapter 1\n"
        '"Mira paused," Mira said. The hall was quiet.\n\n'
        "Chapter 2\n"
        "Dawn came and the city woke."
    )


def test_unit_project_response_includes_selected_mode_field() -> None:
    payload = ProjectResponse(
        id=1,
        title="Mode Persistence Unit",
        selected_mode="academic",
        selected_modes=["audiobook", "academic"],
        llm_enabled=False,
        configuration_snapshot_id="project-1-config-initial",
        character_map_finalized=False,
        ingestion_timestamp=None,
        created_at=datetime.now(timezone.utc),
    )
    assert payload.selected_mode == "academic"
    assert payload.selected_modes == ["audiobook", "academic"]


def test_integration_project_default_mode_is_persisted_on_create() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Mode Persistence Integration"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]
        assert project_resp.json()["selected_mode"] == "audiobook"
        assert project_resp.json()["selected_modes"] == ["audiobook"]
        assert project_resp.json()["configuration_snapshot_id"] == f"project-{project_id}-config-initial"

    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        assert project.selected_mode == "audiobook"
        assert project.selected_modes == ["audiobook"]
    finally:
        session.close()


def test_e2e_run_mode_updates_project_selected_mode() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Mode Persistence E2E"})
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
                "mode": "author",
                "max_segment_chars": 120,
                "llm_enabled": False,
                "provider_name": "openrouter",
                "max_calls_per_day": 5,
            },
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        detail_resp = client.get(f"/api/projects/{project_id}/runs/{run_id}")
        assert detail_resp.status_code == 200
        assert detail_resp.json()["config"]["mode"] == "author"

    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        assert project.selected_mode == "author"
        assert project.selected_modes == ["audiobook", "author"]
    finally:
        session.close()


def test_regression_latest_run_mode_overwrites_project_selected_mode() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Mode Persistence Regression"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        run_one = client.post(
            f"/api/projects/{project_id}/runs",
            json={
                "mode": "academic",
                "max_segment_chars": 120,
                "llm_enabled": False,
                "provider_name": "openrouter",
                "max_calls_per_day": 5,
            },
        )
        assert run_one.status_code == 200

        run_two = client.post(
            f"/api/projects/{project_id}/runs",
            json={
                "mode": "custom",
                "max_segment_chars": 120,
                "llm_enabled": False,
                "provider_name": "openrouter",
                "max_calls_per_day": 5,
            },
        )
        assert run_two.status_code == 200
        run_two_id = run_two.json()["run_id"]

        run_two_detail = client.get(f"/api/projects/{project_id}/runs/{run_two_id}")
        assert run_two_detail.status_code == 200
        assert run_two_detail.json()["config"]["mode"] == "custom"

    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        assert project.selected_mode == "custom"
        assert project.selected_modes == ["audiobook", "academic", "custom"]

        runs = session.query(Run).filter(Run.project_id == project_id).order_by(Run.id.asc()).all()
        assert runs[0].config_json["mode"] == "academic"
        assert runs[1].config_json["mode"] == "custom"
    finally:
        session.close()
