import os
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.models import LLMCache


os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_llm_cache.db"


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_llm_cache.db")
    if db_file.exists():
        db_file.unlink()


def test_llm_cache_table_includes_task_type_in_key() -> None:
    session_factory = get_session_factory()
    session = session_factory()

    try:
        session.query(LLMCache).delete()
        session.commit()

        first_entry = LLMCache(
            input_text_hash="a" * 64,
            task_type="emotion_refinement",
            configuration_snapshot_id="snapshot-1",
            response_payload={"value": "cached-response"},
        )
        session.add(first_entry)
        session.commit()

        assert first_entry.id is not None
        assert first_entry.created_at is not None

        duplicate_entry = LLMCache(
            input_text_hash="a" * 64,
            task_type="emotion_refinement",
            configuration_snapshot_id="snapshot-1",
            response_payload={"value": "different"},
        )
        session.add(duplicate_entry)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        assert session.query(LLMCache).count() == 1

        different_task_type_entry = LLMCache(
            input_text_hash="a" * 64,
            task_type="speaker_resolution",
            configuration_snapshot_id="snapshot-1",
            response_payload={"value": "speaker-cache"},
        )
        session.add(different_task_type_entry)
        session.commit()

        assert session.query(LLMCache).count() == 2

        different_snapshot_entry = LLMCache(
            input_text_hash="a" * 64,
            task_type="speaker_resolution",
            configuration_snapshot_id="snapshot-2",
            response_payload={"value": "speaker-cache-snapshot-2"},
        )
        session.add(different_snapshot_entry)
        session.commit()

        assert session.query(LLMCache).count() == 3
    finally:
        session.rollback()
        session.close()
