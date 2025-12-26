import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_tagging_evaluations.db"

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.main import app
from app.services.tagging import detect_emotion_shift

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
RAPID_EMOTION_FIXTURE_PATH = FIXTURES_DIR / "rapid_emotional_shifts.txt"


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    db_file = Path("test_nipe_tagging_evaluations.db")
    if db_file.exists():
        db_file.unlink()


def _rapid_emotion_text() -> str:
    text = RAPID_EMOTION_FIXTURE_PATH.read_text(encoding="utf-8").strip()
    assert text
    return text


def test_detect_emotion_shift_identifies_rapid_emotional_shifts_from_fixture() -> None:
    text = _rapid_emotion_text()

    shift = detect_emotion_shift(text)

    assert isinstance(shift, dict)
    assert shift["has_shift"] is True
    assert shift["from"] is not None
    assert shift["to"] is not None
    assert shift["evidence"].get("shift_count", 0) >= 2
    assert shift["state"] in {"certain", "uncertain", "unknown"}


def test_pipeline_detects_rapid_emotional_shifts_from_fixture() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Rapid Emotion Shift Fixture"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("rapid-emotional-shifts.txt", io.BytesIO(_rapid_emotion_text().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200
        assert ingest_resp.json()["chapter_count"] == 1

        run_payload = {
            "max_segment_chars": 255,
            "llm_enabled": False,
            "allow_unfinalized_character_map": True,
        }
        run_resp = client.post(f"/api/projects/{project_id}/runs", json=run_payload)
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200
        segments = export_resp.json()["segments"]
        assert segments

        shift_counts = [
            int(segment.get("emotion_shift", {}).get("evidence", {}).get("shift_count", 0))
            for segment in segments
            if isinstance(segment.get("emotion_shift"), dict) and segment.get("emotion_shift", {}).get("has_shift")
        ]
        assert shift_counts
        assert max(shift_counts) >= 1

        emotion_boundaries = [
            boundary
            for segment in segments
            for boundary in (segment.get("sub_segment_boundaries", []) or [])
            if isinstance(boundary, dict) and boundary.get("shift_type") == "emotion_shift"
        ]
        assert emotion_boundaries
