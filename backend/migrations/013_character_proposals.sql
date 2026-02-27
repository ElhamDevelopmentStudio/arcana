CREATE TABLE IF NOT EXISTS character_proposals (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    normalized_name VARCHAR(255) NOT NULL,
    verbalized_form VARCHAR(255) NOT NULL,
    aliases JSONB NOT NULL DEFAULT '[]'::jsonb,
    notes TEXT,
    source VARCHAR(120) NOT NULL DEFAULT 'auto',
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    source_trace JSONB NOT NULL DEFAULT '[]'::jsonb,
    inferred_gender VARCHAR(50) NOT NULL DEFAULT 'unknown',
    inferred_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    inferred_source_trace JSONB NOT NULL DEFAULT '[]'::jsonb,
    status VARCHAR(40) NOT NULL DEFAULT 'proposed',
    extractor_version VARCHAR(80) NOT NULL DEFAULT 'v2',
    extraction_batch_id VARCHAR(64) NOT NULL,
    reviewed_at TIMESTAMPTZ,
    reviewed_by VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_character_proposal_status_allowed CHECK (status IN ('proposed', 'approved', 'rejected'))
);

CREATE INDEX IF NOT EXISTS idx_character_proposals_project_id
    ON character_proposals(project_id);
CREATE INDEX IF NOT EXISTS idx_character_proposals_project_status
    ON character_proposals(project_id, status);
CREATE INDEX IF NOT EXISTS idx_character_proposals_project_normalized_name
    ON character_proposals(project_id, normalized_name);
CREATE INDEX IF NOT EXISTS idx_character_proposals_project_batch
    ON character_proposals(project_id, extraction_batch_id);
