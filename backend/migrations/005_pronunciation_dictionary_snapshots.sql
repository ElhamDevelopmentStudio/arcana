CREATE TABLE IF NOT EXISTS pronunciation_dictionary_snapshots (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    run_id INTEGER REFERENCES runs(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    source VARCHAR(80) NOT NULL,
    snapshot_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_project_pronunciation_dictionary_snapshot_version UNIQUE (project_id, version)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_pronunciation_dictionary_snapshots_run
    ON pronunciation_dictionary_snapshots(run_id)
    WHERE run_id IS NOT NULL;
