import io
import os
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_mode_profile_snapshot.db"

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.main import app
from app.modes import MODE_DEFAULT_PROFILES
from app.schemas import RunCreateRequest
from app.services.mode_profiles import build_run_config_snapshot


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_mode_profile_snapshot.db")
    if db_file.exists():
        db_file.unlink()


def _sample_txt() -> str:
    return (
        "Chapter 1\n"
        '"Sunny looked around," Sunny said. The cold wind cut through the street.\n\n'
        "Chapter 2\n"
        "Nephis smiled. Hope rose."
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


def test_unit_build_run_config_snapshot_keeps_profile_snapshot_and_applies_overrides() -> None:
    snapshot = build_run_config_snapshot(
        mode="author",
        overrides={
            "max_segment_chars": 144,
            "provider_name": "groq",
            "deep_semantic_refinement": True,
            "deterministic_mode": True,
        },
    )
    assert snapshot["mode"] == "author"
    assert snapshot["max_segment_chars"] == 144
    assert snapshot["provider_name"] == "groq"
    assert snapshot["deep_semantic_refinement"] is True
    assert snapshot["deterministic_mode"] is True
    assert snapshot["export_formats"] == ["json", "csv", "time_series_json", "graph_json"]
    assert snapshot["export_chunk_size"] == 500
    assert snapshot["mode_profile_snapshot"] == MODE_DEFAULT_PROFILES["author"]
    assert snapshot["mode_profile_snapshot"]["provider_name"] == "openrouter"


def test_unit_run_create_request_validates_emotion_taxonomy() -> None:
    payload = RunCreateRequest(mode="audiobook", emotion_taxonomy="expanded")
    assert payload.emotion_taxonomy == "expanded"


def test_unit_run_create_request_normalizes_export_formats() -> None:
    payload = RunCreateRequest(
        mode="audiobook",
        export_formats=["CSV", " json ", "csv", "time_series_json", "GRAPH_JSON"],
    )
    assert payload.export_formats == ["csv", "json", "time_series_json", "graph_json"]


def test_unit_run_create_request_rejects_invalid_export_formats() -> None:
    with pytest.raises(ValueError, match="export_formats must be one of: json, csv, time_series_json, graph_json"):
        RunCreateRequest(mode="audiobook", export_formats=["pdf", "json"])


def test_unit_run_create_request_rejects_empty_export_formats() -> None:
    with pytest.raises(ValueError, match="export_formats must contain at least one value"):
        RunCreateRequest(mode="audiobook", export_formats=["  "])


def test_unit_run_create_request_validates_export_chunk_size() -> None:
    payload = RunCreateRequest(mode="audiobook", export_chunk_size=50)
    assert payload.export_chunk_size == 50

    with pytest.raises(ValueError, match="greater than or equal to 1"):
        RunCreateRequest(mode="audiobook", export_chunk_size=0)


def test_unit_run_create_request_rejects_invalid_emotion_taxonomy() -> None:
    with pytest.raises(ValueError, match="emotion_taxonomy must be one of: basic, expanded"):
        RunCreateRequest(mode="audiobook", emotion_taxonomy="ultra")


def test_integration_run_config_stores_loaded_mode_profile_snapshot() -> None:
    with TestClient(app) as client:
        project_id = _create_project_with_ingested_text(client, "Mode Snapshot Integration")

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"mode": "academic"},
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        detail_resp = client.get(f"/api/projects/{project_id}/runs/{run_id}")
        assert detail_resp.status_code == 200
        config = detail_resp.json()["config"]
        assert config["mode"] == "academic"
        assert config["export_formats"] == ["json", "csv", "time_series_json", "graph_json"]
        assert config["export_chunk_size"] == 500
        assert config["max_segment_chars"] == MODE_DEFAULT_PROFILES["academic"]["max_segment_chars"]
        assert config["deterministic_mode"] is False
        assert config["mode_profile_snapshot"] == MODE_DEFAULT_PROFILES["academic"]
        assert config["mode_profile_snapshot"]["export_formats"] == ["json", "csv", "time_series_json", "graph_json"]
        assert config["mode_profile_snapshot"]["export_chunk_size"] == 500


def test_e2e_run_config_defaults_emotion_taxonomy_to_basic() -> None:
    with TestClient(app) as client:
        project_id = _create_project_with_ingested_text(client, "Emotion Taxonomy Default")

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"mode": "audiobook"},
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        detail_resp = client.get(f"/api/projects/{project_id}/runs/{run_id}")
        assert detail_resp.status_code == 200
        assert detail_resp.json()["config"]["emotion_taxonomy"] == "basic"


def test_e2e_run_config_persists_explicit_emotion_taxonomy() -> None:
    with TestClient(app) as client:
        project_id = _create_project_with_ingested_text(client, "Emotion Taxonomy Expanded")

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"mode": "academic", "emotion_taxonomy": "expanded"},
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        detail_resp = client.get(f"/api/projects/{project_id}/runs/{run_id}")
        assert detail_resp.status_code == 200
        assert detail_resp.json()["config"]["emotion_taxonomy"] == "expanded"


