import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_time_series_snapshots.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Run, TimeSeriesSnapshot
from app.modes import MODE_VALUES


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_time_series_snapshots.db")
    if db_file.exists():
        db_file.unlink()


def _ingest_project_text(project_title: str, source_payload: str) -> int:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": project_title})
        assert project_resp.status_code == 201
        project_id = int(project_resp.json()["id"])

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("story.txt", io.BytesIO(source_payload.encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200
        assert ingest_resp.json()["chapter_count"] == 1

        client.post(
            f"/api/projects/{project_id}/characters/import",
            files={
                "file": (
                    "characters.json",
                    io.BytesIO(
                        b'{"Elena":{"verbalized_form":"Elena","gender":"female"},"Milo":{"verbalized_form":"Milo","gender":"male"}}'
                    ),
                    "application/json",
                )
            },
        )

    return project_id


def _run_mode(client: TestClient, project_id: int, mode: str) -> int:
    run_resp = client.post(
        f"/api/projects/{project_id}/runs",
        json={"mode": mode, "allow_unfinalized_character_map": True},
    )
    assert run_resp.status_code == 200
    payload = run_resp.json()
    assert payload["segment_count"] > 0
    return int(payload["run_id"])


def _expected_time_series_keys() -> set[str]:
    return {
        "emotion_valence",
        "emotion_intensity",
        "tension",
        "dominance",
        "emotion_delta",
        "scene_states",
        "volatility_markers",
        "avoid_abrupt_change_hints",
    }


def _segment_lookup_by_id(payload_points: list[dict]) -> dict[str, dict[str, object]]:
    mapping: dict[str, dict[str, object]] = {}
    for point in payload_points:
        segment_id = point.get("segment_id")
        if not isinstance(segment_id, str):
            continue
        mapping[segment_id] = {
            "chapter_id": point.get("chapter_id"),
            "segment_index": point.get("segment_index"),
        }
    return mapping


def _assert_time_series_metric_can_resolve(
    metric_point: dict,
    segment_lookup: dict[str, dict[str, object]],
) -> None:
    segment_id = metric_point.get("segment_id")
    assert isinstance(segment_id, str)
    assert segment_id in segment_lookup
    segment_ref = segment_lookup[segment_id]
    assert metric_point["chapter_id"] == segment_ref["chapter_id"]
    assert metric_point["segment_index"] == segment_ref["segment_index"]

    from_segment_id = metric_point.get("from_segment_id")
    if from_segment_id is None:
        return

    assert isinstance(from_segment_id, str)
    assert from_segment_id in segment_lookup
    from_segment_ref = segment_lookup[from_segment_id]
    assert metric_point["from_chapter_id"] == from_segment_ref["chapter_id"]
    assert metric_point["from_segment_index"] == from_segment_ref["segment_index"]


def test_run_capture_persists_time_series_snapshot_for_all_modes() -> None:
    with TestClient(app) as client:
        project_id = _ingest_project_text(
            project_title="Run Time-Series Snapshot Across Modes",
            source_payload=(
                "Chapter 1\n"
                '"Elena said," Elena whispered. "Milo" answered firmly.\n'
                "The rain stopped and the market opened before dawn.\n"
            ),
        )

        run_records: list[tuple[str, int]] = []
        for mode in MODE_VALUES:
            run_id = _run_mode(client, project_id, mode)
            run_records.append((mode, run_id))

    session = get_session_factory()()
    try:
        snapshots = (
            session.query(TimeSeriesSnapshot)
            .filter(TimeSeriesSnapshot.project_id == project_id)
            .order_by(TimeSeriesSnapshot.version.asc())
            .all()
        )
        assert [snapshot.version for snapshot in snapshots] == [1, 2, 3, 4]

        for mode, run_id in run_records:
            run = session.query(Run).filter(Run.id == run_id).one()
            snapshot = (
                session.query(TimeSeriesSnapshot)
                .filter(TimeSeriesSnapshot.run_id == run.id)
                .one()
            )

            assert snapshot.source == "run_capture"
            assert run.config_json["time_series_snapshot_id"] == snapshot.id
            assert run.config_json["time_series_snapshot_version"] == snapshot.version
            assert snapshot.snapshot_json["project_id"] == project_id
            assert snapshot.snapshot_json["run_id"] == run.id
            assert snapshot.snapshot_json["mode"] == mode
            assert snapshot.snapshot_json["schema_version"] == "1.0.0"

            payload = snapshot.snapshot_json["time_series"]
            assert set(payload.keys()) >= _expected_time_series_keys()
            assert payload["emotion_valence"]
            assert payload["emotion_intensity"]
            assert payload["tension"]
            assert payload["dominance"]
            assert payload["scene_states"]
            assert snapshot.snapshot_json["segment_count"] == len(payload["emotion_valence"])
            assert run.config_json["mode"] == mode

            segment_lookup = _segment_lookup_by_id(payload["emotion_valence"])
            assert segment_lookup

            for metric_point in payload["emotion_delta"]:
                _assert_time_series_metric_can_resolve(metric_point, segment_lookup)
            for metric_point in payload["volatility_markers"]:
                _assert_time_series_metric_can_resolve(metric_point, segment_lookup)
            for metric_point in payload["avoid_abrupt_change_hints"]:
                _assert_time_series_metric_can_resolve(metric_point, segment_lookup)
    finally:
        session.close()
