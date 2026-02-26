import io
import csv
import os
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_export_manifest.db"

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.schemas import NarrativeHealthReport
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
        assert set(time_series.keys()) == {
            "emotion_valence",
            "emotion_intensity",
            "tension",
            "dominance",
            "emotion_delta",
            "scene_states",
            "volatility_markers",
            "avoid_abrupt_change_hints",
        }
        assert len(time_series["emotion_valence"]) == len(export_payload["segments"])
        assert len(time_series["emotion_intensity"]) == len(export_payload["segments"])
        assert len(time_series["tension"]) == len(export_payload["segments"])
        assert len(time_series["dominance"]) == len(export_payload["segments"])
        assert len(time_series["scene_states"]) == len(export_payload["segments"])
        if len(export_payload["segments"]) > 1:
            assert len(time_series["emotion_delta"]) == len(export_payload["segments"]) - 1
            assert set(time_series["emotion_delta"][0].keys()) >= {
                "position",
                "segment_id",
                "from_segment_id",
                "valence_delta",
                "intensity_delta",
            }
            assert len(time_series["avoid_abrupt_change_hints"]) == len(export_payload["segments"]) - 1
            abrupt_hint = time_series["avoid_abrupt_change_hints"][0]
            assert set(abrupt_hint.keys()) >= {
                "position",
                "from_segment_id",
                "segment_id",
                "avoid",
                "severity",
                "volatility_index",
                "fields_to_smooth",
                "suggestions",
                "from_raw_tags",
                "to_raw_tags",
            }
            assert isinstance(abrupt_hint["severity"], str)
            assert abrupt_hint["severity"] in {"low", "moderate", "high"}
            first_segment = export_payload["segments"][0]
            second_segment = export_payload["segments"][1]
            assert abrupt_hint["from_raw_tags"]["type"] == first_segment["type"]
            assert abrupt_hint["to_raw_tags"]["type"] == second_segment["type"]
            assert abrupt_hint["suggestions"]["preserve_raw_tags"] is True
            assert len(time_series["volatility_markers"]) == len(export_payload["segments"]) - 1
            volatility_marker = time_series["volatility_markers"][0]
            assert set(volatility_marker.keys()) >= {
                "position",
                "from_segment_id",
                "segment_id",
                "volatility_index",
                "level",
            }
            assert volatility_marker["level"] in {"low", "moderate", "high"}
        first_point = time_series["emotion_valence"][0]
        assert first_point["position"] == 1
        assert first_point["value"] is not None
        first_scene_state = time_series["scene_states"][0]
        assert first_scene_state["position"] == 1
        assert first_scene_state["segment_id"] == export_payload["segments"][0]["segment_id"]
        assert isinstance(first_scene_state["state"], str)
        assert isinstance(first_scene_state["reasons"], list)
        assert isinstance(first_scene_state["evidence"], dict)
        segment_order = [(segment["chapter_id"], segment["segment_index"]) for segment in export_payload["segments"]]
        assert segment_order == sorted(segment_order, key=lambda item: (item[0], item[1]))

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


def test_export_json_includes_narrative_health_report_schema() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Narrative Health Report Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": (
                    "sample.txt",
                    io.BytesIO(
                        b'Chapter 1\nHe opened the window and breathed in the cold air. "Keep moving," she whispered.\n\n'
                        b"Chapter 2\nFootsteps echoed down the hall as dawn arrived too late."
                    ),
                    "text/plain",
                )
            },
        )
        assert ingest_resp.status_code == 200
        assert ingest_resp.json()["chapter_count"] == 2

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"mode": "author", "max_segment_chars": 80},
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200
        manifest = export_resp.json()["manifest"]

        narrative_health_report = manifest.get("narrative_health_report")
        assert isinstance(narrative_health_report, dict)

        parsed_report = NarrativeHealthReport.model_validate(narrative_health_report)
        assert parsed_report.output_schema == "author_narrative_health_json"
        assert parsed_report.generated_by == "build_run_export"
        assert parsed_report.project_reference["project_id"] == project_id
        assert parsed_report.run_reference["run_id"] == run_id

        requirement_ids = [entry.requirement_id for entry in parsed_report.requirements]
        assert requirement_ids == ["ADR-001", "ADR-002", "ADR-003", "ADR-004", "ADR-005", "ADR-006"]
        status_by_requirement = {entry.requirement_id: entry.status for entry in parsed_report.requirements}
        assert status_by_requirement["ADR-002"] == "implemented"
        assert status_by_requirement["ADR-001"] == "not_implemented"
        assert status_by_requirement["ADR-003"] == "implemented"
        assert status_by_requirement["ADR-005"] == "implemented"
        assert status_by_requirement["ADR-004"] == "not_implemented"
        assert status_by_requirement["ADR-006"] == "implemented"
        assert all(entry.finding_count == len(entry.findings) for entry in parsed_report.requirements)
        assert isinstance(narrative_health_report.get("chapter_type_classification"), list)
        assert len(narrative_health_report["chapter_type_classification"]) >= 1
        for chapter_type in narrative_health_report["chapter_type_classification"]:
            assert chapter_type["chapter_id"] >= 1
            assert chapter_type["confidence"] >= 0.0
            assert chapter_type["chapter_type"] in {
                "setup",
                "build-up",
                "confrontation",
                "resolution",
                "transitional",
            }


def test_export_json_supports_author_output_schema() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Author Output Schema Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": (
                    "sample.txt",
                    io.BytesIO(
                        b"Chapter 1\nA cold wind pushed through the hall and the lamp light flickered.\n\n"
                        b"Chapter 2\nFootsteps in the corridor grew louder as the truth emerged."
                    ),
                    "text/plain",
                )
            },
        )
        assert ingest_resp.status_code == 200
        assert ingest_resp.json()["chapter_count"] == 2

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"mode": "author", "max_segment_chars": 80},
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        report_resp = client.get(
            f"/api/projects/{project_id}/exports/{run_id}.json",
            params={"output_schema": "author"},
        )
        assert report_resp.status_code == 200

        payload = report_resp.json()
        parsed_report = NarrativeHealthReport.model_validate(payload)
        assert parsed_report.output_schema == "author_narrative_health_json"
        assert parsed_report.generated_by == "build_run_export"
        assert parsed_report.project_reference["project_id"] == project_id
        assert parsed_report.run_reference["run_id"] == run_id
        assert isinstance(parsed_report.chapter_type_classification, list)


def test_export_json_rejects_unknown_output_schema() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Unknown Output Schema Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": (
                    "sample.txt",
                    io.BytesIO(
                        b"Chapter 1\nA quick sample line to bootstrap exports."
                    ),
                    "text/plain",
                )
            },
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(f"/api/projects/{project_id}/runs", json={"max_segment_chars": 80})
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        report_resp = client.get(
            f"/api/projects/{project_id}/exports/{run_id}.json",
            params={"output_schema": "unsupported"},
        )
        assert report_resp.status_code == 400
        assert report_resp.json()["detail"].startswith("Unsupported output_schema")


