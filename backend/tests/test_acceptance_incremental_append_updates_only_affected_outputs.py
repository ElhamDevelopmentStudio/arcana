import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_acceptance_incremental_append_updates_only_affected_outputs.db"

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

    db_file = Path("test_nipe_acceptance_incremental_append_updates_only_affected_outputs.db")
    if db_file.exists():
        db_file.unlink()


def test_acceptance_incremental_append_updates_only_affected_outputs() -> None:
    baseline_run_payload = {
        "mode": "author",
        "max_segment_chars": 120,
        "llm_enabled": False,
        "provider_name": "openrouter",
        "max_calls_per_day": 5,
        "allow_unfinalized_character_map": True,
        "deterministic_mode": True,
        "deterministic_seed": 20260226,
        "randomization_config": {"strategy": "stable", "shuffle_enabled": False},
    }

    incremental_run_payload = {
        **baseline_run_payload,
        "incremental_recompute": True,
    }

    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "ACC-009 Incremental Append Scope"})
        assert project_resp.status_code == 201
        project_id = int(project_resp.json()["id"])

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": (
                    "incremental-source.txt",
                    io.BytesIO(
                        (
                            "Chapter 1\n"
                            "Moonlit waves battered the harbor wall through the night.\n\n"
                            "Chapter 2\n"
                            "At dawn, the sentries found fresh tracks by the eastern gate."
                        ).encode("utf-8")
                    ),
                    "text/plain",
                )
            },
        )
        assert ingest_resp.status_code == 200

        baseline_run_resp = client.post(f"/api/projects/{project_id}/runs", json=baseline_run_payload)
        assert baseline_run_resp.status_code == 200
        baseline_run_id = int(baseline_run_resp.json()["run_id"])

        baseline_export_resp = client.get(f"/api/projects/{project_id}/exports/{baseline_run_id}.json")
        assert baseline_export_resp.status_code == 200
        baseline_export_payload = baseline_export_resp.json()
        assert baseline_export_payload["status"] == "completed"
        baseline_segments = baseline_export_payload["segments"]
        assert baseline_segments

        append_resp = client.post(
            f"/api/projects/{project_id}/ingest/append-chapter",
            files={
                "file": (
                    "append-chapter-3.txt",
                    io.BytesIO(
                        (
                            "Chapter 3\n"
                            "The bells rang once, then silence spread over the flooded square."
                        ).encode("utf-8")
                    ),
                    "text/plain",
                )
            },
        )
        assert append_resp.status_code == 200

        incremental_run_resp = client.post(f"/api/projects/{project_id}/runs", json=incremental_run_payload)
        assert incremental_run_resp.status_code == 200
        incremental_run_id = int(incremental_run_resp.json()["run_id"])

        incremental_export_resp = client.get(f"/api/projects/{project_id}/exports/{incremental_run_id}.json")
        assert incremental_export_resp.status_code == 200
        incremental_export_payload = incremental_export_resp.json()
        assert incremental_export_payload["status"] == "completed"
        incremental_segments = incremental_export_payload["segments"]
        assert incremental_segments

        max_baseline_chapter_id = max(int(segment["chapter_id"]) for segment in baseline_segments)
        incremental_prefix_segments = [
            segment for segment in incremental_segments if int(segment["chapter_id"]) <= max_baseline_chapter_id
        ]
        incremental_appended_segments = [
            segment for segment in incremental_segments if int(segment["chapter_id"]) > max_baseline_chapter_id
        ]

        assert incremental_prefix_segments == baseline_segments
        assert incremental_appended_segments

