# System Modes Contract

Reference sources:
- [SRS.md](/Users/elhamdev/work/nipe/SRS.md) section `## 3. System Modes & Mode Selection`
- [SRS_Expanded_Implementation_Checklist.md](/Users/elhamdev/work/nipe/SRS_Expanded_Implementation_Checklist.md) item `MODE-001`

Purpose:
- Define the canonical mode enum contract used by run configuration and validation.
- Keep mode naming and default behavior stable before mode-expansion tasks (`MODE-002+`).

## MODE-001 System Mode Enum Contract

- allowed_modes: audiobook, academic, author, custom
- default_mode: audiobook
- project_mode_path: projects.selected_mode
- run_config_path: runs.config_json.mode
- notes: mode enum values are lower-case and persisted at project level with per-run config snapshots.
