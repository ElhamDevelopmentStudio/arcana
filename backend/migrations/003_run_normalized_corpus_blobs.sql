CREATE TABLE IF NOT EXISTS run_normalized_corpus_blobs (
    id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL UNIQUE REFERENCES runs(id) ON DELETE CASCADE,
    source VARCHAR(80) NOT NULL,
    source_filename VARCHAR(255),
    corpus_sha256 CHAR(64) NOT NULL,
    normalized_corpus_blob BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
