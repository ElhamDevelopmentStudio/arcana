import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_tagging_outputs_persistence.db")

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Segment, SubSegmentTag


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_path = Path("test_tagging_outputs_persistence.db")
    if db_path.exists():
        db_path.unlink()


def _create_run_with_tags(*, project_title: str, source_payload: str) -> tuple[int, int]:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": project_title})
        assert project_resp.status_code == 201
        project_id = int(project_resp.json()["id"])

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("story.txt", io.BytesIO(source_payload.encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={
                "max_segment_chars": 120,
                "llm_enabled": False,
                "allow_unfinalized_character_map": True,
            },
        )
        assert run_resp.status_code == 200

        return project_id, int(run_resp.json()["run_id"])


def test_tagging_outputs_are_persisted_with_reference_fields() -> None:
    project_id, run_id = _create_run_with_tags(
        project_title="Tagging Outputs Persist Project",
        source_payload=(
            "Chapter 1\n"
            'Ava frowned. "Are we still safe," she asked.\n'
            "Nora nodded once and crossed the room."
        ),
    )

    session = get_session_factory()()
    try:
        segment_rows = (
            session.query(Segment)
            .filter(Segment.run_id == run_id)
            .order_by(Segment.segment_index.asc())
            .all()
        )
        assert segment_rows

        total_subsegment_boundaries = 0
        for segment_row in segment_rows:
            segment_payload = segment_row.segment_json
            assert isinstance(segment_payload, dict)
            assert segment_row.chapter_id > 0
            assert segment_payload.get("chapter_id") == segment_row.chapter_id
            assert isinstance(segment_payload.get("chapter_internal_id"), str)
            assert "type" in segment_payload
            assert "speaker" in segment_payload
            assert "speaker_state" in segment_payload
            assert "tag_states" in segment_payload and isinstance(segment_payload["tag_states"], dict)
            assert "summary_tag" in segment_payload
            assert "confidence" in segment_payload and isinstance(segment_payload["confidence"], dict)
            assert "sub_segment_boundaries" in segment_payload and isinstance(
                segment_payload["sub_segment_boundaries"], list
            )
            assert "original_span_pointer" in segment_payload and isinstance(
                segment_payload["original_span_pointer"], dict
            )
            total_subsegment_boundaries += len(segment_payload["sub_segment_boundaries"])

            assert segment_row.run_id == run_id

            segment_pointer = segment_payload["original_span_pointer"]
            assert segment_pointer.get("original_start_char", -1) >= -1
            assert segment_pointer.get("original_end_char", -1) >= segment_pointer.get("original_start_char", -1)
            assert segment_pointer.get("normalized_start_char", 0) >= 0
            assert segment_pointer.get("normalized_end_char", 0) >= segment_pointer["normalized_start_char"]

        tag_rows = (
            session.query(SubSegmentTag)
            .filter(SubSegmentTag.run_id == run_id)
            .order_by(SubSegmentTag.sub_segment_index.asc())
            .all()
        )
        assert len(tag_rows) == total_subsegment_boundaries
        for tag_row in tag_rows:
            assert tag_row.run_id == run_id
            assert tag_row.shift_type
            assert tag_row.sub_segment_index >= 1
            assert tag_row.confidence >= 0.0
            assert tag_row.boundary_end_char >= tag_row.boundary_start_char
            assert session.query(Segment).filter(Segment.id == tag_row.segment_id).one_or_none() is not None
            assert tag_row.segment_id
            assert tag_row.chapter_id
    finally:
        session.close()
