import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_export_ordering.db"

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

    db_file = Path("test_nipe_export_ordering.db")
    if db_file.exists():
        db_file.unlink()


def _create_project(client: TestClient) -> int:
    project_resp = client.post("/api/projects", json={"title": "Ordered Corpus Export"})
    assert project_resp.status_code == 201
    return project_resp.json()["id"]


def _ingest_text(client: TestClient, project_id: int) -> None:
    payload = (
        "Chapter 1\n"
        "First a spark lit the alley, and then the bell echoed through the fog.\n\n"
        "Second breath rose as the crowd gathered near the market.\n\n"
        "Chapter 2\n"
        "Lanterns lined the avenue. The first watch changed. Footsteps clicked behind us.\n\n"
        "Second wind arrived and the story moved onward."
    )
    ingest_resp = client.post(
        f"/api/projects/{project_id}/ingest/txt",
        files={"file": ("ordered.txt", io.BytesIO(payload.encode("utf-8")), "text/plain")},
    )
    assert ingest_resp.status_code == 200
    assert ingest_resp.json()["chapter_count"] == 2


def test_export_segments_are_ordered_across_chapters_then_segments() -> None:
    with TestClient(app) as client:
        project_id = _create_project(client)
        _ingest_text(client, project_id)

        run_resp = client.post(f"/api/projects/{project_id}/runs", json={"max_segment_chars": 80})
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200

        payload = export_resp.json()
        segments = payload["segments"]
        assert payload["status"] == "completed"
        assert segments

        ordered_keys = [
            (int(segment["chapter_id"]), int(segment["segment_index"])) for segment in segments
        ]
        assert ordered_keys == sorted(ordered_keys)

        seen_segment_ids: set[str] = set()
        ordered_by_chapter: dict[int, list[int]] = {}
        for segment in segments:
            segment_id = segment.get("segment_id")
            assert segment_id is not None
            segment_id_str = str(segment_id)
            assert segment_id_str not in seen_segment_ids
            seen_segment_ids.add(segment_id_str)

            chapter_id = int(segment["chapter_id"])
            ordered_by_chapter.setdefault(chapter_id, []).append(int(segment["segment_index"]))

        for segment_indexes in ordered_by_chapter.values():
            assert segment_indexes == list(range(1, len(segment_indexes) + 1))
