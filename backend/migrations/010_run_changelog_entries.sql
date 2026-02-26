CREATE TABLE IF NOT EXISTS run_changelog_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    event_type VARCHAR(80) NOT NULL,
    event_message TEXT,
    event_metadata JSON NOT NULL DEFAULT ('{}'),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_run_changelog_entries_run_id
    ON run_changelog_entries (run_id);

CREATE INDEX IF NOT EXISTS ix_run_changelog_entries_created_at
    ON run_changelog_entries (created_at);
