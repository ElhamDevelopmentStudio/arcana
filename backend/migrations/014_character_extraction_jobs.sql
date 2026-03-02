CREATE TABLE IF NOT EXISTS character_extraction_jobs (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(64) NOT NULL UNIQUE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    status VARCHAR(40) NOT NULL DEFAULT 'queued',
    progress INTEGER NOT NULL DEFAULT 0,
    message VARCHAR(255),
    executor_name VARCHAR(40) NOT NULL DEFAULT 'thread',
    task_id VARCHAR(255),
    request_payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    result_payload_json JSONB,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_character_extraction_job_status_allowed
        CHECK (status IN ('queued', 'running', 'completed', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_character_extraction_jobs_project_id
    ON character_extraction_jobs(project_id);
CREATE INDEX IF NOT EXISTS idx_character_extraction_jobs_project_status
    ON character_extraction_jobs(project_id, status);
CREATE INDEX IF NOT EXISTS idx_character_extraction_jobs_task_id
    ON character_extraction_jobs(task_id);