def test_export_json_includes_chapter_level_valence_means() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Manifest ACAD-001 Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": (
                    "sample.txt",
                    io.BytesIO(
                        (
                            "Chapter 1\n"
                            "The lantern burned low and the rain beat softly outside. "
                            "A detective wrote in a notebook with careful hands and deliberate pauses. "
                            "He heard the floorboards groan behind him once more, then again.\n\n"
                            "Chapter 2\n"
                            "The hallway narrowed and the air smelled of dust and damp stone. "
                            "Footsteps echoed from the stairwell while shutters rattled against wind. "
                            "Every thought seemed to ask a louder question than before."
                        ).encode("utf-8")
                    ),
                    "text/plain",
                )
            },
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"max_segment_chars": 100, "allow_unfinalized_character_map": True},
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200
        export_payload = export_resp.json()

        academic_reports = export_payload["manifest"].get("academic_reports")
        assert isinstance(academic_reports, dict)

        means = academic_reports.get("chapter_level_valence_means")
        assert isinstance(means, list)
        assert means, "Expected at least one chapter mean entry"

        by_chapter: dict[int, list[float]] = {}
        for segment in export_payload["segments"]:
            chapter_id = segment.get("chapter_id")
            valence = segment.get("emotion_valence")
            if isinstance(chapter_id, int) and isinstance(valence, (int, float)):
                by_chapter.setdefault(chapter_id, []).append(float(valence))

        assert len(means) == len(by_chapter)

        for chapter_mean in means:
            assert set(chapter_mean.keys()) >= {
                "chapter_id",
                "valence_mean",
                "segment_count",
            }
            chapter_id = chapter_mean["chapter_id"]
            assert chapter_id in by_chapter

            values = by_chapter[chapter_id]
            expected_mean = round(sum(values) / len(values), 4)
            assert chapter_mean["segment_count"] == len(values)
            assert chapter_mean["valence_mean"] == expected_mean


def test_export_json_includes_chapter_level_valence_variance() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Manifest ACAD-002 Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": (
                    "sample.txt",
                    io.BytesIO(
                        (
                            "Chapter 1\n"
                            "Clouds gathered over the city as bells rang in the distance. "
                            "Someone knocked once, then waited. "
                            "The hallway stayed silent. "
                            "A second knock cracked the darkened air into something more urgent.\n\n"
                            "Chapter 2\n"
                            "By dawn the detective had already checked every door twice. "
                            "He wrote down names, suspects, and every impossible detail he could remember. "
                            "The dawn did not answer."
                        ).encode("utf-8")
                    ),
                    "text/plain",
                )
            },
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"max_segment_chars": 120, "allow_unfinalized_character_map": True},
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200
        export_payload = export_resp.json()

        academic_reports = export_payload["manifest"].get("academic_reports")
        assert isinstance(academic_reports, dict)

        variance = academic_reports.get("chapter_level_valence_variance")
        assert isinstance(variance, list)
        assert variance, "Expected at least one chapter variance entry"

        by_chapter: dict[int, list[float]] = {}
        for segment in export_payload["segments"]:
            chapter_id = segment.get("chapter_id")
            valence = segment.get("emotion_valence")
            if isinstance(chapter_id, int) and isinstance(valence, (int, float)):
                by_chapter.setdefault(chapter_id, []).append(float(valence))

        assert len(variance) == len(by_chapter)

        for chapter_variance in variance:
            assert set(chapter_variance.keys()) >= {
                "chapter_id",
                "valence_variance",
                "segment_count",
            }
            chapter_id = chapter_variance["chapter_id"]
            assert chapter_id in by_chapter

            values = by_chapter[chapter_id]
            assert chapter_variance["segment_count"] == len(values)
            expected_mean = sum(values) / len(values)
            expected_variance = round(sum((value - expected_mean) ** 2 for value in values) / len(values), 4)
            assert chapter_variance["valence_variance"] == expected_variance


def test_export_json_includes_chapter_level_emotional_volatility_index() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Manifest ACAD-003 Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": (
                    "sample.txt",
                    io.BytesIO(
                        (
                            "Chapter 1\n"
                            "The rain came down in a steady rhythm while footsteps moved on the stairs.\n"
                            "A single window blinked with the reflection of distant lights and then vanished.\n"
                            "Every room in the house felt a little too aware.\n"
                            "He closed the door quietly and listened for breath.\n\n"
                            "Chapter 2\n"
                            "By morning the corridor hummed with voices and papers scraping on the table.\n"
                            "Someone moved quickly and a drawer slammed hard.\n"
                            "The detective counted three sets of keys before dawn."
                        ).encode("utf-8")
                    ),
                    "text/plain",
                )
            },
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"max_segment_chars": 100, "allow_unfinalized_character_map": True},
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200
        export_payload = export_resp.json()

        academic_reports = export_payload["manifest"].get("academic_reports")
        assert isinstance(academic_reports, dict)

        volatility_indexes = academic_reports.get("chapter_level_emotional_volatility_index")
        assert isinstance(volatility_indexes, list)
        assert volatility_indexes, "Expected at least one chapter volatility entry"

        volatility_by_chapter: dict[int, list[float]] = {}
        segment_by_id: dict[str, int] = {}
        for segment in export_payload["segments"]:
            if isinstance(segment.get("segment_id"), str) and isinstance(segment.get("chapter_id"), int):
                segment_by_id[segment["segment_id"]] = segment["chapter_id"]

        for marker in export_payload["time_series"]["volatility_markers"]:
            segment_id = marker.get("segment_id")
            if not isinstance(segment_id, str):
                continue
            chapter_id = segment_by_id.get(segment_id)
            if chapter_id is None:
                continue
            volatility_by_chapter.setdefault(chapter_id, []).append(float(marker.get("volatility_index")))

        assert len(volatility_indexes) == len(volatility_by_chapter)

        for chapter_volatility in volatility_indexes:
            assert set(chapter_volatility.keys()) >= {
                "chapter_id",
                "emotional_volatility_index",
                "segment_count",
            }
            chapter_id = chapter_volatility["chapter_id"]
            assert chapter_id in volatility_by_chapter

            values = volatility_by_chapter[chapter_id]
            assert chapter_volatility["segment_count"] == len(values)
            assert values, "Expected at least one volatility transition per included chapter"
            expected_index = round(sum(values) / len(values), 4)
            assert chapter_volatility["emotional_volatility_index"] == expected_index


def test_export_json_includes_rolling_window_emotional_curves() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Manifest ACAD-004 Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": (
                    "sample.txt",
                    io.BytesIO(
                        (
                            "Chapter 1\n"
                            "The city slept under a gray sky while fog rolled along the river.\n"
                            "A clock struck three and no one answered to the call.\n"
                            "Footsteps stopped near the archive and returned to silence.\n"
                            "Ink on paper waited for the truth that might never arrive.\n"
                            "Only the heater hissed beneath the closed door.\n\n"
                            "Chapter 2\n"
                            "By dawn, messages had stacked in the corridor like unpaid debts.\n"
                            "The detective finally saw the pattern and nearly laughed.\n"
                            "Someone was waiting outside with the wrong name."
                        ).encode("utf-8")
                    ),
                    "text/plain",
                )
            },
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"max_segment_chars": 90, "allow_unfinalized_character_map": True},
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200
        export_payload = export_resp.json()

        academic_reports = export_payload["manifest"].get("academic_reports")
        assert isinstance(academic_reports, dict)

        rolling_reports = academic_reports.get("rolling_window_emotional_curves")
        assert isinstance(rolling_reports, dict)
        assert isinstance(rolling_reports.get("window_size"), int)
        assert rolling_reports["window_size"] == 5

        valence_curve = rolling_reports.get("valence_curve")
        intensity_curve = rolling_reports.get("intensity_curve")
        assert isinstance(valence_curve, list)
        assert isinstance(intensity_curve, list)
        assert len(valence_curve) == len(export_payload["segments"])
        assert len(intensity_curve) == len(export_payload["segments"])

        values_valence: list[float] = [
            float(segment.get("emotion_valence", 0.0)) for segment in export_payload["segments"]
        ]
        values_intensity: list[float] = [
            float(segment.get("emotion_intensity", 0.0)) for segment in export_payload["segments"]
        ]

        for i, segment in enumerate(export_payload["segments"]):
            start = max(0, i - 4)
            expected_valence = round(
                sum(values_valence[start : i + 1]) / (i - start + 1),
                4,
            )
            expected_intensity = round(
                sum(values_intensity[start : i + 1]) / (i - start + 1),
                4,
            )
            valence_point = valence_curve[i]
            intensity_point = intensity_curve[i]

            assert valence_point["position"] == i + 1
            assert intensity_point["position"] == i + 1
            assert valence_point["segment_id"] == segment["segment_id"]
            assert intensity_point["segment_id"] == segment["segment_id"]
            assert valence_point["rolling_mean_valence"] == expected_valence
            assert intensity_point["rolling_mean_intensity"] == expected_intensity


