import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_tagging_subsegment.db")

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Segment, SubSegmentTag


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    db_path = Path("test_tagging_subsegment.db")
    if db_path.exists():
        db_path.unlink()


def _ingest_text_payload() -> bytes:
    return (
        b"Chapter 1\n"
        b'She thought he would answer. "No," he said. Then the rain came again.'
    )


def test_segment_shift_boundaries_are_stored_in_sub_segment_table() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Subsegment Storage Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", io.BytesIO(_ingest_text_payload()), "text/plain")},
        )
        assert ingest_resp.status_code == 200
        assert ingest_resp.json()["chapter_count"] == 1

        run_payload = {
            "max_segment_chars": 200,
            "llm_enabled": False,
            "allow_unfinalized_character_map": True,
        }
        run_resp = client.post(f"/api/projects/{project_id}/runs", json=run_payload)
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        session = get_session_factory()()
        try:
            segment_rows = (
                session.query(Segment)
                .filter(Segment.run_id == run_id)
                .order_by(Segment.segment_index.asc())
                .all()
            )
            assert segment_rows
            first_segment = segment_rows[0].segment_json
            expected_boundaries = (
                first_segment.get("sub_segment_boundaries") if isinstance(first_segment, dict) else []
            )
            assert isinstance(expected_boundaries, list)

            tag_rows = (
                session.query(SubSegmentTag)
                .filter(SubSegmentTag.run_id == run_id)
                .order_by(SubSegmentTag.sub_segment_index.asc())
                .all()
            )
            assert len(tag_rows) == len(expected_boundaries)

            for tag_row in tag_rows:
                assert tag_row.sub_segment_id
                assert tag_row.sub_segment_index >= 1
                assert tag_row.run_id == run_id
                assert tag_row.shift_type
                assert tag_row.boundary_start_char >= 0
                assert tag_row.boundary_end_char >= tag_row.boundary_start_char
                assert isinstance(tag_row.tags, dict)
                assert tag_row.tags["shift_type"] == tag_row.shift_type
        finally:
            session.close()
