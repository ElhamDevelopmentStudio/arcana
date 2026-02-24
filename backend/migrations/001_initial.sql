CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    voice_config_json JSON NOT NULL DEFAULT '{}'::json,
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
    voice_id VARCHAR(255),
    CONSTRAINT uq_project_character_name UNIQUE (project_id, name)
);

CREATE TABLE IF NOT EXISTS runs (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL,
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
    detail TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS provider_quota (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(100) NOT NULL,
    day_key VARCHAR(20) NOT NULL,
    calls_used INTEGER NOT NULL DEFAULT 0,
    max_calls_per_day INTEGER NOT NULL,
    blocked BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT uq_provider_day UNIQUE (provider, day_key)
);
