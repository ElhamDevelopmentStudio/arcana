CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    selected_mode VARCHAR(50) NOT NULL DEFAULT 'audiobook',
    voice_config_json JSON NOT NULL DEFAULT '{}'::json,
    default_narrator_voice VARCHAR(255) NOT NULL DEFAULT 'narrator_default',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chapters (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    chapter_index INTEGER NOT NULL,
    chapter_title VARCHAR(255) NOT NULL,
    raw_text TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    CONSTRAINT uq_project_chapter_index UNIQUE (project_id, chapter_index)
);

CREATE TABLE IF NOT EXISTS characters (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    verbalized_form VARCHAR(255) NOT NULL,
    gender VARCHAR(50) NOT NULL,
    aliases JSONB NOT NULL DEFAULT '[]'::jsonb,
    notes TEXT,
    source VARCHAR(120) NOT NULL DEFAULT 'user_import',
    confidence REAL NOT NULL DEFAULT 1.0,
    voice_id VARCHAR(255),
    CONSTRAINT uq_project_character_name UNIQUE (project_id, name)
);

CREATE TABLE IF NOT EXISTS runs (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL,
    deterministic_seed INTEGER,
    deterministic_model_identifier VARCHAR(255),
    deterministic_randomization_config JSONB,
    config_json JSON NOT NULL DEFAULT '{}'::json,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS segments (
    id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    segment_index INTEGER NOT NULL,
    segment_json JSON NOT NULL,
    CONSTRAINT uq_run_chapter_segment UNIQUE (run_id, chapter_id, segment_index)
);

CREATE TABLE IF NOT EXISTS llm_calls (
    id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    provider VARCHAR(100) NOT NULL,
    task_type VARCHAR(100) NOT NULL,
    success BOOLEAN NOT NULL,
    request_count INTEGER NOT NULL,
    is_cache_hit BOOLEAN NOT NULL DEFAULT FALSE,
    detail TEXT,
    model_identifier VARCHAR(255),
    called_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE llm_calls ADD COLUMN IF NOT EXISTS model_identifier VARCHAR(255);
ALTER TABLE llm_calls ADD COLUMN IF NOT EXISTS called_at TIMESTAMPTZ;
ALTER TABLE llm_calls ADD COLUMN IF NOT EXISTS is_cache_hit BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS provider_api_key_usage_audit (
    id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    provider VARCHAR(100) NOT NULL,
    task_type VARCHAR(100) NOT NULL,
    request_id VARCHAR(36),
    attempt_index INTEGER NOT NULL,
    provider_api_key_masked VARCHAR(64),
    provider_api_key_fingerprint VARCHAR(64),
    model_identifier VARCHAR(255),
    success BOOLEAN NOT NULL,
    error_code VARCHAR(64),
    token_usage_estimate INTEGER,
    called_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS provider_quota (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(100) NOT NULL,
    day_key VARCHAR(20) NOT NULL,
    scope_key VARCHAR(120) NOT NULL DEFAULT 'global',
    calls_used INTEGER NOT NULL DEFAULT 0,
    max_calls_per_day INTEGER NOT NULL,
    blocked BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT uq_provider_day_scope UNIQUE (provider, day_key, scope_key)
);

CREATE TABLE IF NOT EXISTS provider_api_key_quota (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(100) NOT NULL,
    provider_api_key VARCHAR(255) NOT NULL,
    day_key VARCHAR(20) NOT NULL,
    scope_key VARCHAR(120) NOT NULL DEFAULT 'global',
    calls_used INTEGER NOT NULL DEFAULT 0,
    max_calls_per_day INTEGER NOT NULL,
    blocked BOOLEAN NOT NULL DEFAULT FALSE,
    last_rate_limit_status VARCHAR(64),
    last_rate_limit_status_at TIMESTAMPTZ,
    last_rate_limit_reset_at TIMESTAMPTZ,
    last_successful_call_at TIMESTAMPTZ,
    CONSTRAINT uq_provider_api_key_day_scope UNIQUE (provider, provider_api_key, day_key, scope_key)
);

CREATE TABLE IF NOT EXISTS llm_cache (
    id SERIAL PRIMARY KEY,
    input_text_hash CHAR(64) NOT NULL,
    task_type VARCHAR(100) NOT NULL,
    configuration_snapshot_id VARCHAR(120) NOT NULL,
    model_identifier VARCHAR(255) NOT NULL,
    response_payload JSON NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_llm_cache_input_text_hash_task_type_configuration_snapshot_model UNIQUE (input_text_hash, task_type, configuration_snapshot_id, model_identifier)
);
