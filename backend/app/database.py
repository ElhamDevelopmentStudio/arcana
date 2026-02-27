from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(settings.database_url, pool_pre_ping=True)
    return _engine


def reset_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
    return _session_factory


def init_db() -> None:
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    _apply_schema_compatibility_updates(engine)


def _apply_schema_compatibility_updates(engine) -> None:
    inspector = inspect(engine)
    if "projects" not in set(inspector.get_table_names()):
        return

    project_columns = {column["name"] for column in inspector.get_columns("projects")}
    dialect_name = engine.dialect.name
    with engine.begin() as connection:
        if "lifecycle_state" not in project_columns:
            connection.execute(
                text(
                    "ALTER TABLE projects ADD COLUMN lifecycle_state VARCHAR(40) NOT NULL DEFAULT 'draft'"
                )
            )

        if "description" not in project_columns:
            connection.execute(
                text(
                    "ALTER TABLE projects ADD COLUMN description TEXT"
                )
            )

        if "tags" not in project_columns:
            if dialect_name == "postgresql":
                connection.execute(
                    text(
                        "ALTER TABLE projects ADD COLUMN tags JSON NOT NULL DEFAULT '[]'::json"
                    )
                )
            else:
                connection.execute(
                    text(
                        "ALTER TABLE projects ADD COLUMN tags JSON NOT NULL DEFAULT '[]'"
                    )
                )

        if "last_run_status" not in project_columns:
            connection.execute(
                text(
                    "ALTER TABLE projects ADD COLUMN last_run_status VARCHAR(40)"
                )
            )

        if "last_export_at" not in project_columns:
            if dialect_name == "postgresql":
                connection.execute(
                    text(
                        "ALTER TABLE projects ADD COLUMN last_export_at TIMESTAMPTZ"
                    )
                )
            else:
                connection.execute(
                    text(
                        "ALTER TABLE projects ADD COLUMN last_export_at DATETIME"
                    )
                )

        if "next_required_action" not in project_columns:
            connection.execute(
                text(
                    "ALTER TABLE projects ADD COLUMN next_required_action VARCHAR(40) NOT NULL DEFAULT 'ingest'"
                )
            )

        if "selected_mode" not in project_columns:
            connection.execute(
                text(
                    "ALTER TABLE projects ADD COLUMN selected_mode VARCHAR(50) NOT NULL DEFAULT 'audiobook'"
                )
            )

        if "selected_modes" not in project_columns:
            if dialect_name == "postgresql":
                connection.execute(
                    text(
                        "ALTER TABLE projects ADD COLUMN selected_modes JSON NOT NULL DEFAULT '[]'::json"
                    )
                )
            else:
                connection.execute(
                    text(
                        "ALTER TABLE projects ADD COLUMN selected_modes JSON NOT NULL DEFAULT '[]'"
                    )
                )

        if "llm_enabled" not in project_columns:
            if dialect_name == "postgresql":
                connection.execute(
                    text(
                        "ALTER TABLE projects ADD COLUMN llm_enabled BOOLEAN NOT NULL DEFAULT FALSE"
                    )
                )
            else:
                connection.execute(
                    text(
                        "ALTER TABLE projects ADD COLUMN llm_enabled BOOLEAN NOT NULL DEFAULT 0"
                    )
                )

        if "do_not_store_source_text" not in project_columns:
            if dialect_name == "postgresql":
                connection.execute(
                    text(
                        "ALTER TABLE projects ADD COLUMN do_not_store_source_text BOOLEAN NOT NULL DEFAULT FALSE"
                    )
                )
            else:
                connection.execute(
                    text(
                        "ALTER TABLE projects ADD COLUMN do_not_store_source_text BOOLEAN NOT NULL DEFAULT 0"
                    )
                )

        if "configuration_snapshot_id" not in project_columns:
            connection.execute(
                text(
                    "ALTER TABLE projects ADD COLUMN configuration_snapshot_id VARCHAR(120)"
                )
            )

        if "voice_config_json" not in project_columns:
            if dialect_name == "postgresql":
                connection.execute(
                    text(
                        "ALTER TABLE projects ADD COLUMN voice_config_json JSON NOT NULL DEFAULT '{}'::json"
                    )
                )
            else:
                connection.execute(
                    text(
                        "ALTER TABLE projects ADD COLUMN voice_config_json JSON NOT NULL DEFAULT '{}'"
                    )
                )

        if "llm_provider_config_json" not in project_columns:
            if dialect_name == "postgresql":
                connection.execute(
                    text(
                        "ALTER TABLE projects ADD COLUMN llm_provider_config_json JSON NOT NULL DEFAULT '{}'::json"
                    )
                )
            else:
                connection.execute(
                    text(
                        "ALTER TABLE projects ADD COLUMN llm_provider_config_json JSON NOT NULL DEFAULT '{}'"
                    )
                )

        if "default_narrator_voice" not in project_columns:
            connection.execute(
                text(
                    "ALTER TABLE projects ADD COLUMN default_narrator_voice VARCHAR(255) NOT NULL DEFAULT 'narrator_default'"
                )
            )

        if "default_male_voice" not in project_columns:
            connection.execute(
                text(
                    "ALTER TABLE projects ADD COLUMN default_male_voice VARCHAR(255) NOT NULL DEFAULT 'male_default'"
                )
            )

        if "default_female_voice" not in project_columns:
            connection.execute(
                text(
                    "ALTER TABLE projects ADD COLUMN default_female_voice VARCHAR(255) NOT NULL DEFAULT 'female_default'"
                )
            )

        if "default_neutral_voice" not in project_columns:
            connection.execute(
                text(
                    "ALTER TABLE projects ADD COLUMN default_neutral_voice VARCHAR(255) NOT NULL DEFAULT 'neutral_default'"
                )
            )

        if "default_unknown_voice" not in project_columns:
            connection.execute(
                text(
                    "ALTER TABLE projects ADD COLUMN default_unknown_voice VARCHAR(255) NOT NULL DEFAULT 'unknown_default'"
                )
            )

        if "ingestion_log_json" not in project_columns:
            if dialect_name == "postgresql":
                connection.execute(
                    text(
                        "ALTER TABLE projects ADD COLUMN ingestion_log_json JSON NOT NULL DEFAULT '{}'::json"
                    )
                )
            else:
                connection.execute(
                    text(
                        "ALTER TABLE projects ADD COLUMN ingestion_log_json JSON NOT NULL DEFAULT '{}'"
                    )
                )

        if "ingestion_timestamp" not in project_columns:
            if dialect_name == "postgresql":
                connection.execute(
                    text(
                        "ALTER TABLE projects ADD COLUMN ingestion_timestamp TIMESTAMPTZ"
                    )
                )
            else:
                connection.execute(
                    text(
                        "ALTER TABLE projects ADD COLUMN ingestion_timestamp DATETIME"
                    )
                )

        if "character_map_finalized" not in project_columns:
            if dialect_name == "postgresql":
                connection.execute(
                    text(
                        "ALTER TABLE projects ADD COLUMN character_map_finalized BOOLEAN NOT NULL DEFAULT FALSE"
                    )
                )
            else:
                connection.execute(
                    text(
                        "ALTER TABLE projects ADD COLUMN character_map_finalized BOOLEAN NOT NULL DEFAULT 0"
                    )
                )


def get_session() -> Generator[Session, None, None]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()