def test_export_json_includes_chapter_level_raw_tension() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Manifest ACAD-005 Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": (
                    "sample.txt",
                    io.BytesIO(
                        (
                            "Chapter 1\n"
                            "The cellar door stayed locked, though the air was thick with dust.\n"
                            "A brass key clinked once against the desk leg.\n"
                            "Nothing moved, then the floor groaned twice.\n"
                            "Someone stood still at the far end and watched.\n\n"
                            "Chapter 2\n"
                            "She pulled the ledger from the shelf and found three pages torn out.\n"
                            "Every missing line looked like a threat."
                        ).encode("utf-8")
                    ),
                    "text/plain",
                )
            },
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"max_segment_chars": 90, "allow_unfinalized_character_map": True},
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200
        export_payload = export_resp.json()

        academic_reports = export_payload["manifest"].get("academic_reports")
        assert isinstance(academic_reports, dict)

        raw_tension = academic_reports.get("chapter_level_raw_tension")
        assert isinstance(raw_tension, list)
        assert raw_tension, "Expected at least one chapter raw tension entry"

        tensions_by_chapter: dict[int, list[float]] = {}
        for segment in export_payload["segments"]:
            chapter_id = segment.get("chapter_id")
            if not isinstance(chapter_id, int):
                continue
            tension_data = segment.get("tension_contribution")
            if not isinstance(tension_data, dict):
                tension_data = segment.get("tag_bundle", {}).get("tension", {})
            if not isinstance(tension_data, dict):
                continue
            tension_value = tension_data.get("value")
            if not isinstance(tension_value, (int, float)):
                continue
            tensions_by_chapter.setdefault(chapter_id, []).append(float(tension_value))

        assert len(raw_tension) == len(tensions_by_chapter)

        for chapter_entry in raw_tension:
            assert set(chapter_entry.keys()) >= {
                "chapter_id",
                "raw_tension_mean",
                "raw_tension_sum",
                "segment_count",
            }
            chapter_id = chapter_entry["chapter_id"]
            assert chapter_id in tensions_by_chapter

            values = tensions_by_chapter[chapter_id]
            assert len(values) == chapter_entry["segment_count"]
            expected_sum = round(sum(values), 4)
            expected_mean = round(sum(values) / len(values), 4)
            assert chapter_entry["raw_tension_sum"] == expected_sum
            assert chapter_entry["raw_tension_mean"] == expected_mean


def test_export_json_includes_smoothed_tension_curve() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Manifest ACAD-006 Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": (
                    "sample.txt",
                    io.BytesIO(
                        (
                            "Chapter 1\n"
                            "The lantern burned low and the rain beat softly outside.\n"
                            "A detective wrote in a notebook with careful hands and deliberate pauses.\n"
                            "He heard the floorboards groan behind him, then again, softly.\n\n"
                            "Chapter 2\n"
                            "Shutters rattled as footsteps approached from the stairwell.\n"
                            "The air grew colder with each breath, and no one came through the door.\n"
                            "The lock turned, but it was already empty."
                        ).encode("utf-8")
                    ),
                    "text/plain",
                )
            },
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"max_segment_chars": 90, "allow_unfinalized_character_map": True},
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200
        export_payload = export_resp.json()

        academic_reports = export_payload["manifest"].get("academic_reports")
        assert isinstance(academic_reports, dict)

        smoothed_curve_report = academic_reports.get("smoothed_tension_curve")
        assert isinstance(smoothed_curve_report, dict)
        assert isinstance(smoothed_curve_report.get("window_size"), int)
        assert smoothed_curve_report["window_size"] == 5

        tension_curve = smoothed_curve_report.get("tension_curve")
        assert isinstance(tension_curve, list)
        assert len(tension_curve) == len(export_payload["segments"])

        values_tension: list[float] = []
        for segment in export_payload["segments"]:
            tension_data = segment.get("tension_contribution")
            if not isinstance(tension_data, dict):
                tension_data = segment.get("tag_bundle", {}).get("tension", {})
            if not isinstance(tension_data, dict):
                values_tension.append(0.0)
                continue
            tension_value = tension_data.get("value")
            values_tension.append(float(tension_value) if isinstance(tension_value, (int, float)) else 0.0)

        for i, segment in enumerate(export_payload["segments"]):
            start = max(0, i - 4)
            expected_tension = round(
                sum(values_tension[start : i + 1]) / (i - start + 1),
                4,
            )
            tension_point = tension_curve[i]
            assert tension_point["position"] == i + 1
            assert tension_point["segment_id"] == segment["segment_id"]
            assert tension_point["smoothed_tension"] == expected_tension


def test_export_json_includes_tension_peak_markers() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Manifest ACAD-007 Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": (
                    "sample.txt",
                    io.BytesIO(
                        (
                            "Chapter 1\n"
                            "The lock clicked loudly and somebody sprinted down the hall.\n"
                            "A scream echoed behind the wall as glass shattered.\n"
                            "Then silence returned, calm and airless.\n"
                            "Footsteps slowed. A calm voice whispered, \"it's over.\"\n"
                            "A loud crash followed, then a second scream.\n\n"
                            "Chapter 2\n"
                            "Rain fell outside while the room stayed still.\n"
                            "The tension dropped to near zero as dawn seeped through the blinds.\n"
                            "She smiled, softly, at the first bird call.\n"
                            "The day finally began."
                        ).encode("utf-8")
                    ),
                    "text/plain",
                )
            },
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"max_segment_chars": 80, "allow_unfinalized_character_map": True},
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200
        export_payload = export_resp.json()

        academic_reports = export_payload["manifest"].get("academic_reports")
        assert isinstance(academic_reports, dict)

        smoothed_curve_report = academic_reports.get("smoothed_tension_curve")
        assert isinstance(smoothed_curve_report, dict)
        tension_curve = smoothed_curve_report.get("tension_curve")
        assert isinstance(tension_curve, list)

        tension_peak_report = academic_reports.get("tension_peak_markers")
        assert isinstance(tension_peak_report, dict)
        peaks = tension_peak_report.get("peaks")
        assert isinstance(peaks, list)
        assert isinstance(tension_peak_report.get("major_peak_count"), int)
        assert isinstance(tension_peak_report.get("minor_peak_count"), int)
        assert isinstance(tension_peak_report.get("peak_count"), int)
        assert tension_peak_report["peak_count"] == len(peaks)

        values_smoothed: list[float] = [float(point["smoothed_tension"]) for point in tension_curve]

        expected_peaks: list[dict[str, Any]] = []
        for index in range(1, len(values_smoothed) - 1):
            prev_value = values_smoothed[index - 1]
            current_value = values_smoothed[index]
            next_value = values_smoothed[index + 1]
            if not (current_value > prev_value and current_value > next_value):
                continue

            prominence = round(current_value - max(prev_value, next_value), 4)
            segment = export_payload["segments"][index]
            if current_value >= 0.55 and prominence >= 0.18:
                severity = "major"
            elif current_value >= 0.40 and prominence >= 0.10:
                severity = "minor"
            else:
                continue

            expected_peaks.append(
                {
                    "position": index + 1,
                    "segment_id": segment["segment_id"],
                    "chapter_id": segment["chapter_id"],
                    "segment_index": segment["segment_index"],
                    "peak_type": "tension_peak",
                    "severity": severity,
                    "prominence": prominence,
                    "tension_value": round(current_value, 4),
                    "neighbors": {
                        "previous_tension": round(prev_value, 4),
                        "next_tension": round(next_value, 4),
                    },
                }
            )

        assert tension_peak_report["major_peak_count"] == len(
            [peak for peak in peaks if peak.get("severity") == "major"]
        )
        assert tension_peak_report["minor_peak_count"] == len(
            [peak for peak in peaks if peak.get("severity") == "minor"]
        )
        assert tension_peak_report["prominence_thresholds"] == {
            "major": 0.18,
            "minor": 0.10,
        }
        assert len(peaks) == len(expected_peaks)
        for expected_peak, actual_peak in zip(expected_peaks, peaks):
            assert expected_peak == actual_peak


