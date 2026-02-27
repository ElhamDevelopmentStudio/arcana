import os
from pathlib import Path

from sqlalchemy import create_engine, text

TEST_DATABASE_URL = "sqlite:///./test_nipe_character_schema_compatibility.db"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from app.config import clear_settings_cache
from app.database import get_engine, get_session_factory, init_db, reset_engine
from app.models import Character


def setup_module() -> None:
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    clear_settings_cache()
    reset_engine()
    db_file = Path("test_nipe_character_schema_compatibility.db")
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
                "CREATE TABLE characters ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE, "
                "name VARCHAR(255) NOT NULL, "
                "verbalized_form VARCHAR(255) NOT NULL, "
                "gender VARCHAR(50) NOT NULL, "
                "voice_id VARCHAR(255)"
                ")"
            )
        )
        connection.execute(text("INSERT INTO projects (title) VALUES ('Legacy Character Project')"))
        connection.execute(
            text(
                "INSERT INTO characters (project_id, name, verbalized_form, gender, voice_id) "
                "VALUES (1, 'Sunny', 'Sunny', 'male', NULL)"
            )
        )
    engine.dispose()

    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()
    db_file = Path("test_nipe_character_schema_compatibility.db")
    if db_file.exists():
        db_file.unlink()


def test_integration_init_db_backfills_legacy_character_columns() -> None:
    session = get_session_factory()()
    try:
        character = session.query(Character).filter(Character.project_id == 1).one()
        assert character.name == "Sunny"
        assert character.aliases == []
        assert character.notes is None
        assert character.source == "user_import"
        assert character.confidence == 1.0
        assert character.inferred_gender == "unknown"
        assert character.inferred_confidence == 0.0
        assert character.inferred_source_trace == []
    finally:
        session.close()

    engine = get_engine()
    with engine.begin() as connection:
        row = connection.execute(
            text(
                "SELECT aliases, source, confidence, inferred_gender, inferred_confidence, inferred_source_trace "
                "FROM characters WHERE id = 1"
            )
        ).mappings().one()

    assert row["source"] == "user_import"
    assert float(row["confidence"]) == 1.0
    assert row["inferred_gender"] == "unknown"
    assert float(row["inferred_confidence"]) == 0.0
