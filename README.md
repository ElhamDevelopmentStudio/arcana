# NIPE

Narrative Intelligence & Performance Engine (NIPE) for long-form fiction processing.

Primary spec documents:
- [PoC.md](/Users/elhamdev/work/nipe/PoC.md): currently implemented baseline scope.
- [SRS.md](/Users/elhamdev/work/nipe/SRS.md): full product requirements.
- [SRS_Expanded_Implementation_Checklist.md](/Users/elhamdev/work/nipe/SRS_Expanded_Implementation_Checklist.md): granular execution checklist for full SRS delivery.

## Current Status

Current codebase implements the PoC vertical slice from `PoC.md`:
- TXT ingestion and chapter detection
- Basic normalization
- Character map import (JSON/CSV)
- Pronunciation substitution
- Segmentation for TTS
- Basic tagging + speaker heuristic
- Voice resolution
- JSON export
- Project-level mode persistence (`projects.selected_mode`) with per-run mode snapshots
- Run status lifecycle baseline (`queued` -> `running` -> terminal `completed|failed|cancelled`)
- Project-level access-control model scaffold (`project_accesses`) with grant endpoints
- Mode catalog endpoint for UI mode selection bootstrap (`GET /api/modes`)
- Minimal LLM router scaffold + quota tracking
- React UI with route-based structure (`router/main.tsx`, `router/auth.tsx`, `router/index.tsx`)
- Global Tailwind-based design system in `frontend/src/styles/globals.css`
- Frontend API/state foundations using Axios + SWR + Zustand + Zod + date-fns
- Frontend test stack with centralized Vitest + Playwright suites (unit, integration, regression, e2e, visual)

## Repository Layout

- `backend/`: FastAPI app, pipeline services, DB models, tests, migrations
  - `backend/app/glossary_terms.py`: shared glossary constants/types synced to `SRS.md §0`
  - `backend/app/modes.py`: shared mode enum values and persistence-path constants
- `frontend/`: React + Vite client
- `PoC.md`: proof-of-concept requirements
- `SRS.md`: full requirements specification
- `SRS_Expanded_Implementation_Checklist.md`: detailed implementation backlog
- `docs/glossary.md`: canonical glossary synced to `SRS.md §0`
- `docs/api_domain_terms.md`: API-facing definitions/examples for key domain terms
- `docs/scope.md`: implementation scope baseline (`SRS.md §1.2` SHALL/SHALL NOT)
- `docs/non_goals.md`: explicit non-goals list and scope-guardrail rules
- `docs/shadow_slave_success_checklist.md`: Shadow Slave end-to-end success criteria checklist (`SRS.md §1.3`)
- `docs/architecture.md`: architecture baseline including deterministic reproducibility objective
- `docs/acceptance_kpis.md`: acceptance KPI definitions aligned to SRS success criteria
- `docs/final_acceptance_report_template.md`: final release acceptance report template with pass/fail per criterion
- `docs/migration_framework.md`: migration framework baseline and required SQL migration naming convention
- `docs/adrs/`: architecture decision records for mode system, tagging, and LLM router
- `docs/persona_end_to_end_flows.md`: one end-to-end flow per SRS persona
- `docs/system_modes.md`: canonical MODE-001 enum contract for SRS section 3 mode values
- `docs/audiobook_ui_api_mapping.md`: USE-002 mapping from audiobook UI steps to concrete API endpoints
- `docs/academic_outputs_export_mapping.md`: USE-003 mapping from academic flow to outputs and export formats
- `docs/author_diagnostic_requirements_mapping.md`: USE-004 mapping from author flow to diagnostic report requirements
- `docs/community_reader_readonly_dashboard_flow.md`: USE-005 read-only dashboard flow for community reader
- `docs/contributor_add_tag_type.md`: contributor guide for adding a new tag type safely
- `docs/contributor_add_llm_provider_adapter.md`: contributor guide for adding a new LLM provider adapter safely
- `docs/contributor_evolve_export_schema_safely.md`: contributor guide for evolving export schema safely
- `docs/release_migration_backward_compatibility_checklist.md`: release checklist for migrations and backward compatibility
- `docs/release_rollback_plan_template.md`: rollback plan template for failed release response
- `docs/release_security_review_checklist.md`: release security review checklist template
- `docs/reference_feature_overlap.md`: overlap map to the external read-only reference project
- `docs/error_warning_catalog.md`: error and warning catalog with remediation guidance
- `AGENTS.md`: repository execution rules for small-task delivery and testing discipline
- `sample_character_map_shadow_slave.json`: sample character map import file
- `shadow_slave_chapter_1_to_95.txt`: sample source text corpus
- `novels_extra_chapter_0_to_22.txt`: additional large-corpus fixture reserved for deferred slow regression/traceability suites
- `seed_fixtures/quick_onboarding/`: starter seed fixtures (minimal novel, characters, run payload) for local onboarding

## Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL running locally

Default local database DSN:

`postgresql+psycopg://postgres@localhost:5432/nipe_poc`

Create DB if needed:

```bash
createdb -U postgres nipe_poc
```

## Quick Start

### Backend

```bash
cd backend
/opt/homebrew/bin/python3.11 -m venv .venv311
source .venv311/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

### Local smoke test (one command)

From repository root:

```bash
python3 backend/scripts_run_local_smoke.py
```

Default behavior:
- Starts a temporary backend instance on `127.0.0.1:8010` using local SQLite (`test_nipe_local_smoke.db`).
- Runs backend smoke API test (`backend/tests/test_api_smoke.py`).
- Runs a stable frontend Playwright live-backend contract smoke (`frontend/tests/e2e/backend-endpoint-contract.e2e.spec.ts`, `--grep` contract baseline case).

### LLM provider keys and failover behavior

Set provider credentials in `backend/.env` (copied from `.env.example`) before running LLM-dependent features.

- OpenRouter:
  - `OPENROUTER_API_KEY`
  - `OPENROUTER_API_KEYS`
- SiliconFlow:
  - `SILICONFLOW_API_KEY`
  - `SILICONFLOW_API_KEYS`
- Groq:
  - `GROQ_API_KEY`
  - `GROQ_API_KEYS`

Multi-key formats:
- Comma-separated: `OPENROUTER_API_KEYS=key_a,key_b,key_c`
- JSON-style array: `OPENROUTER_API_KEYS=["key_a","key_b","key_c"]`
- Provider priority order also accepts either format:
  - `LLM_PROVIDER_PRIORITY_ORDER=openrouter,siliconflow,groq`
  - `LLM_PROVIDER_PRIORITY_ORDER=["openrouter","siliconflow","groq"]`

Parsing behavior:
- If `*_API_KEYS` is present and non-empty, it is used as the ordered key list.
- If no multi-key value is provided, the single-key variable `*_API_KEY` is used as a fallback.
- Keys are tried in listed order.

Failover order:
- The requested provider is tried first.
- Within that provider, all available keys are consumed in order.
- If all keys are rate-limited/quota-exhausted for that provider, the system marks provider as temporarily unavailable and tries the next provider in `LLM_PROVIDER_PRIORITY_ORDER` (default: `openrouter,siliconflow,groq`).
- The provider that returned success is recorded for that probe run.
- Every concrete key/API attempt is also persisted in `provider_api_key_usage_audit` with redacted key data:
  - `provider_api_key_masked` stores a masked suffix (example: `••••ey-a` for `openrouter-key-a`).
  - `provider_api_key_fingerprint` stores a SHA-256 fingerprint of the key (not the key itself).
  - `attempt_index`, `error_code`, `success`, and `called_at` are recorded for each attempt.
- Cached probe responses do not create key-usage audit rows because no outbound call is made.
- If the requested provider is manually disabled, the run returns `provider_disabled` for that request without fallback.

Manual provider toggles are supported and tracked via provider availability rules already configured in the backend.

### Per-project provider configuration

Projects now support per-provider runtime overrides via:

- `PUT /api/projects/{project_id}/llm`
- Response/request body field `provider_config`

`provider_config` supports an object map keyed by provider name (case-insensitive). Supported keys for each provider:

- `base_url` – overrides provider base URL for runs
- `model` – overrides provider default model id for runs
- `api_key` – single fallback key for that provider
- `api_keys` – preferred ordered list (comma-separated string or array) for per-provider failover

Format examples:

- JSON object key-per-provider:

```json
{
  "openrouter": {
    "base_url": "https://api.openrouter.ai/v1",
    "model": "openai/gpt-4o-mini",
    "api_keys": ["or-key-a", "or-key-b"]
  },
  "groq": {
    "base_url": "https://api.groq.com/openai/v1",
    "model": "llama-3.3-70b-versatile",
    "api_key": "groq-key"
  }
}
```

Behavior and precedence:

- Project-level `provider_config` is included in each run config snapshot.
- `provider_api_keys` in a run payload (if present) overrides any configured key list for that provider.
- Run-time routing still follows global provider priority and failover behavior.
- The provider field values are normalized/trimmed and empty entries are dropped before storage.

### LLM cache invalidation policy

### Project access control model (SaaS groundwork)

Project grants are now persisted in `project_accesses` with strict role and principal typing to support future per-project security enforcement:

- `GET /api/projects/{project_id}/access` → list active grants
- `POST /api/projects/{project_id}/access` → add or update principal access

Request schema:

- `principal_id` (string, required)
- `principal_type` (one of `user|service|system`, defaults to `user`)
- `role` (one of `owner|editor|viewer`, defaults to `viewer`)

This establishes the data model for `NFR5-001` and enables `NFR5-002` (project isolation checks) to be layered without changing project semantics later.

Project-scoped access checks can be enforced per request using optional headers:

- `X-Principal-Type` (`user|service|system`)
- `X-Principal-Id` (opaque string principal key)

When both headers are present, routes under `/api/projects/{project_id}/...` enforce:

- minimum `viewer` role for read-style requests (GET/HEAD/OPTIONS)
- minimum `editor` role for write-style requests (POST/PUT/PATCH/DELETE)
- additional principal-type scope checks:
  - `service` principals: `viewer` grants read-only access; `editor`/`owner` adds run execution (`POST /api/projects/{project_id}/runs` and `/runs/{run_id}/recover`) but not data mutation.
  - `system` principals: only read access for all roles.
- these checks are enforced at request time in middleware before endpoint handlers run.

If a principal is not granted for the required role on the project, the response is `403 Forbidden`.
If either header is missing or invalid, the response is `400 Bad Request`.

### SaaS data-at-rest encryption for uploaded text (`NFR5-003`)

Uploaded text is encrypted at rest when SaaS mode is enabled.

Environment variables:

- `SAAS_MODE=true|false` (default: `false`)
- `DATA_ENCRYPTION_KEY=<secret>`

When `SAAS_MODE=true`, the backend stores these persisted text fields encrypted:

- `chapters.raw_text`
- `chapters.original_text_snapshot`
- `chapters.normalized_text`
- `chapters.normalized_text_snapshot`
- `project_raw_corpus_blobs.raw_corpus_blob`

Behavior:

- writes automatically encrypt at bind time;
- reads decrypt automatically when surfaced through SQLAlchemy models;
- integrity checks and run-time processing still operate on the decrypted application value.
- if `DATA_ENCRYPTION_KEY` is missing while `SAAS_MODE` is enabled, writes will fail with a runtime error.

### Derived-metrics-only persistence mode (`NFR6-004`)

Projects can opt into source-text minimization with:

- `POST /api/projects` body field `do_not_store_source_text: true`

In derived-metrics mode, the backend persists only derived outputs required for outputs and analytics:

- ✅ `ProjectRawCorpusBlob` is not stored
- ✅ `chapters.normalized_text` / `chapters.normalized_text_snapshot` are still stored
- ✅ `chapters.raw_text`, `chapters.original_text_snapshot`, and `chapters.original_to_normalized_offset_map` are intentionally left blank

Behavior notes:

- Appends and runs continue to work using derived chapter text.
- Re-imported source text from uploads is not retained.
- Integrity checks intentionally mark `project_raw_corpus_blobs` as passed with reason `do_not_store_source_text` for compliant projects.

LLM responses are cached in the `llm_cache` table and reused only when all cache-key dimensions match exactly:

- hashed input text (`_build_llm_cache_key`)
- task type (`emotion_refinement`, `speaker_resolution`, etc.)
- configuration snapshot ID
- model identifier

Current invalidation policy:

- No API-level or automatic TTL-based eviction is currently implemented.
- There is no "manual clear-cache" endpoint in the public API yet.
- Entries become naturally stale when any key dimension changes (new project snapshot, different task type, or different model).
- Exact-match behavior is strict: near-miss inputs or punctuation-only differences must be treated as separate keys and are not reused.
- Run detail responses expose per-task `llm_cache_metrics` counters (`hits` / `misses`) and per-call `is_cache_hit` flags.

Deterministic run model pinning:

- `POST /api/projects/{project_id}/runs` accepts `deterministic_model_identifier` when `deterministic_mode` is enabled.
- If deterministic mode is enabled and no value is provided, the backend resolves and stores the current provider model in
  `config.deterministic_model_identifier` for that run.
- If a value is provided, it is pinned in that run config and used for primary provider requests during that run.
- The pinned model value is included in `run.config` and in LLM call logs (`model_identifier`).
- `frontend/src/pages/projects/project-pipeline-setup-page.tsx` now exposes deterministic controls for:
  - deterministic mode toggle
  - deterministic model identifier (optional pin)
  - deterministic seed
  - randomization strategy and shuffle flag (sent in `randomization_config`)

Run request segmentation target length config:

- `POST /api/projects/{project_id}/runs` accepts:
  - `max_segment_chars` (primary run config key)
  - `segmentation_target_length` (alias for the same value)
- If omitted, `max_segment_chars` defaults to `255` or the selected mode profile default.
- Accepted range is `80` to `255`, and the resolved value is persisted as `max_segment_chars`
  inside run configuration.

Run request emotion taxonomy config:

- `POST /api/projects/{project_id}/runs` accepts `emotion_taxonomy` for tagging behavior.
- Allowed values are `basic` (default) and `expanded`.
- The value is persisted on the run as `run.config.emotion_taxonomy`.
- `basic` keeps broad primary labels (`positive` / `negative` / `neutral`) and uses secondary labels as a refinement.
- `expanded` enables richer emotion buckets via expanded secondary-label heuristics and maps the primary label accordingly.
- Run snapshots (`run_configuration_snapshot`) include `emotion_taxonomy`.
- If the value is omitted, backend parsing stores `"basic"` and front-end schema sets this default.

Run request internal-thought voice policy config:

- `POST /api/projects/{project_id}/runs` accepts:
  - `internal_thought_voice_policy` (`character` | `narrator` | `thought_voice`)
  - `internal_thought_voice` (optional custom fallback voice id)
- Defaults are sourced from project voice defaults and resolve to `character` when omitted.
- `character`: internal thought segments follow the resolved dialogue-style speaker voice.
- `narrator`: internal thought segments use the narrator voice.
- `thought_voice`: internal thought segments use `internal_thought_voice` when provided, otherwise narrator voice.
- This policy is also persisted in `run.config` (and appears in run snapshots), and voice settings can be updated beforehand via `PUT /api/projects/{project_id}/voices`.
- `frontend/src/pages/projects/project-pipeline-setup-page.tsx` exposes this as:
  - Internal-thought policy selector.
  - Custom thought voice input (enabled only for `thought_voice` policy).
  - Live internal-thought preview row that mirrors effective resolution.

Run request warning-threshold config:

- `POST /api/projects/{project_id}/runs` accepts warning-signal thresholds:
  - `speaker_confidence_threshold` (float, `0.0` to `1.0`)
  - `high_ambiguity_dialogue_flag_threshold` (int, `1` to `20`)
  - `unstable_emotion_shift_transition_threshold` (int, `1` to `20`)
  - `unstable_emotion_shift_density_threshold` (float, `0.0` to `1.0`)
- These values are persisted in `run.config` and included in `run_configuration_snapshot`:
  - `speaker_confidence_threshold`
  - `high_ambiguity_dialogue_flag_threshold`
  - `unstable_emotion_shift_transition_threshold`
  - `unstable_emotion_shift_density_threshold`
- Defaults are sourced from backend mode profiles (also exposed via `GET /api/modes`) and mirrored in the pipeline setup frontend:
  - `speaker_confidence_threshold: 0.6`
  - `high_ambiguity_dialogue_flag_threshold: 2`
  - `unstable_emotion_shift_transition_threshold: 4`
  - `unstable_emotion_shift_density_threshold: 0.5`
- If a field is omitted by client, backend parsing applies default values and the frontend schema also defaults it to the same profile-safe values.
- `frontend/src/pages/projects/project-pipeline-setup-page.tsx` now renders explicit controls for each of the above so users can override per-run.

Run request web scraping toggle config:

- `POST /api/projects/{project_id}/runs` accepts `web_scraping_enabled` to control whether the pipeline may enrich content via external web source lookups.
- This value is sourced from mode profile defaults and also stored on a per-run basis in:
  - `run.config.web_scraping_enabled`
  - `run_configuration_snapshot.web_scraping_enabled`
- For this initial implementation, the default for all mode profiles is `false`, and the
  `GET /api/modes` payload exposes `web_scraping_enabled` on each `mode_profiles` entry for UI bootstrap.

Run config schema versioning + diff viewer:

- Every run now persists `config_schema_version` in `run.config` (currently `1.0.0`).
- Run configuration snapshots also include `config_schema_version`.
- `GET /api/projects/{project_id}/runs/config-diff?base_run_id=<id>&target_run_id=<id>` returns a normalized config diff for two runs in the same project:
  - `changed_fields` with `base_value` and `target_value`
  - `base_only_fields`
  - `target_only_fields`
- Runtime-only run metadata fields (for example snapshot pointer IDs/versions) are excluded from this diff output so comparisons focus on effective run configuration.
- `frontend/src/pages/projects/project-run-monitor-page.tsx` now includes a `Run Config Diff Viewer` panel to inspect these diffs by run ID.

Run config validation errors (field-level):

- Invalid run configuration payloads sent to `POST /api/projects/{project_id}/runs` now return:
  - `detail`: `"Run configuration validation failed."`
  - `field_errors`: array of `{ field, message, code }`
- Field paths are normalized (for example `export_formats.0`) so frontend and API consumers can render precise inline or summary validation feedback.

Run config preset import/export tooling:

- `GET /api/projects/{project_id}/runs/{run_id}/config-preset` exports a reusable run-preset payload:
  - `preset_schema_version`
  - `generated_at`
  - `run_config` (sanitized, reusable config keys only)
- Runtime-only snapshot pointers are excluded from exported presets.
- `frontend/src/pages/projects/project-pipeline-setup-page.tsx` now supports:
  - importing preset JSON files (raw run payload or object containing `run_config`)
  - exporting the current pipeline setup as a preset JSON file.
- `frontend/src/pages/projects/project-run-monitor-page.tsx` now supports exporting a preset from an existing run via backend contract.

Pipeline chunking for long corpora:

- `POST /api/projects/{project_id}/runs` accepts `pipeline_chunk_max_chars` in the request body.
- `pipeline_chunk_max_chars` must be an integer in `[1024, 2000000]`.
- If omitted, the backend defaults to `120000` characters.
- Pipeline segments are processed in chapter-order batches where each batch total normalized chapter size is capped by the resolved threshold.
- Run metadata includes `pipeline_chunking` with:
  - `enabled` (boolean)
  - `chunk_max_chars`
  - `chunk_count`
- Segment payloads include stable `chunk_index` and `chunk_count`.
- Segments are prepared per-chunk in parallel and then flushed in deterministic chapter/segment order to maintain stable ordering.
- Chunks group full chapters only; intra-chapter segmentation remains in segmenter stage.

Incremental recomputation for appended chapters:

- `POST /api/projects/{project_id}/runs` accepts `incremental_recompute` (boolean).
- When `incremental_recompute` is true, the pipeline:
  - requires the current run config to match the latest completed run config for the same project,
  - requires chapter content to be unchanged for all prior chapters,
  - requires the latest completed run to have a contiguous processed chapter prefix.
- If those conditions hold, previously computed outputs for unchanged chapters are copied forward:
  - existing `segments.segment_json` rows are duplicated into the new run,
  - existing `sub_segment_tags` rows are duplicated into the new run and remapped to the copied segment IDs.
- Only chapters appended after the reused prefix are rebuilt.
- The run config includes:
  - `incremental_recompute.enabled` (boolean),
  - `incremental_recompute.reused_chapter_count` (count of chapters preserved from the prior run).
- For this feature to engage, the latest completed run must include all prior chapters in a contiguous sequence starting at chapter `1`.

Run model metadata persistence:

- Every run now stores selected LLM metadata on the `runs` record:
  - `llm_provider_name`
  - `llm_model_identifier`
  - `llm_model_version` (derived from provider model identifier when a version suffix is present, e.g. `openai/gpt-4o-mini:preview` → `preview`)
- These fields are returned by `GET /api/projects/{project_id}/runs/{run_id}` and are currently persisted even when the run completes with fallback attempts.
- For runs executed with `llm_enabled` false, these values remain `null` because no LLM probe runs.

Run changelog persistence:

- Each run now records a changelog in `run_changelog_entries` with:
  - `run_id` (FK to `runs.id`)
  - `event_type` (for example `run_created`, `pipeline_execution_started`, `pipeline_completed`)
  - `event_message` (human-readable summary)
  - `event_metadata` (structured context like snapshot ids, segment counts, or failure reasons)
  - `created_at` timestamp (UTC)
- Changelog entries are written at run lifecycle boundaries and included in:
  - `GET /api/projects/{project_id}/runs/{run_id}` under `changelog_entries`
- The endpoint returns entries ordered by timestamp so consumers can reconstruct run history deterministically.

Deterministic seed + randomization metadata:

- `POST /api/projects/{project_id}/runs` also accepts:
  - `deterministic_seed` (integer, defaults to `0` when omitted in deterministic mode)
  - `randomization_config` (an object; defaults to a stable preset when omitted)
- In deterministic mode, these values are persisted in `run.config` as:
  - `deterministic_seed`
  - `randomization_config` (defaults: `{"seed": <deterministic_seed>, "strategy": "stable", "shuffle_enabled": false}`)
- Outside deterministic mode, these fields are not persisted to avoid coupling seed-sensitive settings into non-replay runs.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend URL: `http://localhost:5173`  
Backend API URL: `http://localhost:8000`