def test_export_json_includes_tension_plateau_regions() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Manifest ACAD-008 Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": (
                    "sample.txt",
                    io.BytesIO(
                        (
                            "Chapter 1\n"
                            "The rain tapped on the old shingles while the fire stayed low.\n"
                            "He set the tea down and listened, then listened again.\n"
                            "A soft knock came from the attic and no one answered.\n"
                            "The hallway remained empty as the hour slowly passed.\n"
                            "Another soft knock came from deeper in the dark.\n"
                            "By then the quiet had become a pressure in his chest.\n"
                            "The pressure stayed, steady and patient.\n\n"
                            "Chapter 2\n"
                            "Outside, the storm moved farther off.\n"
                            "The same low hum of rain returned once more.\n"
                            "The quiet returned, low and constant.\n"
                            "Nothing changed for the next sentence either."
                        ).encode("utf-8")
                    ),
                    "text/plain",
                )
            },
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"max_segment_chars": 80, "allow_unfinalized_character_map": True},
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200
        export_payload = export_resp.json()

        academic_reports = export_payload["manifest"].get("academic_reports")
        assert isinstance(academic_reports, dict)

        smoothed_curve_report = academic_reports.get("smoothed_tension_curve")
        assert isinstance(smoothed_curve_report, dict)
        tension_curve = smoothed_curve_report.get("tension_curve")
        assert isinstance(tension_curve, list)
        assert len(tension_curve) == len(export_payload["segments"])

        plateau_report = academic_reports.get("tension_plateau_regions")
        assert isinstance(plateau_report, dict)
        assert isinstance(plateau_report.get("flatness_tolerance"), float)
        assert plateau_report["flatness_tolerance"] == 0.05
        assert plateau_report["min_region_length"] == 3
        regions = plateau_report.get("regions")
        assert isinstance(regions, list)

        values_smoothed: list[float] = []
        for point in tension_curve:
            smoothed_value = point.get("smoothed_tension")
            assert isinstance(smoothed_value, (int, float))
            values_smoothed.append(float(smoothed_value))

        expected_regions: list[dict[str, Any]] = []
        min_region_length = 3
        tolerance = 0.05
        index = 0
        while index < len(values_smoothed):
            region_end = index + 1
            while region_end < len(values_smoothed) and abs(
                values_smoothed[region_end] - values_smoothed[region_end - 1]
            ) <= tolerance:
                region_end += 1

            region_length = region_end - index
            if region_length >= min_region_length:
                region_slice = tension_curve[index:region_end]
                region_values = values_smoothed[index:region_end]
                region_segment_ids: list[str] = []
                region_segment_indices: list[int] = []
                region_chapters: list[int] = []

                for region_point in region_slice:
                    segment_id = region_point.get("segment_id")
                    segment_index = region_point.get("segment_index")
                    chapter_id = region_point.get("chapter_id")
                    if isinstance(segment_id, str):
                        region_segment_ids.append(segment_id)
                    if isinstance(segment_index, int):
                        region_segment_indices.append(segment_index)
                    if isinstance(chapter_id, int):
                        region_chapters.append(chapter_id)

                unique_chapters: list[int] = []
                for chapter_id in region_chapters:
                    if chapter_id not in unique_chapters:
                        unique_chapters.append(chapter_id)

                expected_regions.append(
                    {
                        "region_type": "tension_plateau",
                        "start_position": region_slice[0].get("position"),
                        "end_position": region_slice[-1].get("position"),
                        "length": region_length,
                        "segment_count": region_length,
                        "segment_ids": region_segment_ids,
                        "segment_indices": region_segment_indices,
                        "chapter_ids": unique_chapters,
                        "average_tension": round(sum(region_values) / region_length, 4),
                        "tension_value_range": {
                            "min": round(min(region_values), 4),
                            "max": round(max(region_values), 4),
                            "delta": round(max(region_values) - min(region_values), 4),
                        },
                    }
                )

            index = region_end

        assert plateau_report["plateau_region_count"] == len(expected_regions)
        assert len(regions) == len(expected_regions)
        for expected_region, actual_region in zip(expected_regions, regions):
            assert expected_region == actual_region


