# System Modes Contract

Reference sources:
- [SRS.md](/Users/elhamdev/work/nipe/SRS.md) section `## 3. System Modes & Mode Selection`
- [SRS_Expanded_Implementation_Checklist.md](/Users/elhamdev/work/nipe/SRS_Expanded_Implementation_Checklist.md) item `MODE-001`

Purpose:
- Define the canonical mode enum contract used by run configuration and validation.
- Keep mode naming and default behavior stable before mode-expansion tasks (`MODE-002+`).
- Define mode-profile defaults that downstream run config loading can consume (`MODE-006` baseline).

## MODE-001 System Mode Enum Contract

- allowed_modes: audiobook, academic, author, custom
- default_mode: audiobook
- project_mode_path: projects.selected_mode
- run_config_path: runs.config_json.mode
- notes: mode enum values are lower-case and persisted at project level with per-run config snapshots.

## MODE-006 Default Mode Profiles

- catalog_path: /api/modes -> `mode_profiles`
- profile_fields: `max_segment_chars`, `llm_enabled`, `provider_name`, `max_calls_per_day`, `profile_intent`
- guaranteed_profile_modes: audiobook, academic, author, custom

## MODE-007 Backend Mode Profile Loader

- service_path: `backend/app/services/mode_profiles.py`
- loader_functions:
  - `normalize_mode_value(mode)` -> resolves blank/none to default mode and validates enum values.
  - `load_mode_profile(mode)` -> returns a deep-copied profile for safe per-request usage.
  - `load_mode_profile_catalog()` -> returns a full mode->profile map built via loader function.
- integration_note: `/api/modes` now loads `mode_profiles` through the service loader to avoid direct mutable constant exposure.

## MODE-008 Mode Profile Snapshot In Run Config

- runtime_entrypoint: `POST /api/projects/{project_id}/runs`
- loader_usage: run creation builds config via `build_run_config_snapshot(mode, overrides)`.
- stored_fields:
  - `mode`
  - effective runtime fields (`max_segment_chars`, `llm_enabled`, `provider_name`, `max_calls_per_day`)
  - `mode_profile_snapshot` (immutable copy of defaults for selected mode at run creation time)
- override_rule: user-supplied run fields override effective runtime values, but do not mutate `mode_profile_snapshot`.

## MODE-009 Project Mode Switching Endpoint

- endpoint: `PUT /api/projects/{project_id}/mode`
- request: `{ "mode": "audiobook|academic|author|custom" }`
- response: `project_id`, `previous_mode`, `selected_mode`, `chapter_count`, `reused_ingested_corpus`
- behavior:
  - updates only `projects.selected_mode`
  - does not re-ingest or alter stored chapters
  - reports whether existing ingested corpus is being reused (`chapter_count > 0`)

## MODE-010 Raw Text Duplication Guard (Mode Switch)

- guarantee: switching modes does not create new chapter/raw-text rows.
- verification: repeated mode switches preserve chapter row IDs and raw-text content snapshots for the project.
- implementation_scope: no write-path to `chapters` table inside mode switch endpoint.
