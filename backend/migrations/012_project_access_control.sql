CREATE TABLE IF NOT EXISTS project_accesses (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    principal_type VARCHAR(40) NOT NULL DEFAULT 'user',
    principal_id VARCHAR(255) NOT NULL,
    role VARCHAR(40) NOT NULL DEFAULT 'viewer',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_project_access_principal UNIQUE (project_id, principal_type, principal_id),
    CONSTRAINT ck_project_access_role CHECK (role IN ('owner', 'editor', 'viewer')),
    CONSTRAINT ck_project_access_principal_type CHECK (principal_type IN ('user', 'service', 'system'))
);

CREATE INDEX IF NOT EXISTS idx_project_access_project_id ON project_accesses(project_id);
CREATE INDEX IF NOT EXISTS idx_project_access_principal_lookup ON project_accesses(principal_type, principal_id);
