# Contributor Guide: Evolve Export Schema Safely

Use this guide when changing export payload shape so backward compatibility and frontend contracts remain stable.

## Contributor Guide: How to evolve export schema safely

### Step 1: Define change scope and compatibility strategy
- objective: Decide whether the change is additive, soft-deprecated, or breaking, and document required compatibility guarantees.
- files: `SRS.md`, `SRS_Expanded_Implementation_Checklist.md`, `docs/api_domain_terms.md`
- checks: confirm requirement IDs and acceptance impact are explicit before code changes.

### Step 2: Version schema and keep parser-safe defaults
- objective: Add or update explicit schema/version markers and default-safe field behavior to prevent consumer crashes.
- files: `backend/app/schemas.py`, `backend/app/services/export.py`
- checks: ensure omitted/legacy fields still parse and new fields have deterministic defaults where required.

### Step 3: Update backend manifest/export builders
- objective: Propagate the schema change through all export endpoints and manifest sections consistently.
- files: `backend/app/services/export.py`, `backend/app/main.py`
- checks: verify JSON/CSV/academic/author export paths produce coherent field sets and error messages for invalid requests.

### Step 4: Update frontend schema guards and consumers
- objective: Keep frontend runtime validation and feature modules synchronized with new export fields.
- files: `frontend/src/app/schemas/api.ts`, `frontend/src/features/workflow/api/workflow-hooks.ts`, route modules under `frontend/src/pages`
- checks: ensure parsing, rendering, and download flows handle both current and transitional payloads.

### Step 5: Add regression fixtures and contract coverage
- objective: Freeze expected output shape with snapshots/fixtures and contract assertions to catch accidental drift.
- files: `backend/tests/test_export_manifest.py`, `backend/tests/fixtures/`, `frontend/tests/unit/`, `frontend/tests/e2e/backend-endpoint-contract.e2e.spec.ts`
- checks: include unit/integration/e2e tests for new and legacy-compatible payload shapes.

### Step 6: Document migration notes and run local smoke
- objective: Record rollout notes and verify live backend/frontend contract behavior before merge.
- files: `README.md`, `backend/README.md`, `docs/final_acceptance_report_template.md`
- checks: run `python3 backend/scripts_run_local_smoke.py` and confirm backend smoke plus frontend live-backend contract smoke pass.
