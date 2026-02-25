import os
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_norm_offset_map.db"

import pytest

from app.services.normalization import (
    build_original_to_normalized_offset_map,
    build_segment_level_offset_map,
)


def setup_module() -> None:
    from app.config import clear_settings_cache
    from app.database import init_db, reset_engine

    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    from app.config import clear_settings_cache
    from app.database import reset_engine

    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_norm_offset_map.db")
    if db_file.exists():
        db_file.unlink()



def test_unit_build_original_to_normalized_offset_map_tracks_equal_and_insert_ops() -> None:
    original = "ab"
    normalized = "a-b"

    mapping = build_original_to_normalized_offset_map(original, normalized)

    assert mapping == [
        {
            "type": "equal",
            "original_start": 0,
            "original_end": 1,
            "normalized_start": 0,
            "normalized_end": 1,
        },
        {
            "type": "insert",
            "original_start": 1,
            "original_end": 1,
            "normalized_start": 1,
            "normalized_end": 2,
        },
        {
            "type": "equal",
            "original_start": 1,
            "original_end": 2,
            "normalized_start": 2,
            "normalized_end": 3,
        },
    ]


def test_unit_build_original_to_normalized_offset_map_tracks_replace_op() -> None:
    original = "He said “Hello and waited."
    normalized = 'He said "Hello and waited."'

    mapping = build_original_to_normalized_offset_map(original, normalized)

    assert mapping[1] == {
        "type": "replace",
        "original_start": 8,
        "original_end": 9,
        "normalized_start": 8,
        "normalized_end": 9,
    }
    assert mapping[2] == {
        "type": "equal",
        "original_start": 9,
        "original_end": 26,
        "normalized_start": 9,
        "normalized_end": 26,
    }
    assert mapping[3] == {
        "type": "insert",
        "original_start": 26,
        "original_end": 26,
        "normalized_start": 26,
        "normalized_end": 27,
    }


def test_unit_build_segment_level_offset_map_shifts_segment_offsets() -> None:
    original = "He said “Hello and waited."
    normalized = 'He said "Hello and waited."'
    chapter_map = build_original_to_normalized_offset_map(original, normalized)
    segment_start = 8
    segment_text = '"Hello and waited."'

    segment_map = build_segment_level_offset_map(chapter_map, segment_start, segment_text)

    assert segment_map == [
        {
            "type": "replace",
            "original_start": 8,
            "original_end": 9,
            "normalized_start": 0,
            "normalized_end": 1,
        },
        {
            "type": "equal",
            "original_start": 9,
            "original_end": 26,
            "normalized_start": 1,
            "normalized_end": 18,
        },
        {
            "type": "insert",
            "original_start": -1,
            "original_end": -1,
            "normalized_start": 18,
            "normalized_end": 19,
        },
    ]


def test_unit_persist_chapter_original_to_normalized_offset_map_in_database() -> None:
    try:
        from app.config import clear_settings_cache
        from app.database import get_session_factory, init_db, reset_engine
        from app.models import Chapter, Project
    except ImportError as exc:
        pytest.skip(f"chapter persistence test unavailable in current environment: {exc}")

    original = "He said \u201cHello and waited."
    normalized = 'He said "Hello and waited."'
    offset_map = build_original_to_normalized_offset_map(original, normalized)

    clear_settings_cache()
    reset_engine()
    init_db()
    session = get_session_factory()()
    try:
        project = Project(title="Offset Map Persistence Test")
        session.add(project)
        session.flush()

        session.add(
            Chapter(
                project_id=project.id,
                chapter_index=1,
                chapter_internal_id="chapter-1",
                chapter_title="Chapter 1",
                raw_text=original,
                original_text_snapshot=original,
                normalized_text=normalized,
                normalized_text_snapshot=normalized,
                original_to_normalized_offset_map=offset_map,
            )
        )
        session.commit()

        loaded = session.query(Chapter).filter(Chapter.project_id == project.id).one()
        assert loaded.original_to_normalized_offset_map == offset_map
        assert loaded.original_to_normalized_offset_map[1]["type"] == "replace"
    finally:
        session.close()
