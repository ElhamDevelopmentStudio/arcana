import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_run_configuration_snapshots.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Run, RunConfigurationSnapshot


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_run_configuration_snapshots.db")
    if db_file.exists():
        db_file.unlink()


def _ingest_project_text(project_title: str, source_payload: str) -> int:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": project_title})
        assert project_resp.status_code == 201
        project_id = int(project_resp.json()["id"])

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("story.txt", io.BytesIO(source_payload.encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        return project_id


def _run_project(client: TestClient, project_id: int, payload: dict[str, object]) -> int:
    run_resp = client.post(
        f"/api/projects/{project_id}/runs",
        json=payload,
    )
    assert run_resp.status_code == 200
    return int(run_resp.json()["run_id"])


def test_e2e_run_creation_persists_run_configuration_snapshot() -> None:
    with TestClient(app) as client:
        project_id = _ingest_project_text(
            project_title="Run Config Snapshot Project",
            source_payload=(
                "Chapter 1\n"
                "Mara crossed the harbor at dawn.\n"
                "Jules watched silently."
            ),
        )
        run_id = _run_project(
            client,
            project_id,
            payload={
                "mode": "academic",
                "max_segment_chars": 120,
                "llm_enabled": True,
                "provider_name": "openrouter",
                "deterministic_mode": True,
                "deterministic_seed": 2026,
                "max_calls_per_day": 120,
            },
        )

    session = get_session_factory()()
    try:
        run = session.query(Run).filter(Run.id == run_id).one()
        snapshot = (
            session.query(RunConfigurationSnapshot)
            .filter(RunConfigurationSnapshot.run_id == run.id)
            .one()
        )

        assert snapshot.source == "run_capture"
        assert snapshot.project_id == project_id
        assert snapshot.version == 1
        assert snapshot.run_id == run.id
        assert snapshot.snapshot_json["project_id"] == project_id
        assert snapshot.snapshot_json["run_id"] == run.id
        assert snapshot.snapshot_json["mode"] == "academic"
        assert snapshot.snapshot_json["configuration_snapshot_id"] == f"run-{run.id}-config-{snapshot.version}"
        assert snapshot.snapshot_json["configuration"]["mode"] == "academic"
        assert snapshot.snapshot_json["configuration"]["deterministic_seed"] == 2026
        assert run.config_json["configuration_snapshot_id"] == f"run-{run.id}-config-{snapshot.version}"
        assert run.config_json["configuration_snapshot_version"] == snapshot.version

        original_snapshot_configuration = dict(snapshot.snapshot_json["configuration"])
        run.config_json["mode"] = "audiobook"
        run.config_json["configuration_snapshot_version"] = 9999
        session.add(run)
        session.commit()

        refreshed_snapshot = (
            session.query(RunConfigurationSnapshot)
            .filter(RunConfigurationSnapshot.run_id == run.id)
            .one()
        )
        assert refreshed_snapshot.snapshot_json["configuration"] == original_snapshot_configuration
    finally:
        session.close()


def test_run_configuration_snapshot_versions_increase_across_runs() -> None:
    with TestClient(app) as client:
        project_id = _ingest_project_text(
            project_title="Run Config Snapshot Version Project",
            source_payload="Chapter 1\nThe gate opened slowly.",
        )

        first_run_id = _run_project(
            client,
            project_id,
            payload={"mode": "audiobook", "max_segment_chars": 120, "allow_unfinalized_character_map": True},
        )
        second_run_id = _run_project(
            client,
            project_id,
            payload={"mode": "author", "max_segment_chars": 120, "allow_unfinalized_character_map": True},
        )

    session = get_session_factory()()
    try:
        snapshots = (
            session.query(RunConfigurationSnapshot)
            .filter(RunConfigurationSnapshot.project_id == project_id)
            .order_by(RunConfigurationSnapshot.version.asc())
            .all()
        )
        assert [snapshot.version for snapshot in snapshots] == [1, 2]
        assert [snapshot.run_id for snapshot in snapshots] == [first_run_id, second_run_id]

        first_run = session.query(Run).filter(Run.id == first_run_id).one()
        second_run = session.query(Run).filter(Run.id == second_run_id).one()
        assert first_run.config_json["configuration_snapshot_id"] == f"run-{first_run_id}-config-1"
        assert second_run.config_json["configuration_snapshot_id"] == f"run-{second_run_id}-config-2"
        assert second_run.config_json["configuration_snapshot_version"] == 2
    finally:
        session.close()
