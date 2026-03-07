import io
import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_e2e_golden_dataset_snapshots.db"

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.main import app

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
GOLDEN_SNAPSHOT_FIXTURE_PATH = FIXTURES_DIR / "e2e_golden_export_snapshots.json"


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_e2e_golden_dataset_snapshots.db")
    if db_file.exists():
        db_file.unlink()


def _load_fixture_text(filename: str) -> str:
    text = (FIXTURES_DIR / filename).read_text(encoding="utf-8").strip()
    assert text
    return text


def _load_golden_snapshots() -> dict[str, object]:
    with GOLDEN_SNAPSHOT_FIXTURE_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    assert isinstance(payload, dict)
    return payload


def _create_project_run_and_export(client: TestClient, filename: str) -> list[dict[str, object]]:
    create_resp = client.post("/api/projects", json={"title": f"Golden dataset {filename}"})
    assert create_resp.status_code == 201
    project_id = int(create_resp.json()["id"])

    ingest_resp = client.post(
        f"/api/projects/{project_id}/ingest/txt",
        files={
            "file": (
                filename,
                io.BytesIO(_load_fixture_text(filename).encode("utf-8")),
                "text/plain",
            )
        },
    )
    assert ingest_resp.status_code == 200
    assert ingest_resp.json()["chapter_count"] == 1

    run_resp = client.post(
        f"/api/projects/{project_id}/runs",
        json={
            "max_segment_chars": 255,
            "llm_enabled": False,
            "allow_unfinalized_character_map": True,
        },
    )
    assert run_resp.status_code == 200
    run_id = int(run_resp.json()["run_id"])

    export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
    assert export_resp.status_code == 200
    payload = export_resp.json()
    assert isinstance(payload.get("segments"), list)
    return payload["segments"]


def _build_segment_snapshot(segments: list[dict[str, object]]) -> list[dict[str, object]]:
    snapshot: list[dict[str, object]] = []
    for segment in segments:
        boundaries = [
            item
            for item in (segment.get("sub_segment_boundaries") or [])
            if isinstance(item, dict) and item.get("shift_type") == "emotion_shift"
        ]
        emotion_shift = segment.get("emotion_shift") if isinstance(segment.get("emotion_shift"), dict) else {}
        shift_evidence = emotion_shift.get("evidence") if isinstance(emotion_shift.get("evidence"), dict) else {}
        snapshot.append(
            {
                "segment_index": int(segment["segment_index"]),
                "type": str(segment["type"]),
                "speaker": str(segment["speaker"]) if segment.get("speaker") is not None else None,
                "type_confidence": round(float(segment.get("type_confidence") or 0.0), 2),
                "emotion_primary_label": str(segment.get("emotion_primary_label") or ""),
                "emotion_shift_has_shift": bool(emotion_shift.get("has_shift")),
                "emotion_shift_count": int(shift_evidence.get("shift_count") or 0),
                "emotion_shift_boundaries": len(boundaries),
                "ambiguity_flags": sorted(str(flag) for flag in (segment.get("ambiguity_flags") or [])),
            }
        )
    return sorted(snapshot, key=lambda item: int(item["segment_index"]))


def test_unit_golden_dataset_snapshot_fixture_index() -> None:
    snapshots = _load_golden_snapshots()
    assert sorted(snapshots.keys()) == ["mixed_narration_dialogue_segment.txt", "rapid_emotional_shifts.txt"]


def test_e2e_fixture_datasets_match_export_golden_snapshots() -> None:
    expected = _load_golden_snapshots()
    actual: dict[str, object] = {}

    with TestClient(app) as client:
        for filename in sorted(expected.keys()):
            segments = _create_project_run_and_export(client, filename)
            actual[filename] = {
                "segment_count": len(segments),
                "segments": _build_segment_snapshot(segments),
            }

    assert actual == expected
