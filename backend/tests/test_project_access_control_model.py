import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_project_access_control.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.schemas import ProjectAccessGrantRequest, ProjectAccessListResponse
from app.models import ProjectAccess


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_project_access_control.db")
    if db_file.exists():
        db_file.unlink()


def test_unit_access_request_normalizes_principal_type_and_role() -> None:
    payload = ProjectAccessGrantRequest(
        principal_id="User-Alpha",
        principal_type="USER",
        role="EDITOR",
    )

    assert payload.principal_type == "user"
    assert payload.role == "editor"


def test_integration_manage_project_access_grants() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Access Control Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        grant_response = client.post(
            f"/api/projects/{project_id}/access",
            json={"principal_id": "alice", "principal_type": "user", "role": "viewer"},
        )
        assert grant_response.status_code == 201
        grant_payload = grant_response.json()
        assert grant_payload["principal_id"] == "alice"
        assert grant_payload["principal_type"] == "user"
        assert grant_payload["role"] == "viewer"

        duplicate_principal_response = client.post(
            f"/api/projects/{project_id}/access",
            json={"principal_id": "alice", "principal_type": "user", "role": "editor"},
        )
        assert duplicate_principal_response.status_code == 201
        updated_payload = duplicate_principal_response.json()
        assert updated_payload["role"] == "editor"

        additional_response = client.post(
            f"/api/projects/{project_id}/access",
            json={"principal_id": "svc-builder", "principal_type": "service", "role": "viewer"},
        )
        assert additional_response.status_code == 201

        list_response = client.get(f"/api/projects/{project_id}/access")
        assert list_response.status_code == 200
        list_payload = ProjectAccessListResponse.model_validate(list_response.json())
        assert list_payload.project_id == project_id
        assert len(list_payload.grants) == 2
        roles_by_principal = {
            f"{entry.principal_type}:{entry.principal_id}": entry.role for entry in list_payload.grants
        }
        assert roles_by_principal["user:alice"] == "editor"
        assert roles_by_principal["service:svc-builder"] == "viewer"

    session = get_session_factory()()
    try:
        grants = (
            session.query(ProjectAccess)
            .filter(ProjectAccess.project_id == project_id)
            .order_by(ProjectAccess.id.asc())
            .all()
        )
        assert len(grants) == 2
        created_at_values = [entry.created_at for entry in grants]
        assert all(isinstance(ts, datetime) for ts in created_at_values)
    finally:
        session.close()


def test_reject_invalid_access_role_with_422() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Invalid Role Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        invalid = client.post(
            f"/api/projects/{project_id}/access",
            json={"principal_id": "alice", "principal_type": "user", "role": "superuser"},
        )
        assert invalid.status_code == 422
