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
    table_names = set(inspector.get_table_names())
    if "projects" not in table_names:
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

        if "chapters" in table_names:
            chapter_columns = {column["name"] for column in inspector.get_columns("chapters")}

            if "chapter_internal_id" not in chapter_columns:
                connection.execute(
                    text(
                        "ALTER TABLE chapters ADD COLUMN chapter_internal_id VARCHAR(80) NOT NULL DEFAULT ''"
                    )
                )
                if dialect_name == "postgresql":
                    connection.execute(
                        text(
                            "UPDATE chapters "
                            "SET chapter_internal_id = CONCAT('ch-', LPAD(CAST(chapter_index AS TEXT), 4, '0')) "
                            "WHERE chapter_internal_id IS NULL OR chapter_internal_id = ''"
                        )
                    )
                else:
                    connection.execute(
                        text(
                            "UPDATE chapters "
                            "SET chapter_internal_id = 'ch-' || printf('%04d', chapter_index) "
                            "WHERE chapter_internal_id IS NULL OR chapter_internal_id = ''"
                        )
                    )

            if "original_text_snapshot" not in chapter_columns:
                connection.execute(
                    text(
                        "ALTER TABLE chapters ADD COLUMN original_text_snapshot TEXT NOT NULL DEFAULT ''"
                    )
                )
                connection.execute(
                    text(
                        "UPDATE chapters "
                        "SET original_text_snapshot = raw_text "
                        "WHERE original_text_snapshot IS NULL OR original_text_snapshot = ''"
                    )
                )

            if "normalized_text_snapshot" not in chapter_columns:
                connection.execute(
                    text(
                        "ALTER TABLE chapters ADD COLUMN normalized_text_snapshot TEXT NOT NULL DEFAULT ''"
                    )
                )
                connection.execute(
                    text(
                        "UPDATE chapters "
                        "SET normalized_text_snapshot = normalized_text "
                        "WHERE normalized_text_snapshot IS NULL OR normalized_text_snapshot = ''"
                    )
                )

            if "original_to_normalized_offset_map" not in chapter_columns:
                if dialect_name == "postgresql":
                    connection.execute(
                        text(
                            "ALTER TABLE chapters "
                            "ADD COLUMN original_to_normalized_offset_map JSON NOT NULL DEFAULT '[]'::json"
                        )
                    )
                else:
                    connection.execute(
                        text(
                            "ALTER TABLE chapters "
                            "ADD COLUMN original_to_normalized_offset_map JSON NOT NULL DEFAULT '[]'"
                        )
                    )

            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_project_chapter_internal_id "
                    "ON chapters (project_id, chapter_internal_id)"
                )
            )

        if "characters" in table_names:
            character_columns = {column["name"] for column in inspector.get_columns("characters")}

            if "aliases" not in character_columns:
                if dialect_name == "postgresql":
                    connection.execute(
                        text(
                            "ALTER TABLE characters ADD COLUMN aliases JSON NOT NULL DEFAULT '[]'::json"
                        )
                    )
                else:
                    connection.execute(
                        text(
                            "ALTER TABLE characters ADD COLUMN aliases JSON NOT NULL DEFAULT '[]'"
                        )
                    )
            else:
                if dialect_name == "postgresql":
                    connection.execute(
                        text(
                            "UPDATE characters SET aliases = '[]'::json WHERE aliases IS NULL"
                        )
                    )
                else:
                    connection.execute(
                        text(
                            "UPDATE characters SET aliases = '[]' WHERE aliases IS NULL"
                        )
                    )

            if "notes" not in character_columns:
                connection.execute(
                    text(
                        "ALTER TABLE characters ADD COLUMN notes TEXT"
                    )
                )

            if "source" not in character_columns:
                connection.execute(
                    text(
                        "ALTER TABLE characters ADD COLUMN source VARCHAR(120) NOT NULL DEFAULT 'user_import'"
                    )
                )
            else:
                connection.execute(
                    text(
                        "UPDATE characters SET source = 'user_import' WHERE source IS NULL OR source = ''"
                    )
                )

            if "confidence" not in character_columns:
                connection.execute(
                    text(
                        "ALTER TABLE characters ADD COLUMN confidence DOUBLE PRECISION NOT NULL DEFAULT 1.0"
                    )
                )
            else:
                connection.execute(
                    text(
                        "UPDATE characters SET confidence = 1.0 WHERE confidence IS NULL"
                    )
                )

            if "inferred_gender" not in character_columns:
                connection.execute(
                    text(
                        "ALTER TABLE characters ADD COLUMN inferred_gender VARCHAR(50) NOT NULL DEFAULT 'unknown'"
                    )
                )
            else:
                connection.execute(
                    text(
                        "UPDATE characters SET inferred_gender = 'unknown' "
                        "WHERE inferred_gender IS NULL OR inferred_gender = ''"
                    )
                )

            if "inferred_confidence" not in character_columns:
                connection.execute(
                    text(
                        "ALTER TABLE characters ADD COLUMN inferred_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0"
                    )
                )
            else:
                connection.execute(
                    text(
                        "UPDATE characters SET inferred_confidence = 0.0 WHERE inferred_confidence IS NULL"
                    )
                )

            if "inferred_source_trace" not in character_columns:
                if dialect_name == "postgresql":
                    connection.execute(
                        text(
                            "ALTER TABLE characters ADD COLUMN inferred_source_trace JSON NOT NULL DEFAULT '[]'::json"
                        )
                    )
                else:
                    connection.execute(
                        text(
                            "ALTER TABLE characters ADD COLUMN inferred_source_trace JSON NOT NULL DEFAULT '[]'"
                        )
                    )
            else:
                if dialect_name == "postgresql":
                    connection.execute(
                        text(
                            "UPDATE characters SET inferred_source_trace = '[]'::json WHERE inferred_source_trace IS NULL"
                        )
                    )
                else:
                    connection.execute(
                        text(
                            "UPDATE characters SET inferred_source_trace = '[]' WHERE inferred_source_trace IS NULL"
                        )
                    )

            if "voice_id" not in character_columns:
                connection.execute(
                    text(
                        "ALTER TABLE characters ADD COLUMN voice_id VARCHAR(255)"
                    )
                )

        if "provider_quota" in table_names:
            provider_quota_columns = {column["name"] for column in inspector.get_columns("provider_quota")}

            if "scope_key" not in provider_quota_columns:
                connection.execute(
                    text(
                        "ALTER TABLE provider_quota ADD COLUMN scope_key VARCHAR(120) NOT NULL DEFAULT 'global'"
                    )
                )
            else:
                connection.execute(
                    text(
                        "UPDATE provider_quota SET scope_key = 'global' WHERE scope_key IS NULL OR scope_key = ''"
                    )
                )

            if "last_rate_limit_status" not in provider_quota_columns:
                connection.execute(
                    text(
                        "ALTER TABLE provider_quota ADD COLUMN last_rate_limit_status VARCHAR(64)"
                    )
                )

            if "last_rate_limit_status_at" not in provider_quota_columns:
                if dialect_name == "postgresql":
                    connection.execute(
                        text(
                            "ALTER TABLE provider_quota ADD COLUMN last_rate_limit_status_at TIMESTAMPTZ"
                        )
                    )
                else:
                    connection.execute(
                        text(
                            "ALTER TABLE provider_quota ADD COLUMN last_rate_limit_status_at DATETIME"
                        )
                    )

            if "last_rate_limit_reset_at" not in provider_quota_columns:
                if dialect_name == "postgresql":
                    connection.execute(
                        text(
                            "ALTER TABLE provider_quota ADD COLUMN last_rate_limit_reset_at TIMESTAMPTZ"
                        )
                    )
                else:
                    connection.execute(
                        text(
                            "ALTER TABLE provider_quota ADD COLUMN last_rate_limit_reset_at DATETIME"
                        )
                    )

            if "last_successful_call_at" not in provider_quota_columns:
                if dialect_name == "postgresql":
                    connection.execute(
                        text(
                            "ALTER TABLE provider_quota ADD COLUMN last_successful_call_at TIMESTAMPTZ"
                        )
                    )
                else:
                    connection.execute(
                        text(
                            "ALTER TABLE provider_quota ADD COLUMN last_successful_call_at DATETIME"
                        )
                    )

            if dialect_name == "postgresql":
                connection.execute(text("ALTER TABLE provider_quota DROP CONSTRAINT IF EXISTS uq_provider_day"))
            connection.execute(text("DROP INDEX IF EXISTS uq_provider_day"))
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_provider_day_scope "
                    "ON provider_quota (provider, day_key, scope_key)"
                )
            )

        if "llm_calls" in table_names:
            llm_call_columns = {column["name"] for column in inspector.get_columns("llm_calls")}

            if "model_identifier" not in llm_call_columns:
                connection.execute(
                    text(
                        "ALTER TABLE llm_calls ADD COLUMN model_identifier VARCHAR(255)"
                    )
                )

            if "called_at" not in llm_call_columns:
                if dialect_name == "postgresql":
                    connection.execute(
                        text(
                            "ALTER TABLE llm_calls ADD COLUMN called_at TIMESTAMPTZ"
                        )
                    )
                else:
                    connection.execute(
                        text(
                            "ALTER TABLE llm_calls ADD COLUMN called_at DATETIME"
                        )
                    )

            if "is_cache_hit" not in llm_call_columns:
                if dialect_name == "postgresql":
                    connection.execute(
                        text(
                            "ALTER TABLE llm_calls ADD COLUMN is_cache_hit BOOLEAN NOT NULL DEFAULT FALSE"
                        )
                    )
                else:
                    connection.execute(
                        text(
                            "ALTER TABLE llm_calls ADD COLUMN is_cache_hit BOOLEAN NOT NULL DEFAULT 0"
                        )
                    )
            else:
                if dialect_name == "postgresql":
                    connection.execute(
                        text(
                            "UPDATE llm_calls SET is_cache_hit = FALSE WHERE is_cache_hit IS NULL"
                        )
                    )
                else:
                    connection.execute(
                        text(
                            "UPDATE llm_calls SET is_cache_hit = 0 WHERE is_cache_hit IS NULL"
                        )
                    )

        if "runs" in table_names:
            run_columns = {column["name"] for column in inspector.get_columns("runs")}

            if "status" not in run_columns:
                connection.execute(
                    text(
                        "ALTER TABLE runs ADD COLUMN status VARCHAR(50) NOT NULL DEFAULT 'pending'"
                    )
                )

            if "deterministic_seed" not in run_columns:
                connection.execute(
                    text(
                        "ALTER TABLE runs ADD COLUMN deterministic_seed INTEGER"
                    )
                )

            if "deterministic_model_identifier" not in run_columns:
                connection.execute(
                    text(
                        "ALTER TABLE runs ADD COLUMN deterministic_model_identifier VARCHAR(255)"
                    )
                )

            if "deterministic_randomization_config" not in run_columns:
                connection.execute(
                    text(
                        "ALTER TABLE runs ADD COLUMN deterministic_randomization_config JSON"
                    )
                )

            if "llm_provider_name" not in run_columns:
                connection.execute(
                    text(
                        "ALTER TABLE runs ADD COLUMN llm_provider_name VARCHAR(100)"
                    )
                )

            if "llm_model_identifier" not in run_columns:
                connection.execute(
                    text(
                        "ALTER TABLE runs ADD COLUMN llm_model_identifier VARCHAR(255)"
                    )
                )

            if "llm_model_version" not in run_columns:
                connection.execute(
                    text(
                        "ALTER TABLE runs ADD COLUMN llm_model_version VARCHAR(120)"
                    )
                )

            if "config_json" not in run_columns:
                if dialect_name == "postgresql":
                    connection.execute(
                        text(
                            "ALTER TABLE runs ADD COLUMN config_json JSON NOT NULL DEFAULT '{}'::json"
                        )
                    )
                else:
                    connection.execute(
                        text(
                            "ALTER TABLE runs ADD COLUMN config_json JSON NOT NULL DEFAULT '{}'"
                        )
                    )
            else:
                if dialect_name == "postgresql":
                    connection.execute(
                        text(
                            "UPDATE runs SET config_json = '{}'::json WHERE config_json IS NULL"
                        )
                    )
                else:
                    connection.execute(
                        text(
                            "UPDATE runs SET config_json = '{}' WHERE config_json IS NULL"
                        )
                    )

            if "started_at" not in run_columns:
                if dialect_name == "postgresql":
                    connection.execute(
                        text(
                            "ALTER TABLE runs ADD COLUMN started_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
                        )
                    )
                else:
                    connection.execute(
                        text(
                            "ALTER TABLE runs ADD COLUMN started_at DATETIME"
                        )
                    )
                    connection.execute(
                        text(
                            "UPDATE runs SET started_at = CURRENT_TIMESTAMP WHERE started_at IS NULL"
                        )
                    )

            if "finished_at" not in run_columns:
                if dialect_name == "postgresql":
                    connection.execute(
                        text(
                            "ALTER TABLE runs ADD COLUMN finished_at TIMESTAMPTZ"
                        )
                    )
                else:
                    connection.execute(
                        text(
                            "ALTER TABLE runs ADD COLUMN finished_at DATETIME"
                        )
                    )


def get_session() -> Generator[Session, None, None]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()