def test_e2e_run_config_uses_overrides_without_mutating_profile_snapshot() -> None:
    with TestClient(app) as client:
        project_id = _create_project_with_ingested_text(client, "Mode Snapshot E2E")

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={
                "mode": "audiobook",
                "max_segment_chars": 99,
                "llm_enabled": True,
                "provider_name": "siliconflow",
                "max_calls_per_day": 3,
            },
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        detail_resp = client.get(f"/api/projects/{project_id}/runs/{run_id}")
        assert detail_resp.status_code == 200
        config = detail_resp.json()["config"]
        assert config["max_segment_chars"] == 99
        assert config["llm_enabled"] is True
        assert config["deterministic_mode"] is False
        assert config["provider_name"] == "siliconflow"
        assert config["max_calls_per_day"] == 3
        assert config["mode_profile_snapshot"] == MODE_DEFAULT_PROFILES["audiobook"]
        assert config["export_formats"] == ["json", "csv", "time_series_json", "graph_json"]
        assert config["export_chunk_size"] == 500
        assert config["mode_profile_snapshot"]["provider_name"] == "openrouter"


def test_e2e_run_config_accepts_segmentation_target_length_alias() -> None:
    with TestClient(app) as client:
        project_id = _create_project_with_ingested_text(client, "Segmentation Target Alias")

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={
                "mode": "academic",
                "segmentation_target_length": 95,
                "allow_unfinalized_character_map": True,
            },
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        detail_resp = client.get(f"/api/projects/{project_id}/runs/{run_id}")
        assert detail_resp.status_code == 200
        config = detail_resp.json()["config"]
        assert config["max_segment_chars"] == 95
        assert config["mode"] == "academic"


def test_regression_custom_mode_snapshot_payload_shape() -> None:
    assert build_run_config_snapshot("custom") == {
        "mode": "custom",
        "max_segment_chars": 255,
        "export_formats": ["json", "csv", "time_series_json", "graph_json"],
        "export_chunk_size": 500,
        "llm_enabled": False,
        "provider_name": "openrouter",
        "max_calls_per_day": 25,
        "llm_confidence_threshold": 0.6,
        "speaker_confidence_threshold": 0.6,
        "high_ambiguity_dialogue_flag_threshold": 2,
        "unstable_emotion_shift_transition_threshold": 4,
        "unstable_emotion_shift_density_threshold": 0.5,
        "deep_semantic_refinement": False,
        "deterministic_mode": False,
        "web_scraping_enabled": False,
        "contradiction_review_required": True,
        "mode_profile_snapshot": {
            "max_segment_chars": 255,
            "export_formats": ["json", "csv", "time_series_json", "graph_json"],
            "export_chunk_size": 500,
            "llm_enabled": False,
            "provider_name": "openrouter",
            "max_calls_per_day": 25,
            "llm_confidence_threshold": 0.6,
            "speaker_confidence_threshold": 0.6,
            "high_ambiguity_dialogue_flag_threshold": 2,
            "unstable_emotion_shift_transition_threshold": 4,
            "unstable_emotion_shift_density_threshold": 0.5,
            "deep_semantic_refinement": False,
            "deterministic_mode": False,
            "web_scraping_enabled": False,
            "contradiction_review_required": True,
            "profile_intent": "user-tuned baseline with conservative defaults",
        },
    }


def test_integration_audiobook_target_length_config_is_respected_in_export_segments() -> None:
    long_text = (
        "Chapter 1\n"
        '"Hello," said the traveler. The traveler nodded and kept walking through the crowded streets. '
    ) * 20
    long_text = f"{long_text}\n\nChapter 2\n" + ('"Another day," the traveler said. ' * 20)

    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Segmentation target length"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", io.BytesIO(long_text.encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        default_run = client.post(
            f"/api/projects/{project_id}/runs",
            json={"mode": "audiobook"},
        )
        assert default_run.status_code == 200
        default_export = client.get(f"/api/projects/{project_id}/exports/{default_run.json()['run_id']}.json")
        assert default_export.status_code == 200
        default_segments = default_export.json()["segments"]
        assert all(len(segment["original_text"]) <= 120 for segment in default_segments)

        tuned_run = client.post(
            f"/api/projects/{project_id}/runs",
            json={"mode": "audiobook", "max_segment_chars": 80},
        )
        assert tuned_run.status_code == 200
        tuned_export = client.get(f"/api/projects/{project_id}/exports/{tuned_run.json()['run_id']}.json")
        assert tuned_export.status_code == 200
        tuned_segments = tuned_export.json()["segments"]
        assert all(len(segment["original_text"]) <= 80 for segment in tuned_segments)
        assert len(tuned_segments) >= len(default_segments)
