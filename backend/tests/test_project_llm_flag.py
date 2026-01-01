import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_project_llm_flag.db"

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

    db_file = Path("test_nipe_project_llm_flag.db")
    if db_file.exists():
        db_file.unlink()


def _sample_txt() -> str:
    return (
        "Chapter 1\n"
        '"Mira paused," Mira said. The hall was quiet.\n\n'
        "Chapter 2\n"
        "Ari listened."
    )


def test_unit_project_response_supports_llm_enabled_field() -> None:
    payload = ProjectResponse(
        id=1,
        title="LLM Flag Unit",
        selected_mode="audiobook",
        selected_modes=["audiobook"],
        llm_enabled=False,
        configuration_snapshot_id="project-1-config-initial",
        character_map_finalized=False,
        ingestion_timestamp=None,
        created_at="2026-02-25T00:00:00Z",
    )
    assert payload.llm_enabled is False


def test_integration_project_llm_endpoints_control_project_default() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "LLM Flag Endpoint Integration"})
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    with TestClient(app) as client:
        project_llm_get_resp = client.get(f"/api/projects/{project_id}/llm")
    assert project_llm_get_resp.status_code == 200
    assert project_llm_get_resp.json()["project_id"] == project_id
    assert project_llm_get_resp.json()["llm_enabled"] is False

    with TestClient(app) as client:
        project_llm_update_resp = client.put(
            f"/api/projects/{project_id}/llm",
            json={"llm_enabled": True},
        )
    assert project_llm_update_resp.status_code == 200
    assert project_llm_update_resp.json()["llm_enabled"] is True

    with TestClient(app) as client:
        updated_get_resp = client.get(f"/api/projects/{project_id}/llm")
    assert updated_get_resp.status_code == 200
    assert updated_get_resp.json()["llm_enabled"] is True

    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        assert project.llm_enabled is True
    finally:
        session.close()


def test_integration_run_payload_inherits_project_llm_default_and_allows_override() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "LLM Flag Inheritance Integration"})
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    with TestClient(app) as client:
        project_update_resp = client.put(f"/api/projects/{project_id}/llm", json={"llm_enabled": True})
    assert project_update_resp.status_code == 200

    with TestClient(app) as client:
        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
        )
    assert ingest_resp.status_code == 200

    with TestClient(app) as client:
        run_inherited_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={
                "mode": "author",
                "max_segment_chars": 120,
                "provider_name": "openrouter",
                "max_calls_per_day": 5,
                "allow_unfinalized_character_map": True,
            },
        )
    assert run_inherited_resp.status_code == 200
    inherited_run_id = run_inherited_resp.json()["run_id"]

    with TestClient(app) as client:
        run_inherited_detail = client.get(f"/api/projects/{project_id}/runs/{inherited_run_id}")
    assert run_inherited_detail.status_code == 200
    assert run_inherited_detail.json()["config"]["llm_enabled"] is True

    with TestClient(app) as client:
        run_override_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={
                "mode": "author",
                "max_segment_chars": 120,
                "provider_name": "openrouter",
                "max_calls_per_day": 5,
                "allow_unfinalized_character_map": True,
                "llm_enabled": False,
            },
        )
    assert run_override_resp.status_code == 200
    overridden_run_id = run_override_resp.json()["run_id"]

    with TestClient(app) as client:
        run_override_detail = client.get(f"/api/projects/{project_id}/runs/{overridden_run_id}")
    assert run_override_detail.status_code == 200
    assert run_override_detail.json()["config"]["llm_enabled"] is False
