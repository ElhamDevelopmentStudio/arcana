CREATE TABLE IF NOT EXISTS run_configuration_snapshots (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE UNIQUE,
    version INTEGER NOT NULL,
    source VARCHAR(80) NOT NULL,
    snapshot_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_project_run_configuration_snapshot_version UNIQUE (project_id, version)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_run_configuration_snapshots_run
    ON run_configuration_snapshots(run_id);
