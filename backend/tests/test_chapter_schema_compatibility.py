import os
from pathlib import Path

from sqlalchemy import create_engine, text

TEST_DATABASE_URL = "sqlite:///./test_nipe_chapter_schema_compatibility.db"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from app.config import clear_settings_cache
from app.database import get_engine, get_session_factory, init_db, reset_engine
from app.models import Chapter


def setup_module() -> None:
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    clear_settings_cache()
    reset_engine()
    db_file = Path("test_nipe_chapter_schema_compatibility.db")
    if db_file.exists():
        db_file.unlink()

    engine = create_engine(TEST_DATABASE_URL)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE projects ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "title VARCHAR(255) NOT NULL, "
                "selected_mode VARCHAR(50) NOT NULL DEFAULT 'audiobook', "
                "voice_config_json JSON NOT NULL DEFAULT '{}', "
                "default_narrator_voice VARCHAR(255) NOT NULL DEFAULT 'narrator_default', "
                "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"
                ")"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE chapters ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE, "
                "chapter_index INTEGER NOT NULL, "
                "chapter_title VARCHAR(255) NOT NULL, "
                "raw_text TEXT NOT NULL, "
                "normalized_text TEXT NOT NULL, "
                "CONSTRAINT uq_project_chapter_index UNIQUE (project_id, chapter_index)"
                ")"
            )
        )
        connection.execute(text("INSERT INTO projects (title) VALUES ('Legacy Project')"))
        connection.execute(
            text(
                "INSERT INTO chapters (project_id, chapter_index, chapter_title, raw_text, normalized_text) "
                "VALUES (1, 1, 'Chapter 1', 'Legacy Raw', 'Legacy Normalized')"
            )
        )
    engine.dispose()

    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()
    db_file = Path("test_nipe_chapter_schema_compatibility.db")
    if db_file.exists():
        db_file.unlink()


def test_integration_init_db_backfills_legacy_chapter_columns() -> None:
    session = get_session_factory()()
    try:
        chapter = session.query(Chapter).filter(Chapter.project_id == 1).one()
        assert chapter.chapter_internal_id == "ch-0001"
        assert chapter.original_text_snapshot == "Legacy Raw"
        assert chapter.normalized_text_snapshot == "Legacy Normalized"
        assert chapter.original_to_normalized_offset_map == []
    finally:
        session.close()

    engine = get_engine()
    with engine.begin() as connection:
        row = connection.execute(
            text(
                "SELECT chapter_internal_id, original_text_snapshot, normalized_text_snapshot "
                "FROM chapters WHERE id = 1"
            )
        ).mappings().one()
    assert row["chapter_internal_id"] == "ch-0001"
    assert row["original_text_snapshot"] == "Legacy Raw"
    assert row["normalized_text_snapshot"] == "Legacy Normalized"