## Testing

Backend tests:

```bash
cd backend
source .venv311/bin/activate
pytest -q
```

Backend module-level unit coverage thresholds:

```bash
cd backend
source .venv311/bin/activate
pytest tests -q --cov=app --cov-report=json:coverage.unit.json
python scripts_validate_unit_coverage_thresholds.py --coverage-json coverage.unit.json --thresholds unit_coverage_thresholds.json
```

Docs glossary key lint (same check used in CI):

```bash
python backend/scripts_lint_glossary_keys.py
```

Scope consistency validation (`SRS.md §1.2` vs `docs/scope.md`):

```bash
python backend/scripts_validate_scope.py
```

Non-goals consistency validation (`SRS.md §1.2 NIPE SHALL NOT` vs `docs/non_goals.md`):

```bash
python backend/scripts_validate_non_goals.py
```

Shadow Slave success checklist validation (`SRS.md §1.3` vs `docs/shadow_slave_success_checklist.md`):

```bash
python backend/scripts_validate_shadow_slave_success.py
```

Architecture deterministic objective validation (`SRS.md §1.3` vs `docs/architecture.md`):

```bash
python backend/scripts_validate_architecture.py
```

Acceptance KPI validation (`SRS.md §1.3` criteria mapping vs `docs/acceptance_kpis.md`, currently SC-001, SC-002, SC-003, and SC-004):

