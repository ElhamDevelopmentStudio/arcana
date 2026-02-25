import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_project_configuration_snapshot.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import _build_initial_configuration_snapshot_id, app
from app.models import Project


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_project_configuration_snapshot.db")
    if db_file.exists():
        db_file.unlink()


def test_unit_configuration_snapshot_id_builder() -> None:
    assert _build_initial_configuration_snapshot_id(7) == "project-7-config-initial"


def test_integration_create_project_returns_configuration_snapshot_reference() -> None:
    with TestClient(app) as client:
        response = client.post("/api/projects", json={"title": "Configuration Snapshot Integration"})
    assert response.status_code == 201
    payload = response.json()
    assert payload["configuration_snapshot_id"] == f"project-{payload['id']}-config-initial"


def test_e2e_configuration_snapshot_reference_is_persisted_on_project_row() -> None:
    with TestClient(app) as client:
        response = client.post("/api/projects", json={"title": "Configuration Snapshot E2E"})
    assert response.status_code == 201
    payload = response.json()
    project_id = payload["id"]

    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        assert project.configuration_snapshot_id == f"project-{project_id}-config-initial"
    finally:
        session.close()


def test_regression_configuration_snapshot_reference_format() -> None:
    assert _build_initial_configuration_snapshot_id(101) == "project-101-config-initial"
