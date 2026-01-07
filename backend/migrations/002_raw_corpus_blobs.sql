CREATE TABLE IF NOT EXISTS project_raw_corpus_blobs (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    source VARCHAR(80) NOT NULL,
    source_filename VARCHAR(255),
    blob_sha256 CHAR(64) NOT NULL,
    raw_corpus_blob BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
