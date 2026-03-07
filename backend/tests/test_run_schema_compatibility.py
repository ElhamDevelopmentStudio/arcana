import os
from pathlib import Path

from sqlalchemy import create_engine, text

TEST_DATABASE_URL = "sqlite:///./test_nipe_run_schema_compatibility.db"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from app.config import clear_settings_cache
from app.database import get_engine, get_session_factory, init_db, reset_engine
from app.models import Run


def setup_module() -> None:
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    clear_settings_cache()
    reset_engine()
    db_file = Path("test_nipe_run_schema_compatibility.db")
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
                "CREATE TABLE runs ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE"
                ")"
            )
        )
        connection.execute(text("INSERT INTO projects (title) VALUES ('Legacy Run Project')"))
        connection.execute(text("INSERT INTO runs (project_id) VALUES (1)"))
    engine.dispose()

    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()
    db_file = Path("test_nipe_run_schema_compatibility.db")
    if db_file.exists():
        db_file.unlink()


def test_integration_init_db_backfills_legacy_run_columns() -> None:
    session = get_session_factory()()
    try:
        run = session.query(Run).filter(Run.project_id == 1).one()
        assert run.status == "pending"
        assert run.deterministic_seed is None
        assert run.deterministic_model_identifier is None
        assert run.deterministic_randomization_config is None
        assert run.llm_provider_name is None
        assert run.llm_model_identifier is None
        assert run.llm_model_version is None
        assert run.config_json == {}
        assert run.started_at is not None
        assert run.finished_at is None
    finally:
        session.close()

    engine = get_engine()
    with engine.begin() as connection:
        row = connection.execute(
            text(
                "SELECT status, deterministic_seed, llm_provider_name, config_json "
                "FROM runs WHERE id = 1"
            )
        ).mappings().one()
    assert row["status"] == "pending"
    assert row["deterministic_seed"] is None
    assert row["llm_provider_name"] is None
    assert row["config_json"] == "{}"
