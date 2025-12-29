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