def test_export_json_includes_chapter_level_character_dominance() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Manifest ACAD-009 Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        characters_payload = {
            "characters": [
                {
                    "name": "Alice",
                    "verbalized_form": "Alice",
                    "gender": "female",
                    "aliases": ["A"],
                    "source": "manual",
                    "confidence": 1.0,
                },
                {
                    "name": "Bob",
                    "verbalized_form": "Bob",
                    "gender": "male",
                    "aliases": ["B"],
                    "source": "manual",
                    "confidence": 1.0,
                },
            ]
        }
        assert client.put(f"/api/projects/{project_id}/characters", json=characters_payload).status_code == 200

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": (
                        "sample.txt",
                        io.BytesIO(
                            (
                                "Chapter 1\n"
                                "\"Hello,\" Alice said.\n"
                                "\"No,\" Bob said, \"stay with me.\"\n"
                                "\"Listen,\" Alice said.\n"
                                "Alice whispered as the door closed.\n\n"
                                "Chapter 2\n"
                                "\"Meet me at dawn,\" Alice said.\n"
                                "\"I will,\" Bob said now.\n"
                                "Together they packed the last things in silence.\n"
                            ).encode("utf-8")
                        ),
                    "text/plain",
                )
            },
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"max_segment_chars": 90, "allow_unfinalized_character_map": True},
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200
        export_payload = export_resp.json()

        academic_reports = export_payload["manifest"].get("academic_reports")
        assert isinstance(academic_reports, dict)

        dominance_report = academic_reports.get("chapter_level_character_dominance")
        assert isinstance(dominance_report, list)
        assert dominance_report, "Expected at least one chapter-level character dominance entry"

        by_chapter: dict[int, dict[str, dict[str, Any]]] = {}
        for segment in export_payload["segments"]:
            chapter_id = segment.get("chapter_id")
            if not isinstance(chapter_id, int):
                continue
            speaker = segment.get("speaker")
            if not isinstance(speaker, str):
                continue
            normalized_speaker = speaker.strip()
            if not normalized_speaker or normalized_speaker.lower() == "unknown":
                continue
            dominance_data = segment.get("dominance_contribution")
            if not isinstance(dominance_data, dict):
                dominance_data = segment.get("tag_bundle", {}).get("dominance", {})
            if not isinstance(dominance_data, dict):
                continue
            dominance_value = dominance_data.get("value")
            if not isinstance(dominance_value, (int, float)):
                continue
            key = normalized_speaker.lower()
            by_chapter.setdefault(chapter_id, {})
            speaker_bucket = by_chapter[chapter_id].setdefault(
                key,
                {
                    "speaker": normalized_speaker,
                    "speaker_id": segment.get("speaker_id"),
                    "segment_count": 0,
                    "total_dominance": 0.0,
                },
            )
            speaker_bucket["segment_count"] = int(speaker_bucket["segment_count"]) + 1
            speaker_bucket["total_dominance"] = float(speaker_bucket["total_dominance"]) + float(dominance_value)

        assert dominance_report
        for chapter_report in dominance_report:
            assert isinstance(chapter_report, dict)
            assert set(chapter_report.keys()) >= {
                "chapter_id",
                "chapter_segment_count",
                "dominance_total",
                "character_dominance_distribution",
                "key_characters",
            }

            chapter_id = chapter_report["chapter_id"]
            assert isinstance(chapter_id, int)
            assert chapter_report["chapter_segment_count"] >= 0
            assert isinstance(chapter_report["character_dominance_distribution"], list)
            assert isinstance(chapter_report["key_characters"], list)
            assert len(chapter_report["key_characters"]) <= 3

            if chapter_id not in by_chapter:
                expected_distribution = []
            else:
                expected_distribution = []
                total_dominance = sum(
                    char_bucket["total_dominance"] for char_bucket in by_chapter[chapter_id].values()
                )
                for char_bucket in by_chapter[chapter_id].values():
                    total = float(char_bucket["total_dominance"])
                    seg_count = int(char_bucket["segment_count"])
                    expected_distribution.append(
                        {
                            "speaker": char_bucket["speaker"],
                            "speaker_id": char_bucket["speaker_id"]
                            if isinstance(char_bucket["speaker_id"], int)
                            else None,
                            "segment_count": seg_count,
                            "total_dominance": round(total, 4),
                            "average_dominance": round(total / seg_count, 4),
                            "dominance_share": round(total / total_dominance, 4) if total_dominance > 0 else 0.0,
                        }
                    )
                expected_distribution.sort(
                    key=lambda item: (
                        -item["total_dominance"],
                        -item["segment_count"],
                        str(item["speaker"]).lower(),
                    )
                )

            assert chapter_report["dominance_total"] == round(
                sum(char_bucket["total_dominance"] for char_bucket in by_chapter.get(chapter_id, {}).values()),
                4,
            )
            assert chapter_report["character_dominance_distribution"] == expected_distribution
            assert chapter_report["key_characters"] == expected_distribution[:3]


def test_export_json_includes_character_cooccurrence_graph() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Manifest ACAD-010 Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        characters_payload = {
            "characters": [
                {
                    "name": "Alice",
                    "verbalized_form": "Alice",
                    "gender": "female",
                    "aliases": ["A"],
                    "source": "manual",
                    "confidence": 1.0,
                },
                {
                    "name": "Bob",
                    "verbalized_form": "Bob",
                    "gender": "male",
                    "aliases": ["B"],
                    "source": "manual",
                    "confidence": 1.0,
                },
                {
                    "name": "Charlie",
                    "verbalized_form": "Charlie",
                    "gender": "male",
                    "aliases": ["C"],
                    "source": "manual",
                    "confidence": 1.0,
                },
            ]
        }
        assert client.put(f"/api/projects/{project_id}/characters", json=characters_payload).status_code == 200

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": (
                    "sample.txt",
                    io.BytesIO(
                        (
                            "Chapter 1\n"
                            "\"Hello, I have been waiting at the gate for you,\" Alice said.\n"
                            "\"No, Bob is ready now,\" Bob said.\n"
                            "\"Then listen carefully, Charlie, we move at dusk,\" Charlie said.\n"
                            "\"And now we leave,\" Alice said.\n\n"
                            "Chapter 2\n"
                            "\"Hold steady, everyone,\" Bob said. \"I am with you,\" Charlie said.\n"
                        ).encode("utf-8")
                    ),
                    "text/plain",
                )
            },
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"max_segment_chars": 80, "allow_unfinalized_character_map": True},
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200
        export_payload = export_resp.json()

        academic_reports = export_payload["manifest"].get("academic_reports")
        assert isinstance(academic_reports, dict)

        graph_report = academic_reports.get("character_cooccurrence_graph")
        assert isinstance(graph_report, dict)
        nodes = graph_report.get("nodes")
        edges = graph_report.get("edges")
        metadata = graph_report.get("metadata")
        assert isinstance(nodes, list)
        assert isinstance(edges, list)
        assert isinstance(metadata, dict)

        node_by_key = {
            node.get("character_key"): node
            for node in nodes
            if isinstance(node.get("character_key"), str)
        }
        assert set(node_by_key) == {"alice", "bob", "charlie"}

        for key in {"alice", "bob", "charlie"}:
            node = node_by_key[key]
            assert node["character_label"] == key.capitalize() if len(key) > 0 else key
            assert isinstance(node["segment_count"], int)
            assert node["segment_count"] >= 1
            assert node["chapter_count"] >= 1
            assert isinstance(node["chapter_ids"], list)
            assert len(node["chapter_ids"]) >= 1
            assert node["adjacency_weight"] >= 0

        edge_by_pair = {
            (edge.get("source"), edge.get("target")): edge
            for edge in edges
            if isinstance(edge.get("source"), str) and isinstance(edge.get("target"), str)
        }
        assert edge_by_pair.get(("alice", "bob"), {}).get("co_occurrence_count") == 1
        assert edge_by_pair.get(("alice", "charlie"), {}).get("co_occurrence_count") == 1
        assert edge_by_pair.get(("bob", "charlie"), {}).get("co_occurrence_count") == 1

        for edge in edges:
            assert edge["source"] < edge["target"]
            assert edge["co_occurrence_count"] >= 1
            assert edge["weight"] == edge["co_occurrence_count"]
            assert isinstance(edge["chapter_ids"], list)
            assert edge["chapter_count"] == len(edge["chapter_ids"])

        assert metadata["node_count"] == len(nodes)
        assert metadata["edge_count"] == len(edges)
        assert metadata["undirected"] is True
        assert metadata["scope"] == "adjacent_speaker_transitions_within_chapter"


