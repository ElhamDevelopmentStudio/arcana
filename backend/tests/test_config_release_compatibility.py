import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_config_release_compatibility.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Run


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_config_release_compatibility.db")
    if db_file.exists():
        db_file.unlink()


def _sample_txt() -> str:
    return (
        "Chapter 1\n"
        '"Vale stopped," Vale said. Snow drifted across the road.\n\n'
        "Chapter 2\n"
        "Morning bells echoed over the square."
    )


def _create_project_with_ingested_text(client: TestClient, title: str) -> int:
    project_resp = client.post("/api/projects", json={"title": title})
    assert project_resp.status_code == 201
    project_id = int(project_resp.json()["id"])

    ingest_resp = client.post(
        f"/api/projects/{project_id}/ingest/txt",
        files={"file": ("sample.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
    )
    assert ingest_resp.status_code == 200
    return project_id


def test_integration_run_creation_accepts_legacy_preset_fields() -> None:
    with TestClient(app) as client:
        project_id = _create_project_with_ingested_text(client, "Legacy Preset Compatibility")
        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={
                "mode": "author",
                "max_segment_chars": 170,
                "export_formats": ["json", "csv"],
                "allow_unfinalized_character_map": True,
                "config_schema_version": "0.9.0",
                "legacy_profile_name": "release-2025",
                "deprecated_thresholds": {"speaker": 0.5},
            },
        )
        assert run_resp.status_code == 200
        run_id = int(run_resp.json()["run_id"])

        run_detail_resp = client.get(f"/api/projects/{project_id}/runs/{run_id}")
        assert run_detail_resp.status_code == 200
        config = run_detail_resp.json()["config"]
        assert config["mode"] == "author"
        assert config["config_schema_version"] == "1.0.0"
        assert "legacy_profile_name" not in config
        assert "deprecated_thresholds" not in config


def test_integration_config_diff_defaults_schema_version_for_legacy_run_rows() -> None:
    with TestClient(app) as client:
        project_id = _create_project_with_ingested_text(client, "Legacy Diff Compatibility")
        base_run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"mode": "author", "allow_unfinalized_character_map": True},
        )
        assert base_run_resp.status_code == 200
        base_run_id = int(base_run_resp.json()["run_id"])

        target_run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"mode": "academic", "allow_unfinalized_character_map": True},
        )
        assert target_run_resp.status_code == 200
        target_run_id = int(target_run_resp.json()["run_id"])

    session = get_session_factory()()
    try:
        base_run = session.query(Run).filter(Run.id == base_run_id).one()
        legacy_config = dict(base_run.config_json or {})
        legacy_config.pop("config_schema_version", None)
        base_run.config_json = legacy_config
        session.add(base_run)
        session.commit()
    finally:
        session.close()

    with TestClient(app) as client:
        diff_resp = client.get(
            f"/api/projects/{project_id}/runs/config-diff",
            params={"base_run_id": base_run_id, "target_run_id": target_run_id},
        )
        assert diff_resp.status_code == 200
        diff_payload = diff_resp.json()
        assert diff_payload["base_config_schema_version"] == "1.0.0"
        assert diff_payload["target_config_schema_version"] == "1.0.0"

        preset_resp = client.get(f"/api/projects/{project_id}/runs/{base_run_id}/config-preset")
        assert preset_resp.status_code == 200
