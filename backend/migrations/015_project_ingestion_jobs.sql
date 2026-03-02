CREATE TABLE IF NOT EXISTS project_ingestion_jobs (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(64) NOT NULL UNIQUE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    source VARCHAR(40) NOT NULL,
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
    CONSTRAINT ck_project_ingestion_job_source_allowed
        CHECK (source IN ('txt', 'markdown', 'epub', 'chapters-dir', 'append-chapter')),
    CONSTRAINT ck_project_ingestion_job_status_allowed
        CHECK (status IN ('queued', 'running', 'completed', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_project_ingestion_jobs_project_id
    ON project_ingestion_jobs(project_id);
CREATE INDEX IF NOT EXISTS idx_project_ingestion_jobs_project_status
    ON project_ingestion_jobs(project_id, status);
CREATE INDEX IF NOT EXISTS idx_project_ingestion_jobs_task_id
    ON project_ingestion_jobs(task_id);

CREATE TABLE IF NOT EXISTS project_ingestion_job_files (
    id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES project_ingestion_jobs(id) ON DELETE CASCADE,
    file_index INTEGER NOT NULL,
    filename VARCHAR(255) NOT NULL,
    content_type VARCHAR(255),
    payload_blob BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_project_ingestion_job_file_order UNIQUE (job_id, file_index)
);

CREATE INDEX IF NOT EXISTS idx_project_ingestion_job_files_job_id
    ON project_ingestion_job_files(job_id);