```bash
python backend/scripts_validate_acceptance_kpis.py
```

Migration framework validation (`backend/migrations` + naming convention):

```bash
python backend/scripts_validate_migration_framework.py
```

Architecture decision records validation (`docs/adrs` coverage and ADR structure):

```bash
python backend/scripts_validate_adrs.py
```

Persona flow validation (`SRS.md §2.1` vs `docs/persona_end_to_end_flows.md`):

```bash
python backend/scripts_validate_persona_flows.py
```

Audiobook UI/API mapping validation (`USE-002` doc completeness and endpoint sequence):

```bash
python backend/scripts_validate_audiobook_flow_map.py
```

Academic outputs/export mapping validation (`USE-003` output definitions and format coverage):

```bash
python backend/scripts_validate_academic_outputs_map.py
```

Author diagnostics mapping validation (`USE-004` requirement definitions and coverage categories):

```bash
python backend/scripts_validate_author_diagnostics_map.py
```

Community reader flow validation (`USE-005` read-only steps and dashboard coverage):

```bash
python backend/scripts_validate_community_reader_flow.py
```

Mode enum contract validation (`MODE-001`, SRS system mode baseline):

```bash
python backend/scripts_validate_mode_enum.py
```

Checklist frontend+Playwright coverage validation (parallel delivery guardrail):

```bash
python backend/scripts_validate_checklist_frontend_coverage.py
```

UC-1 traceability execution (`USE-006`, Shadow Slave -> Audiobook export):

```bash
python backend/scripts_run_uc1_traceability.py
```

UC-2 traceability execution (`USE-007`, Any novel -> Academic export):

```bash
python backend/scripts_run_uc2_traceability.py
```

UC-3 traceability execution (`USE-008`, Draft novel -> Author diagnostics):

```bash
python backend/scripts_run_uc3_traceability.py
```

Frontend build verification:

```bash
cd frontend
npm run build
```

Frontend unit/integration tests:

```bash
cd frontend
npm run test:vitest
```

Frontend unit coverage thresholds by module:

```bash
cd frontend
npm run test:unit:coverage:thresholds
```

Frontend Playwright visual/e2e tests:

```bash
cd frontend
npx playwright install chromium
npm run test:e2e
npm run test:visual
```

## Notes

- The project is currently in PoC stage and intentionally excludes full SRS mode expansion.
- Full-scale implementation work should follow `SRS_Expanded_Implementation_Checklist.md`.