def test_export_json_includes_character_cooccurrence_centrality_table() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Manifest ACAD-011 Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        characters_payload = {
            "characters": [
                {
                    "name": "Alice",
                    "verbalized_form": "Alice",
                    "gender": "female",
                    "aliases": ["A"],
                    "source": "manual",
                    "confidence": 1.0,
                },
                {
                    "name": "Bob",
                    "verbalized_form": "Bob",
                    "gender": "male",
                    "aliases": ["B"],
                    "source": "manual",
                    "confidence": 1.0,
                },
                {
                    "name": "Charlie",
                    "verbalized_form": "Charlie",
                    "gender": "male",
                    "aliases": ["C"],
                    "source": "manual",
                    "confidence": 1.0,
                },
            ]
        }
        assert client.put(f"/api/projects/{project_id}/characters", json=characters_payload).status_code == 200

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": (
                    "sample.txt",
                    io.BytesIO(
                        (
                            "Chapter 1\n"
                            "\"Hello, I have been waiting at the gate for you,\" Alice said.\n"
                            "\"No, Bob is ready now,\" Bob said.\n"
                            "\"Then listen carefully, Charlie, we move at dusk,\" Charlie said.\n"
                            "\"And now we leave,\" Alice said.\n"
                        ).encode("utf-8")
                    ),
                    "text/plain",
                )
            },
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"max_segment_chars": 80, "allow_unfinalized_character_map": True},
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200
        export_payload = export_resp.json()

        academic_reports = export_payload["manifest"].get("academic_reports")
        assert isinstance(academic_reports, dict)

        centrality = academic_reports.get("character_cooccurrence_centrality_table")
        assert isinstance(centrality, dict)
        table = centrality.get("metrics_table")
        metadata = centrality.get("metadata")
        assert isinstance(table, list)
        assert isinstance(metadata, dict)

        assert len(table) == 3
        assert metadata["node_count"] == 3
        assert metadata["edge_count"] == 3
        assert metadata["centrality_metrics"] == [
            "degree",
            "degree_centrality",
            "weighted_degree",
            "weighted_degree_centrality",
            "closeness_centrality",
            "betweenness_centrality",
        ]
        assert metadata["generated_by"] == "export_academic_centrality"
        assert metadata["distance_transform"] == "inverse_weight"

        rows_by_character = {
            row.get("character_key"): row
            for row in table
            if isinstance(row.get("character_key"), str)
        }
        assert set(rows_by_character) == {"alice", "bob", "charlie"}

        alice_row = rows_by_character["alice"]
        bob_row = rows_by_character["bob"]
        charlie_row = rows_by_character["charlie"]

        assert alice_row["character_label"] == "Alice"
        assert bob_row["character_label"] == "Bob"
        assert charlie_row["character_label"] == "Charlie"

        assert alice_row["degree"] == 2
        assert bob_row["degree"] == 2
        assert charlie_row["degree"] == 2

        assert alice_row["weighted_degree"] == 2.0
        assert bob_row["weighted_degree"] == 2.0
        assert charlie_row["weighted_degree"] == 2.0

        assert alice_row["degree_centrality"] == 1.0
        assert bob_row["degree_centrality"] == 1.0
        assert charlie_row["degree_centrality"] == 1.0

        assert alice_row["weighted_degree_centrality"] == 1.0
        assert bob_row["weighted_degree_centrality"] == 1.0
        assert charlie_row["weighted_degree_centrality"] == 1.0

        assert alice_row["closeness_centrality"] == 1.0
        assert bob_row["closeness_centrality"] == 1.0
        assert charlie_row["closeness_centrality"] == 1.0

        assert bob_row["betweenness_centrality"] == 0.0
        assert alice_row["betweenness_centrality"] == 0.0
        assert charlie_row["betweenness_centrality"] == 0.0

        ranked = [row["character_key"] for row in table]
        assert ranked == ["alice", "bob", "charlie"]
        assert table[0]["rank"] == 1
        assert table[1]["rank"] == 2
        assert table[2]["rank"] == 3


def test_export_json_includes_academic_json_schema_manifest() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Manifest ACAD-012 Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": (
                    "sample.txt",
                    io.BytesIO(
                        (
                            "Chapter 1\n"
                            "Ada looked down the canyon and thought about the storm.\n\n"
                            "Chapter 2\n"
                            "The signal tower blinked once, and then again, then again."
                        ).encode("utf-8")
                    ),
                    "text/plain",
                )
            },
        )
        assert ingest_resp.status_code == 200
        assert ingest_resp.json()["chapter_count"] == 2

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"max_segment_chars": 120, "allow_unfinalized_character_map": True},
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200
        manifest = export_resp.json()["manifest"]

        academic_manifest = manifest.get("academic_export_manifest")
        assert isinstance(academic_manifest, dict)
        assert academic_manifest["schema_version"] == "1.0.0"
        assert academic_manifest["output_schema"] == "academic_json"
        assert academic_manifest["export_format"] == "json"
        assert academic_manifest["project_id"] == project_id
        assert academic_manifest["run_id"] == run_id
        assert academic_manifest["run_status"] == "completed"

        outputs = academic_manifest.get("outputs")
        assert isinstance(outputs, list)
        assert len(outputs) == 6

        outputs_by_id = {entry.get("output_id"): entry for entry in outputs if isinstance(entry, dict)}
        expected_output_names = {
            "AO-001": "chapter_emotion_metrics_series",
            "AO-002": "chapter_tension_curve_summary",
            "AO-003": "character_dominance_series",
            "AO-004": "character_cooccurrence_graph",
            "AO-005": "comparative_run_metrics_snapshot",
            "AO-006": "academic_export_manifest",
        }

        assert set(outputs_by_id.keys()) >= set(expected_output_names.keys())
        for output_id, expected_name in expected_output_names.items():
            output = outputs_by_id[output_id]
            assert output["output_name"] == expected_name
            assert "supported_formats" in output
            assert "available_formats" in output
            assert "data_keys" in output
            assert "evidence" in output

        available_outputs = {
            output["output_id"]
            for output in outputs
            if isinstance(output, dict) and output.get("status") == "available"
        }
        assert {"AO-001", "AO-002", "AO-003", "AO-004", "AO-005", "AO-006"} <= available_outputs

        ao_005 = outputs_by_id["AO-005"]
        assert ao_005["status"] == "available"
        assert ao_005["available_formats"] == ["json", "csv"]

        ao_006 = outputs_by_id["AO-006"]
        assert ao_006["available_formats"] == ["json"]
        assert ao_006["data_keys"] == ["academic_export_manifest"]
        evidence = ao_006["evidence"]
        assert evidence["generated_by"] == "academic_export_schema_1_0_0"


def test_export_json_manifest_respects_run_level_export_format_gates() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Manifest Format Gate Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": (
                    "sample.txt",
                    io.BytesIO(b"Chapter 1\nThe lantern burned low and the rain beat softly outside."),
                    "text/plain",
                )
            },
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={
                "max_segment_chars": 80,
                "allow_unfinalized_character_map": True,
                "export_formats": ["json", "csv"],
            },
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200
        manifest = export_resp.json()["manifest"]
        academic_manifest = manifest["academic_export_manifest"]
        outputs = academic_manifest.get("outputs")
        assert isinstance(outputs, list)

        outputs_by_id = {entry.get("output_id"): entry for entry in outputs if isinstance(entry, dict)}
        assert outputs_by_id["AO-001"]["available_formats"] == ["json", "csv"]
        assert outputs_by_id["AO-002"]["available_formats"] == ["json", "csv"]
        assert outputs_by_id["AO-003"]["available_formats"] == ["json", "csv"]
        assert outputs_by_id["AO-004"]["available_formats"] == ["json", "csv"]
        assert outputs_by_id["AO-005"]["available_formats"] == ["json", "csv"]
        assert outputs_by_id["AO-006"]["available_formats"] == ["json"]


def test_export_json_manifest_hides_json_only_outputs_when_run_disables_json() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Manifest CSV-Only Gate Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": (
                    "sample.txt",
                    io.BytesIO(b"Chapter 1\nThe lantern burned low and the rain beat softly outside."),
                    "text/plain",
                )
            },
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={
                "max_segment_chars": 80,
                "allow_unfinalized_character_map": True,
                "export_formats": ["csv"],
            },
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200
        manifest = export_resp.json()["manifest"]
        academic_manifest = manifest["academic_export_manifest"]
        outputs = academic_manifest.get("outputs")
        assert isinstance(outputs, list)

        outputs_by_id = {entry.get("output_id"): entry for entry in outputs if isinstance(entry, dict)}
        assert outputs_by_id["AO-001"]["available_formats"] == ["csv"]
        assert outputs_by_id["AO-002"]["available_formats"] == ["csv"]
        assert outputs_by_id["AO-003"]["available_formats"] == ["csv"]
        assert outputs_by_id["AO-004"]["available_formats"] == ["csv"]
        assert outputs_by_id["AO-005"]["available_formats"] == ["csv"]
        assert outputs_by_id["AO-006"]["available_formats"] == []
        assert outputs_by_id["AO-006"]["status"] == "not_implemented"


