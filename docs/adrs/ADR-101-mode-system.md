# ADR-101: Mode System Uses Profile Defaults with Project and Run Snapshots

Reference sources:
- [SRS.md](/Users/elhamdev/work/nipe/SRS.md) section `## 3. System Modes & Mode Selection`

## Status

accepted

## Context

- NIPE must support multiple workflows (audiobook, academic, author, custom) without requiring corpus re-upload.
- Project-level mode selection and run-level configuration both need explicit persistence for reproducibility.
- Mode switches must not silently mutate historical run behavior.

## Decision

- Keep canonical mode enum and default mode in backend shared mode constants.
- Persist project-level selection independently from run-level snapshots.
- Build run config from mode profile defaults plus explicit run overrides.
- Persist immutable mode profile snapshots on each run to preserve replayability.

## Consequences

- Historical runs remain stable after later project mode changes.
- Adding a new mode requires synchronized updates to mode catalog, profile defaults, schema validation, and UI mode selection.
- Run exports and diagnostics can reason about mode context without querying mutable project state.

## Backend Impact

- `backend/app/modes.py`
- `backend/app/services/mode_profiles.py`
- `backend/app/main.py` mode + run endpoints

## Frontend Impact

- Route-driven mode selection flow at `/projects/:project_id/mode`
- Run creation payload builders that pass selected mode and resolved profile-driven settings
- Mode-aware pipeline setup defaults shown before run submission

