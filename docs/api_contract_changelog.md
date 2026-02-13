# API Contract Changelog

This changelog is maintained for frontend maintainers to track backend/API contract changes and required UI/schema follow-through.

## API Contract Changelog (Frontend Maintainers)

| Change ID | Date | Backend/API change | Frontend impact | Source artifact | Status |
| --- | --- | --- | --- | --- | --- |
| API-001 | 2026-02-20 | `GET /api/modes` now exposes `mode_profiles.*.export_formats` in the mode catalog payload. | Update mode-catalog schema and mode-selection defaults to consume `export_formats`. | `backend/tests/test_modes_endpoint.py` | implemented |
| API-002 | 2026-02-20 | `POST /api/projects/{project_id}/runs` accepts run-level `export_formats` allow-list. | Include selected `export_formats` in pipeline setup run payload and validate request schema support. | `frontend/tests/unit/run-request-schema.unit.test.ts` | implemented |
| API-003 | 2026-02-20 | Academic export endpoints now enforce run-level export format gates (`json`, `csv`, `time_series_json`, `graph_json`). | Handle blocked export requests in UI and only show available download options from manifest inventory. | `backend/tests/test_export_manifest.py` | implemented |
| API-004 | 2026-02-21 | Run detail payload persists mode profile snapshots with export format defaults in `config.mode_profile_snapshot`. | Keep run-detail schema guards compatible with persisted snapshot shape and display effective export formats. | `frontend/tests/unit/run-detail-schema.unit.test.ts` | implemented |
| API-005 | 2026-02-22 | Live backend endpoint contract suite expanded to include mode/profile and export gate assertions. | Ensure frontend e2e contract tests continue to run against live backend for regression visibility. | `frontend/tests/e2e/backend-endpoint-contract.e2e.spec.ts` | implemented |
| API-006 | 2026-02-26 | One-command local smoke script standardizes backend + frontend contract verification for API-affecting changes. | Use smoke command output as acceptance evidence in PR notes when backend/API contract behavior changes. | `backend/scripts_run_local_smoke.py` | implemented |
| API-007 | 2026-02-26 | Added `GET /api/projects/{project_id}/actions` to return lifecycle-gated allowed actions (`ingest`, `select_mode`, `configure`, `run`, `rerun`, `export`, `archive`, `restore`). | Use allowed actions payload to gate project-detail/dashboard CTA availability and avoid calling disallowed workflows from UI state. | `backend/tests/test_project_allowed_actions_endpoint.py` | implemented |
| API-008 | 2026-02-26 | Added `POST /api/projects/{project_id}/runs/{run_id}/rerun` to clone source run configuration snapshot into a new run and persist lineage metadata (`rerun_source_*`). | Add rerun CTA wiring to call the endpoint and surface rerun lineage details in run history/detail views. | `backend/tests/test_run_rerun_endpoint.py` | implemented |
