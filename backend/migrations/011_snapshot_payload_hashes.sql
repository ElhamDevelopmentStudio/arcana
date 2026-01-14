ALTER TABLE character_map_snapshots
    ADD COLUMN snapshot_json_sha256 VARCHAR(64) NOT NULL DEFAULT '';

ALTER TABLE run_configuration_snapshots
    ADD COLUMN snapshot_json_sha256 VARCHAR(64) NOT NULL DEFAULT '';

ALTER TABLE pronunciation_dictionary_snapshots
    ADD COLUMN snapshot_json_sha256 VARCHAR(64) NOT NULL DEFAULT '';

ALTER TABLE voice_map_snapshots
    ADD COLUMN snapshot_json_sha256 VARCHAR(64) NOT NULL DEFAULT '';

ALTER TABLE time_series_snapshots
    ADD COLUMN snapshot_json_sha256 VARCHAR(64) NOT NULL DEFAULT '';
