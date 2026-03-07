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
| API-009 | 2026-02-26 | Added `GET /api/projects/{project_id}/timeline` to return project activity timeline events (paginated, reverse chronological) for detail views. | Use timeline payload to render project activity history UI with pagination and event metadata drill-down. | `backend/tests/test_project_activity_timeline_endpoint.py` | implemented |
| API-010 | 2026-02-27 | Added `GET /api/projects/{project_id}` to return a dashboard-ready project detail payload (`lifecycle_state`, `next_required_action`, `allowed_actions`, mode/config metadata, timestamps). | Replace multi-call project header hydration with one detail request and use returned `allowed_actions` for local CTA gating. | `backend/tests/test_project_detail_endpoint.py` | implemented |
| API-011 | 2026-02-27 | Added `POST /api/projects/{project_id}/archive` and `POST /api/projects/{project_id}/restore` with lifecycle-state-change payloads for project management actions. | Wire archive/restore controls to dedicated endpoints and refresh list/detail views from returned state/action payloads. | `backend/tests/test_project_archive_restore_endpoints.py` | implemented |
| API-012 | 2026-02-27 | Added `GET /api/projects/{project_id}/setup-status` (`CP-007`) returning per-step setup readiness (`steps[]`) and aggregate `is_complete`. | Use setup-status as the source of truth for project setup gate routing, step checklist UI, and locked route redirects. | `backend/tests/test_project_setup_status_endpoint.py` | implemented |
| API-013 | 2026-02-27 | Added `GET /api/projects/{project_id}/workspace-summary` (`CP-008`) returning project-shell counters/readiness context (`chapters_count`, `characters_count`, `voice_mappings_count`, run counters). | Hydrate project workspace sidebar badges and overview cards from one summary call instead of stitching multiple endpoint reads. | `backend/tests/test_project_workspace_summary_endpoint.py` | implemented |
| API-014 | 2026-02-27 | Extended `GET /api/projects/{project_id}/actions` with optional gating metadata: `blocked_reason` and `required_step`. | Show actionable lock/guard messaging and route users directly to required setup step from blocked actions. | `backend/tests/test_action_gating_rerun_permissions_regression.py` | implemented |
| API-015 | 2026-03-01 | Character extraction now persists reviewable proposals and adds proposal-review APIs: `GET /api/projects/{project_id}/characters/proposals`, `POST /api/projects/{project_id}/characters/proposals/review`; `POST /api/projects/{project_id}/characters/extract` accepts optional extraction config, returns `extraction_batch_id`/`proposal_count`, and now auto-applies strong candidates into canonical `/characters` by default (`auto_applied_count`). | Add proposal queue query/mutation hooks, review actions in characters workflow, and updated extraction request/response schemas (including `auto_apply_to_character_map` and `auto_apply_min_confidence`). | `backend/tests/test_character_auto_extraction.py`, `backend/tests/test_character_extraction_v2.py` | implemented |
| API-016 | 2026-03-01 | Added async character extraction job endpoints: `POST /api/projects/{project_id}/characters/extract/jobs` and `GET /api/projects/{project_id}/characters/extract/jobs/{job_id}`. Jobs persist progress/status/result (`queued|running|completed|failed`) and execute via Celery when configured, with thread fallback. | Switch characters page extraction action to start-job + polling flow; add job start/status schemas and polling hook integration while preserving legacy sync `POST /characters/extract`. | `backend/tests/test_character_auto_extraction.py` | implemented |
| API-017 | 2026-03-01 | Added async project ingestion job endpoints: `POST /api/projects/{project_id}/ingest/jobs` and `GET /api/projects/{project_id}/ingest/jobs/{job_id}`. Jobs persist uploaded file payloads, progress/status/result (`queued|running|completed|failed`), and execute via Celery when configured with thread fallback. | Switch project ingestion UI flows to start-job + polling (project wizard and setup page) so large uploads no longer rely on one long request timeout; add ingestion job start/status schemas, hooks, and API client methods. | `backend/tests/test_project_ingestion_jobs.py` | implemented |
| API-018 | 2026-03-02 | Added async execution mode for pipeline run orchestration via `async=true` query parameter on existing endpoints: `POST /api/projects/{project_id}/runs`, `POST /api/projects/{project_id}/runs/{run_id}/rerun`, and `POST /api/projects/{project_id}/runs/{run_id}/recover`. Async dispatch now routes through Celery (`pipeline.execute_run`) when configured, with thread fallback. | Frontend run actions now call async mode by default and rely on run-status polling; global notification center tracks ingestion/extraction/pipeline jobs with per-job status and deep links. | `backend/tests/test_pipeline_async_runs.py` | implemented |

