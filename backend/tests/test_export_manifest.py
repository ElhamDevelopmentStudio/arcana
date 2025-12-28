import io
import csv
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_export_manifest.db"

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

    db_file = Path("test_nipe_export_manifest.db")
    if db_file.exists():
        db_file.unlink()


def test_export_json_includes_manifest_metadata() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Manifest Package Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", io.BytesIO(b"Chapter 1\nThe lantern burned low and the rain beat softly outside."), "text/plain")},
        )
        assert ingest_resp.status_code == 200
        assert ingest_resp.json()["chapter_count"] == 1

        run_resp = client.post(f"/api/projects/{project_id}/runs", json={"max_segment_chars": 80})
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200
        export_payload = export_resp.json()

        assert export_payload["project_id"] == project_id
        assert export_payload["run_id"] == run_id
        assert export_payload["status"] == "completed"
        assert isinstance(export_payload["segments"], list)
        time_series = export_payload["time_series"]
        assert isinstance(time_series, dict)
        assert set(time_series.keys()) == {"emotion_valence", "emotion_intensity", "tension", "dominance"}
        assert len(time_series["emotion_valence"]) == len(export_payload["segments"])
        assert len(time_series["emotion_intensity"]) == len(export_payload["segments"])
        assert len(time_series["tension"]) == len(export_payload["segments"])
        assert len(time_series["dominance"]) == len(export_payload["segments"])
        first_point = time_series["emotion_valence"][0]
        assert first_point["position"] == 1
        assert first_point["value"] is not None

        manifest = export_payload.get("manifest")
        assert isinstance(manifest, dict)
        assert manifest["schema_version"] == "1.0.0"
        assert manifest["export_type"] == "audiobook_tts_package"
        assert manifest["export_format"] == "json"
        assert isinstance(manifest["generated_at"], str)
        assert manifest["segment_count"] == len(export_payload["segments"])
        assert manifest["ordered_by"] == ["chapter_index", "segment_index"]
        assert manifest["project"]["id"] == project_id
        assert manifest["project"]["title"] == "Manifest Package Project"
        assert manifest["project"]["configuration_snapshot_id"] is not None
        assert manifest["project"]["selected_mode"] == "audiobook"
        assert manifest["run"]["id"] == run_id
        assert manifest["run"]["status"] == "completed"
        assert isinstance(manifest["run"]["config_snapshot"], dict)

        project_snapshot = manifest["project_config_snapshot"]
        assert isinstance(project_snapshot, dict)
        assert project_snapshot["configuration_snapshot_id"] == manifest["project"]["configuration_snapshot_id"]
        assert project_snapshot["selected_mode"] == "audiobook"
        assert project_snapshot["selected_modes"] == ["audiobook"]
        assert project_snapshot["voice_config"]["narrator_voice"] == "narrator_default"
        assert project_snapshot["default_voices"]["narrator"] == "narrator_default"

        logs = manifest["logs"]
        assert isinstance(logs, dict)
        assert isinstance(logs["ingestion_log"], dict)
        assert logs["ingestion_log"]["source"] == "txt"
        assert isinstance(logs["llm_calls"], list)

        reports = manifest["reports"]
        assert isinstance(reports, dict)
        assert isinstance(reports["project"], dict)
        assert reports["run"]["id"] == run_id
        assert reports["run"]["segment_count"] == len(export_payload["segments"])
        assert reports["run"]["ordered_by"] == ["chapter_index", "segment_index"]
        assert reports["project"]["configuration_snapshot_id"] == manifest["project"]["configuration_snapshot_id"]
        assert isinstance(reports["normalization_report"], dict)
        assert reports["normalization_report"]["source"] == "txt"
        assert isinstance(reports["character_analytics_snapshot"], dict)
        assert isinstance(reports["mode_profile_snapshot"], dict)


def test_export_json_includes_warning_report_summary() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Manifest Warnings Report Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": (
                    "repair.txt",
                    io.BytesIO(b'Chapter 1\nHe said "Take cover on the east side.'),
                    "text/plain",
                )
            },
        )
        assert ingest_resp.status_code == 200
        assert ingest_resp.json()["chapter_count"] == 1

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"max_segment_chars": 80, "mode": "audiobook"},
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200
        manifest = export_resp.json()["manifest"]

        logs = manifest["logs"]["ingestion_log"]
        assert logs["source"] == "txt"
        warning_types = {item.get("type") for item in logs.get("warnings", [])}
        assert "quote_repair_confidence_low" in warning_types

        reports = manifest["reports"]
        assert reports["normalization_report"]["lossy_transform_flags"]["quote_repair_applied"] is True
        assert reports["normalization_report"]["counts"]["quote_repair_count"] >= 1


def test_export_csv_contains_tts_ready_segments() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Manifest CSV Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", io.BytesIO(b"Chapter 1\nThe lantern burned low and the rain beat softly outside."), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"max_segment_chars": 80, "allow_unfinalized_character_map": True},
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_csv_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.csv")
        assert export_csv_resp.status_code == 200
        assert export_csv_resp.headers["content-type"] == "text/csv; charset=utf-8"
        assert export_csv_resp.headers["content-disposition"] == f"attachment; filename=\"project-{project_id}-run-{run_id}.csv\""

        rows = list(csv.reader(export_csv_resp.text.splitlines()))
        assert len(rows) >= 2
        header = rows[0]
        assert "segment_id" in header
        assert "normalized_text" in header
        assert "phonetic_text" in header
        assert "resolved_voice_id" in header
        assert rows[1][header.index("segment_id")] != ""


def test_export_json_includes_project_config_snapshot_after_project_customization() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Manifest Project With Snapshot"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        switch_resp = client.put(f"/api/projects/{project_id}/mode", json={"mode": "academic"})
        assert switch_resp.status_code == 200
        assert "academic" in switch_resp.json()["selected_modes"]

        voice_resp = client.put(
            f"/api/projects/{project_id}/voices",
            json={
                "narrator_voice": "manifest_narrator_voice",
                "male_default_voice": "manifest_male_voice",
                "female_default_voice": "manifest_female_voice",
                "neutral_default_voice": "manifest_neutral_voice",
                "unknown_default_voice": "manifest_unknown_voice",
                "internal_thought_voice_policy": "thought_voice",
                "internal_thought_voice": "manifest_thought_voice",
            },
        )
        assert voice_resp.status_code == 200

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", io.BytesIO(b"Chapter 1\nQuietly, it came to pass."), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"mode": "academic", "allow_unfinalized_character_map": True},
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200
        export_payload = export_resp.json()
        manifest = export_payload.get("manifest")
        assert isinstance(manifest, dict)

        project_snapshot = manifest["project_config_snapshot"]
        assert project_snapshot["selected_mode"] == "academic"
        assert "academic" in project_snapshot["selected_modes"]
        assert project_snapshot["voice_config"]["narrator_voice"] == "manifest_narrator_voice"
        assert project_snapshot["default_voices"]["male"] == "manifest_male_voice"
        assert project_snapshot["default_voices"]["female"] == "manifest_female_voice"
        assert project_snapshot["voice_config"]["internal_thought_voice_policy"] == "thought_voice"
        assert project_snapshot["voice_config"]["thought_voice"] == "manifest_thought_voice"
