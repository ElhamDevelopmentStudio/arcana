import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_run_config_diff_endpoint.db"

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.main import app


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_run_config_diff_endpoint.db")
    if db_file.exists():
        db_file.unlink()


def _sample_txt() -> str:
    return (
        "Chapter 1\n"
        '"Cass looked up," Cass said. The harbor lights flickered.\n\n'
        "Chapter 2\n"
        "Storm clouds gathered over the bay."
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


def _run_project(client: TestClient, project_id: int, payload: dict[str, object]) -> int:
    run_resp = client.post(
        f"/api/projects/{project_id}/runs",
        json=payload,
    )
    assert run_resp.status_code == 200
    return int(run_resp.json()["run_id"])


def test_integration_run_config_diff_endpoint_reports_changed_and_unique_fields() -> None:
    with TestClient(app) as client:
        project_id = _create_project_with_ingested_text(client, "Run Config Diff")
        base_run_id = _run_project(
            client,
            project_id,
            payload={"mode": "author", "allow_unfinalized_character_map": True},
        )
        target_run_id = _run_project(
            client,
            project_id,
            payload={
                "mode": "academic",
                "allow_unfinalized_character_map": True,
                "deterministic_mode": True,
                "deterministic_seed": 2026,
                "export_formats": ["json", "csv"],
            },
        )

        diff_resp = client.get(
            f"/api/projects/{project_id}/runs/config-diff",
            params={"base_run_id": base_run_id, "target_run_id": target_run_id},
        )
        assert diff_resp.status_code == 200
        payload = diff_resp.json()

        assert payload["project_id"] == project_id
        assert payload["base_run_id"] == base_run_id
        assert payload["target_run_id"] == target_run_id
        assert payload["base_config_schema_version"] == "1.0.0"
        assert payload["target_config_schema_version"] == "1.0.0"
        assert payload["is_identical"] is False

        changed_field_names = [entry["field"] for entry in payload["changed_fields"]]
        assert changed_field_names == sorted(changed_field_names)
        changed_by_field = {entry["field"]: entry for entry in payload["changed_fields"]}
        assert changed_by_field["mode"]["base_value"] == "author"
        assert changed_by_field["mode"]["target_value"] == "academic"
        assert changed_by_field["deterministic_mode"]["base_value"] is False
        assert changed_by_field["deterministic_mode"]["target_value"] is True
        assert changed_by_field["export_formats"]["base_value"] == ["json", "csv", "time_series_json", "graph_json"]
        assert changed_by_field["export_formats"]["target_value"] == ["json", "csv"]
        assert "deterministic_seed" in payload["target_only_fields"]

        assert "configuration_snapshot_id" not in changed_by_field
        assert "configuration_snapshot_version" not in changed_by_field
        assert "configuration_snapshot_id" not in payload["base_only_fields"]
        assert "configuration_snapshot_id" not in payload["target_only_fields"]


def test_integration_run_config_diff_endpoint_rejects_same_run_id() -> None:
    with TestClient(app) as client:
        project_id = _create_project_with_ingested_text(client, "Run Config Diff Validation")
        run_id = _run_project(
            client,
            project_id,
            payload={"mode": "author", "allow_unfinalized_character_map": True},
        )

        diff_resp = client.get(
            f"/api/projects/{project_id}/runs/config-diff",
            params={"base_run_id": run_id, "target_run_id": run_id},
        )
        assert diff_resp.status_code == 400
        assert diff_resp.json()["detail"] == "base_run_id and target_run_id must be different."
