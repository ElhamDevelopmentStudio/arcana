import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_mode_switch_stale.db"

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.main import app
from app.models import Run
from app.services.mode_switch import mark_runs_stale_for_mode_switch


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_mode_switch_stale.db")
    if db_file.exists():
        db_file.unlink()


def _sample_txt() -> str:
    return (
        "Chapter 1\n"
        '"Sunny looked around," Sunny said. The cold wind cut through the dark street.\n\n'
        "Chapter 2\n"
        "Nephis smiled. Hope rose with the warm light."
    )


def _create_project_with_ingested_text(client: TestClient, title: str) -> int:
    project_resp = client.post("/api/projects", json={"title": title})
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    ingest_resp = client.post(
        f"/api/projects/{project_id}/ingest/txt",
        files={"file": ("sample.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
    )
    assert ingest_resp.status_code == 200
    return project_id


def _run_pipeline(client: TestClient, project_id: int, mode: str) -> int:
    run_resp = client.post(
        f"/api/projects/{project_id}/runs",
        json={"mode": mode},
    )
    assert run_resp.status_code == 200
    return int(run_resp.json()["run_id"])


def test_unit_mark_runs_stale_sets_flag_for_non_matching_modes_only() -> None:
    run_a = Run(project_id=1, status="completed", config_json={"mode": "audiobook"})
    run_b = Run(project_id=1, status="completed", config_json={"mode": "author"})

    marked = mark_runs_stale_for_mode_switch([run_a, run_b], selected_mode="author")

    assert marked == 1
    assert run_a.config_json["artifacts_stale"] is True
    assert run_a.config_json["stale_on_mode"] == "author"
    assert "stale_marked_at" in run_a.config_json
    assert "artifacts_stale" not in run_b.config_json


def test_integration_mode_switch_marks_existing_runs_stale_when_mode_changes() -> None:
    with TestClient(app) as client:
        project_id = _create_project_with_ingested_text(client, "Mode Switch Stale Integration")
        run_id = _run_pipeline(client, project_id, "audiobook")

        switch_resp = client.put(f"/api/projects/{project_id}/mode", json={"mode": "academic"})
        assert switch_resp.status_code == 200
        assert switch_resp.json()["stale_runs_marked"] == 1

        detail_resp = client.get(f"/api/projects/{project_id}/runs/{run_id}")
        assert detail_resp.status_code == 200
        config = detail_resp.json()["config"]
        assert config["mode"] == "audiobook"
        assert config["artifacts_stale"] is True
        assert config["stale_reason"] == "mode_switched"
        assert config["stale_on_mode"] == "academic"


def test_e2e_same_mode_switch_does_not_mark_runs_stale() -> None:
    with TestClient(app) as client:
        project_id = _create_project_with_ingested_text(client, "Mode Switch Stale E2E")
        run_id = _run_pipeline(client, project_id, "author")

        switch_resp = client.put(f"/api/projects/{project_id}/mode", json={"mode": "author"})
        assert switch_resp.status_code == 200
        assert switch_resp.json()["stale_runs_marked"] == 0

        detail_resp = client.get(f"/api/projects/{project_id}/runs/{run_id}")
        assert detail_resp.status_code == 200
        config = detail_resp.json()["config"]
        assert "artifacts_stale" not in config


def test_regression_mode_switch_response_includes_stale_count_field() -> None:
    with TestClient(app) as client:
        project_id = _create_project_with_ingested_text(client, "Mode Switch Stale Regression")
        _ = _run_pipeline(client, project_id, "custom")

        switch_resp = client.put(f"/api/projects/{project_id}/mode", json={"mode": "audiobook"})
        assert switch_resp.status_code == 200
        payload = switch_resp.json()
        assert set(payload.keys()) == {
            "project_id",
            "previous_mode",
            "selected_mode",
            "selected_modes",
            "chapter_count",
            "reused_ingested_corpus",
            "stale_runs_marked",
        }
        assert payload["stale_runs_marked"] == 1