def test_export_json_rejects_graph_json_when_output_format_not_allowed() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Manifest Graph JSON Gate Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", io.BytesIO(b"Chapter 1\nA cold wind pushed through the hall."), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={
                "max_segment_chars": 80,
                "allow_unfinalized_character_map": True,
                "export_formats": ["json", "csv"],
            },
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        blocked_graph_resp = client.get(
            f"/api/projects/{project_id}/exports/{run_id}.json",
            params={"output_schema": "academic", "output_format": "graph_json"},
        )
        assert blocked_graph_resp.status_code == 400
        assert "not allowed for this run" in blocked_graph_resp.json()["detail"]


def test_export_json_rejects_academic_json_when_output_format_not_allowed() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Manifest Academic JSON Gate Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", io.BytesIO(b"Chapter 1\nA cold wind pushed through the hall."), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={
                "max_segment_chars": 80,
                "allow_unfinalized_character_map": True,
                "export_formats": ["csv"],
            },
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        blocked_json_resp = client.get(
            f"/api/projects/{project_id}/exports/{run_id}.json",
            params={"output_schema": "academic", "output_format": "json"},
        )
        assert blocked_json_resp.status_code == 400
        assert "not allowed for this run" in blocked_json_resp.json()["detail"]


def test_export_json_includes_comparative_run_metrics_snapshot() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Manifest ACAD-015 Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": (
                    "sample.txt",
                    io.BytesIO(
                        (
                            "Chapter 1\n"
                            "The rain turned the hall into silver glass.\n"
                            "Chapter 2\n"
                            "Footsteps kept arriving, but no one entered."
                        ).encode("utf-8")
                    ),
                    "text/plain",
                )
            },
        )
        assert ingest_resp.status_code == 200
        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"max_segment_chars": 120, "allow_unfinalized_character_map": True},
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_payload = client.get(f"/api/projects/{project_id}/exports/{run_id}.json").json()
        manifest = export_payload["manifest"]
        academic_reports = manifest.get("academic_reports")
        assert isinstance(academic_reports, dict)

        comparative_snapshot = academic_reports.get("comparative_run_metrics_snapshot")
        assert isinstance(comparative_snapshot, dict)
        assert comparative_snapshot["snapshot_type"] == "comparative_run_metrics_snapshot"
        assert comparative_snapshot["project_reference"]["project_id"] == project_id
        assert comparative_snapshot["run_reference"]["run_id"] == run_id
        assert comparative_snapshot["run_reference"]["segment_count"] > 0
        assert comparative_snapshot["reproducibility"]["input_signature"]["segment_signature"]
        assert isinstance(comparative_snapshot["run_config_snapshot"], dict)


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


def test_export_csv_supports_academic_output_schema() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Manifest Academic CSV Project"})
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

        export_payload = client.get(f"/api/projects/{project_id}/exports/{run_id}.json").json()
        manifest = export_payload["manifest"]
        academic_manifest = manifest["academic_export_manifest"]
        assert academic_manifest["output_schema"] == "academic_json"

        academic_csv_resp = client.get(
            f"/api/projects/{project_id}/exports/{run_id}.csv",
            params={"output_schema": "academic"},
        )
        assert academic_csv_resp.status_code == 200
        assert academic_csv_resp.headers["content-type"] == "text/csv; charset=utf-8"
        assert academic_csv_resp.headers["content-disposition"] == f"attachment; filename=\"project-{project_id}-run-{run_id}-academic.csv\""

        rows = list(csv.DictReader(io.StringIO(academic_csv_resp.text)))
        assert len(rows) > 0
        expected_fields = {
            "record_type",
            "output_order",
            "output_id",
            "output_name",
            "output_status",
            "output_schema",
            "data_key",
            "record_count",
            "record_payload",
            "status_reason",
            "generated_by",
            "generated_at",
            "project_id",
            "run_id",
            "run_status",
        }
        assert set(rows[0].keys()) >= expected_fields

        manifest_row = next((row for row in rows if row["record_type"] == "manifest"), None)
        assert manifest_row is not None
        assert manifest_row["output_id"] == "AO-MANIFEST"
        assert manifest_row["output_name"] == "academic_export_manifest"
        assert manifest_row["output_status"] == "available"
        assert manifest_row["data_key"] == "academic_export_manifest"
        assert manifest_row["project_id"] == str(project_id)
        assert manifest_row["run_id"] == str(run_id)

        output_rows = [row for row in rows if row["record_type"] == "output"]
        assert len(output_rows) == 6

        data_records = [row for row in rows if row["record_type"] == "data_record"]
        assert len(data_records) > 0

        output_ids = {row["output_id"] for row in output_rows}
        assert output_ids == {"AO-001", "AO-002", "AO-003", "AO-004", "AO-005", "AO-006"}

        by_output = {row["output_id"]: [] for row in output_rows}
        for record in data_records:
            by_output.setdefault(record["output_id"], []).append(record)

        assert len(by_output["AO-005"]) > 0
        for output_id in ("AO-001", "AO-002", "AO-003", "AO-004", "AO-006"):
            assert len(by_output[output_id]) > 0

        ao_005_rows = [row for row in output_rows if row["output_id"] == "AO-005"]
        assert ao_005_rows
        assert ao_005_rows[0]["output_status"] == "available"

        ao_006_row = next(row for row in output_rows if row["output_id"] == "AO-006")
        assert ao_006_row["output_status"] == "available"
        assert ao_006_row["data_key"] == ""

        csv_output_ids = {row["output_id"] for row in output_rows if row["output_id"] != "AO-MANIFEST"}
        assert csv_output_ids == {"AO-001", "AO-002", "AO-003", "AO-004", "AO-005", "AO-006"}


def test_export_csv_manifest_row_tracks_run_level_manifest_visibility() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Manifest Academic CSV Visibility Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", io.BytesIO(b"Chapter 1\nThe lantern burned low and the rain beat softly outside."), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={
                "max_segment_chars": 80,
                "allow_unfinalized_character_map": True,
                "export_formats": ["csv"],
            },
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        academic_csv_resp = client.get(
            f"/api/projects/{project_id}/exports/{run_id}.csv",
            params={"output_schema": "academic"},
        )
        assert academic_csv_resp.status_code == 200

        rows = list(csv.DictReader(io.StringIO(academic_csv_resp.text)))
        manifest_row = next((row for row in rows if row["record_type"] == "manifest"), None)
        assert manifest_row is not None
        assert manifest_row["output_status"] == "not_implemented"
        assert manifest_row["available_formats"] == "[]"

        ao_006_row = next((row for row in rows if row["record_type"] == "output" and row["output_id"] == "AO-006"), None)
        assert ao_006_row is not None
        assert ao_006_row["output_status"] == "not_implemented"
        assert ao_006_row["available_formats"] == "[]"

        ao_006_records = [row for row in rows if row["record_type"] == "data_record" and row["output_id"] == "AO-006"]
        assert ao_006_records == []


def test_export_csv_rejects_academic_format_when_csv_disabled() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Manifest CSV Gate Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", io.BytesIO(b"Chapter 1\nThe lantern burned low and the rain beat softly outside."), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={
                "max_segment_chars": 80,
                "allow_unfinalized_character_map": True,
                "export_formats": ["json"],
            },
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        blocked_csv_resp = client.get(
            f"/api/projects/{project_id}/exports/{run_id}.csv",
            params={"output_schema": "academic"},
        )
        assert blocked_csv_resp.status_code == 400
        assert blocked_csv_resp.json()["detail"].startswith("CSV export is not allowed for this run.")


