import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

DB_FILE = "test_nipe_project_workspace_summary_endpoint.db"
DB_URL = f"sqlite:///./{DB_FILE}"
os.environ["DATABASE_URL"] = DB_URL

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Character, CharacterVoiceMap
from app.schemas import ProjectWorkspaceSummaryResponse


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


def test_integration_project_workspace_summary_endpoint_for_draft_project() -> None:
    with TestClient(app) as client:
        create_resp = client.post("/api/projects/drafts", json={"title": "Workspace Summary Draft"})
        assert create_resp.status_code == 201
        project_id = create_resp.json()["id"]

        summary_resp = client.get(f"/api/projects/{project_id}/workspace-summary")
        assert summary_resp.status_code == 200
        payload = summary_resp.json()
        parsed = ProjectWorkspaceSummaryResponse.model_validate(payload)

    assert parsed.output_schema == "project_workspace_summary_json"
    assert parsed.project_id == project_id
    assert parsed.lifecycle_state == "draft"
    assert parsed.last_run_status is None
    assert parsed.next_required_action == "ingest"
    assert parsed.is_setup_complete is False
    assert parsed.chapters_count == 0
    assert parsed.characters_count == 0
    assert parsed.voice_mappings_count == 0
    assert parsed.runs_total_count == 0
    assert parsed.runs_completed_count == 0
    assert parsed.runs_failed_count == 0
    assert parsed.last_export_at is None


def test_integration_project_workspace_summary_endpoint_for_populated_project() -> None:
    with TestClient(app) as client:
        create_resp = client.post("/api/projects/drafts", json={"title": "Workspace Summary Populated"})
        assert create_resp.status_code == 201
        project_id = create_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("workspace-summary.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(f"/api/projects/{project_id}/runs", json={"mode": "author"})
        assert run_resp.status_code == 200

    session = get_session_factory()()
    try:
        character = Character(
            project_id=project_id,
            name="Sunny",
            verbalized_form="Sunny",
            gender="male",
            aliases=["Sunless"],
            notes="Lead character",
            source="user_import",
            confidence=1.0,
            inferred_gender="male",
            inferred_confidence=1.0,
            inferred_source_trace=[],
            voice_id="voice_sunny",
        )
        session.add(character)
        session.flush()
        session.add(
            CharacterVoiceMap(
                project_id=project_id,
                character_id=character.id,
                voice_id="voice_sunny",
            ),
        )
        session.commit()
    finally:
        session.close()

    with TestClient(app) as client:
        summary_resp = client.get(f"/api/projects/{project_id}/workspace-summary")
        assert summary_resp.status_code == 200
        payload = summary_resp.json()
        parsed = ProjectWorkspaceSummaryResponse.model_validate(payload)

    assert parsed.project_id == project_id
    assert parsed.lifecycle_state == "completed"
    assert parsed.last_run_status == "completed"
    assert parsed.next_required_action == "export"
    assert parsed.is_setup_complete is True
    assert parsed.chapters_count == 2
    assert parsed.characters_count == 1
    assert parsed.voice_mappings_count == 1
    assert parsed.runs_total_count == 1
    assert parsed.runs_completed_count == 1
    assert parsed.runs_failed_count == 0


def test_regression_project_workspace_summary_endpoint_rejects_unknown_project() -> None:
    with TestClient(app) as client:
        summary_resp = client.get("/api/projects/999999999/workspace-summary")

    assert summary_resp.status_code == 404
    assert summary_resp.json()["detail"] == "Project not found"
