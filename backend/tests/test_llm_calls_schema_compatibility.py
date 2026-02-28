import os
from pathlib import Path

from sqlalchemy import create_engine, text

TEST_DATABASE_URL = "sqlite:///./test_nipe_llm_calls_schema_compatibility.db"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from app.config import clear_settings_cache
from app.database import get_engine, init_db, reset_engine


def setup_module() -> None:
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    clear_settings_cache()
    reset_engine()
    db_file = Path("test_nipe_llm_calls_schema_compatibility.db")
    if db_file.exists():
        db_file.unlink()

    engine = create_engine(TEST_DATABASE_URL)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE llm_calls ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "run_id INTEGER NOT NULL, "
                "provider VARCHAR(100) NOT NULL, "
                "task_type VARCHAR(100) NOT NULL, "
                "success BOOLEAN NOT NULL, "
                "request_count INTEGER NOT NULL, "
                "detail TEXT, "
                "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"
                ")"
            )
        )
        connection.execute(
            text(
                "INSERT INTO llm_calls (run_id, provider, task_type, success, request_count, detail) "
                "VALUES (1, 'openrouter', 'tagging', 1, 1, 'ok')"
            )
        )
    engine.dispose()

    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()
    db_file = Path("test_nipe_llm_calls_schema_compatibility.db")
    if db_file.exists():
        db_file.unlink()


def test_integration_init_db_backfills_legacy_llm_calls_columns() -> None:
    engine = get_engine()
    with engine.begin() as connection:
        columns = {
            row["name"]: row
            for row in connection.execute(text("PRAGMA table_info(llm_calls)")).mappings()
        }
        row = connection.execute(
            text(
                "SELECT model_identifier, called_at, is_cache_hit "
                "FROM llm_calls WHERE id = 1"
            )
        ).mappings().one()

    assert {"model_identifier", "called_at", "is_cache_hit"}.issubset(columns.keys())
    assert row["model_identifier"] is None
    assert row["called_at"] is None
    assert int(row["is_cache_hit"]) == 0