def test_export_graph_json_format_for_academic_output() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Manifest Academic Graph JSON Project"})
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

        graph_json_resp = client.get(
            f"/api/projects/{project_id}/exports/{run_id}.json",
            params={"output_schema": "academic", "output_format": "graph_json"},
        )
        assert graph_json_resp.status_code == 200
        assert graph_json_resp.headers["content-type"] == "application/json"

        payload = graph_json_resp.json()
        assert payload["schema_version"] == "1.0.0"
        assert payload["output_schema"] == "graph_json"
        assert payload["output_format"] == "graph_json"
        assert payload["output_id"] == "AO-004"
        assert payload["output_name"] == "character_cooccurrence_graph"
        assert payload["project_id"] == project_id
        assert payload["run_id"] == run_id
        assert payload["run_status"] == "completed"

        graph = payload["graph"]
        assert set(graph.keys()) >= {"nodes", "edges", "metadata"}
        assert isinstance(graph["nodes"], list)
        assert isinstance(graph["edges"], list)

        centrality = payload["character_cooccurrence_centrality"]
        assert set(centrality.keys()) >= {"metrics_table", "metadata"}
        assert isinstance(centrality["metrics_table"], list)

        assert payload["manifest_snapshot"]["output_schema"] == "academic_json"
        assert payload["manifest_snapshot"]["generated_by"] == "build_run_export"


def test_export_graph_json_rejects_invalid_academic_output_id() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Manifest Academic Graph JSON Invalid Output Project"})
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

        invalid_output_resp = client.get(
            f"/api/projects/{project_id}/exports/{run_id}.json",
            params={
                "output_schema": "academic",
                "output_format": "graph_json",
                "output_id": "AO-001",
            },
        )
        assert invalid_output_resp.status_code == 400
def test_export_json_supports_resumable_cursor() -> None:
    source_text = (
        "Chapter 1\n"
        "In the beginning there was a lantern and a hallway and a door and another door and a hallway "
        "that stretched beyond the edge of sight. The moon rose high and the rain whispered across the "
        "roof while footsteps echoed in distant corridors and voices floated from somewhere else. "
        "No one answered when called, and yet each room seemed to keep listening, collecting each word "
        "like a promise. The narrator counted every breath, every shadow. "
        "The mystery deepened with every step, and the wind carried paper across the tile floor. "
        "Then came the storm, and all the candles in the corridor flared into life, one after another, "
        "as if someone had already made their decision. "
    )
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Manifest Resume Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", io.BytesIO(source_text.encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"max_segment_chars": 80, "allow_unfinalized_character_map": True},
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        full_export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert full_export_resp.status_code == 200
        full_payload = full_export_resp.json()

        assert full_payload["cursor"]["returned_segment_count"] == len(full_payload["segments"])
        assert full_payload["cursor"]["has_more_segments"] is False
        assert full_payload["cursor"]["total_segment_count"] == len(full_payload["segments"])
        assert full_payload["cursor"]["next_resume_from"] == {
            "chapter_index": full_payload["segments"][-1]["chapter_id"],
            "segment_index": full_payload["segments"][-1]["segment_index"],
        }

        cursor_payload = client.get(
            f"/api/projects/{project_id}/exports/{run_id}.json",
            params={
                "from_chapter_index": full_payload["segments"][0]["chapter_id"],
                "from_segment_index": full_payload["segments"][0]["segment_index"],
            },
        )
        assert cursor_payload.status_code == 200
        resumed = cursor_payload.json()
        assert resumed["cursor"]["from_chapter_index"] == full_payload["segments"][0]["chapter_id"]
        assert resumed["cursor"]["from_segment_index"] == full_payload["segments"][0]["segment_index"]
        assert resumed["cursor"]["returned_segment_count"] == max(len(full_payload["segments"]) - 1, 0)
        assert len(resumed["segments"]) == max(len(full_payload["segments"]) - 1, 0)


def test_export_json_respects_run_level_export_chunk_size() -> None:
    source_text = (
        "Chapter 1\n"
        "In the beginning there was a lantern and a hallway and a door and another door and a hallway "
        "that stretched beyond the edge of sight. The moon rose high and the rain whispered across the "
        "roof while footsteps echoed in distant corridors and voices floated from somewhere else. "
        "No one answered when called, and yet each room seemed to keep listening, collecting each word "
        "like a promise. The narrator counted every breath, every shadow. "
        "The mystery deepened with every step, and the wind carried paper across the tile floor. "
        "Then came the storm, and all the candles in the corridor flared into life, one after another, "
        "as if someone had already made their decision. "
    )
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Manifest Export Chunk Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", io.BytesIO(source_text.encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={
                "max_segment_chars": 80,
                "allow_unfinalized_character_map": True,
                "export_chunk_size": 1,
            },
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        first_page_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert first_page_resp.status_code == 200
        first_page = first_page_resp.json()

        assert first_page["cursor"]["export_chunk_size"] == 1
        assert first_page["cursor"]["returned_segment_count"] == 1
        assert first_page["cursor"]["has_more_segments"] is True
        assert first_page["cursor"]["total_segment_count"] > 1
        assert len(first_page["segments"]) == 1

        resume_from = first_page["cursor"]["next_resume_from"]
        second_page_resp = client.get(
            f"/api/projects/{project_id}/exports/{run_id}.json",
            params={
                "from_chapter_index": resume_from["chapter_index"],
                "from_segment_index": resume_from["segment_index"],
            },
        )
        assert second_page_resp.status_code == 200
        second_page = second_page_resp.json()

        assert second_page["cursor"]["export_chunk_size"] == 1
        assert second_page["cursor"]["returned_segment_count"] == 1
        assert len(second_page["segments"]) == 1
        assert second_page["segments"][0]["segment_id"] != first_page["segments"][0]["segment_id"]


def test_export_segment_ids_stable_across_equivalent_reruns() -> None:
    source_text = (
        "Chapter 1\nA lantern glowed in the study as rain traced silver lines across the windows. "
        "The detective waited for the truth to arrive, or the truth to confess. "
        "The clock in the hall counted each heartbeat with perfect indifference.\n\n"
        "Chapter 2\nHe moved through the old wing with careful steps, listening to the groan of timber "
        "and the thin scrape of paper in a locked drawer. "
        "Every choice now had a shadow, and every shadow had a name."
    ).encode("utf-8")

    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Manifest Stable Segment IDs"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", io.BytesIO(source_text), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        first_run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"max_segment_chars": 120, "allow_unfinalized_character_map": True},
        )
        assert first_run_resp.status_code == 200
        first_run_id = first_run_resp.json()["run_id"]

        second_run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"max_segment_chars": 120, "mode": "audiobook", "allow_unfinalized_character_map": True},
        )
        assert second_run_resp.status_code == 200
        second_run_id = second_run_resp.json()["run_id"]

        first_export = client.get(f"/api/projects/{project_id}/exports/{first_run_id}.json")
        second_export = client.get(f"/api/projects/{project_id}/exports/{second_run_id}.json")
        assert first_export.status_code == 200
        assert second_export.status_code == 200

        first_segments = first_export.json()["segments"]
        second_segments = second_export.json()["segments"]
        assert [segment["segment_id"] for segment in first_segments] == [
            segment["segment_id"] for segment in second_segments
        ]


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