## Response examples (setup/workspace/action gating)

### `GET /api/projects/{project_id}/setup-status`

```json
{
  "schema_version": "1.0.0",
  "output_schema": "project_setup_status_json",
  "output_format": "json",
  "output_id": "CP-007",
  "output_name": "project_setup_status",
  "generated_at": "2026-02-27T21:55:30.000000+00:00",
  "generated_by": "build_project_setup_status",
  "project_id": 42,
  "lifecycle_state": "ingested",
  "next_required_action": "run",
  "is_complete": false,
  "steps": [
    { "step_id": "ingestion", "label": "Ingestion", "ready": true, "required": true },
    { "step_id": "mode_selection", "label": "Mode Selection", "ready": true, "required": true },
    { "step_id": "initial_run", "label": "Initial Run", "ready": false, "required": true },
    { "step_id": "character_mapping", "label": "Character Mapping", "ready": false, "required": false },
    { "step_id": "voice_mapping", "label": "Voice Mapping", "ready": false, "required": false }
  ]
}
```

### `GET /api/projects/{project_id}/workspace-summary`

```json
{
  "schema_version": "1.0.0",
  "output_schema": "project_workspace_summary_json",
  "output_format": "json",
  "output_id": "CP-008",
  "output_name": "project_workspace_summary",
  "generated_at": "2026-02-27T21:56:05.000000+00:00",
  "generated_by": "build_project_workspace_summary",
  "project_id": 42,
  "lifecycle_state": "completed",
  "last_run_status": "completed",
  "next_required_action": "export",
  "is_setup_complete": true,
  "chapters_count": 20,
  "characters_count": 18,
  "voice_mappings_count": 18,
  "runs_total_count": 2,
  "runs_completed_count": 1,
  "runs_failed_count": 1,
  "last_export_at": "2026-02-27T21:40:00.000000+00:00"
}
```

### `GET /api/projects/{project_id}/actions`

```json
{
  "schema_version": "1.0.0",
  "output_schema": "project_allowed_actions_json",
  "output_format": "json",
  "output_id": "CP-003",
  "output_name": "project_allowed_actions",
  "generated_at": "2026-02-27T21:56:40.000000+00:00",
  "generated_by": "build_project_allowed_actions",
  "project_id": 42,
  "lifecycle_state": "draft",
  "last_run_status": null,
  "next_required_action": "ingest",
  "allowed_actions": ["ingest", "select_mode", "configure", "archive"],
  "blocked_reason": "Source ingestion is required before setup and run actions are available.",
  "required_step": "ingestion"
}
```

### `GET /api/projects/{project_id}/characters/proposals`

```json
{
  "project_id": 42,
  "proposal_count": 2,
  "proposals": [
    {
      "id": 901,
      "name": "Sunny",
      "verbalized_form": "Sunny",
      "gender": "unknown",
      "aliases": [],
      "notes": null,
      "source": "auto",
      "confidence": 0.81,
      "source_trace": [
        {
          "kind": "dialogue_attribution",
          "chapter_index": 3,
          "span_start": 180,
          "span_end": 186,
          "excerpt": "...\"Watch out,\" Sunny said...",
          "weight": 1.0
        }
      ],
      "inferred_gender": "unknown",
      "inferred_confidence": 0.0,
      "inferred_source_trace": [],
      "status": "proposed",
      "extractor_version": "v2",
      "extraction_batch_id": "d8a54b3404f5426f8f3f99d9877546f7",
      "reviewed_at": null,
      "reviewed_by": null,
      "created_at": "2026-03-01T17:00:11.000000+00:00",
      "updated_at": "2026-03-01T17:00:11.000000+00:00"
    }
  ]
}
```

### `POST /api/projects/{project_id}/characters/proposals/review`

Request:

```json
{
  "approve_ids": [901],
  "reject_ids": [902],
  "reviewed_by": "editor@local"
}
```

Response:

```json
{
  "project_id": 42,
  "approved_count": 1,
  "rejected_count": 1,
  "character_map_finalized": false,
  "characters": [
    {
      "name": "Sunny",
      "verbalized_form": "Sunny",
      "gender": "unknown",
      "aliases": [],
      "notes": null,
      "source": "auto",
      "confidence": 0.81,
      "source_trace": []
    }
  ],
  "proposal_count": 0,
  "proposals": []
}
```
