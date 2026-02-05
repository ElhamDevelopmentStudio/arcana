# Contributor Guide: Add a New Tag Type

Use this guide when introducing a new tag type to NIPE so backend, frontend, and exports stay contract-safe.

## Contributor Guide: How to add a new tag type

### Step 1: Define the tag contract
- objective: Specify exact tag fields, state/confidence semantics, and evidence payload shape before implementation.
- files: `SRS.md`, `docs/api_domain_terms.md`, `backend/app/schemas.py`, `frontend/src/app/schemas/api.ts`
- checks: validate that backend and frontend schemas accept the same field names and enum values.

### Step 2: Implement backend tagging logic
- objective: Produce the new tag in deterministic backend tagging services and include source evidence.
- files: `backend/app/services/tagging.py`, `backend/app/services/tagging_warning_catalog.py`
- checks: run unit tests for the tag builder and verify deterministic output for identical input/config.

### Step 3: Propagate the tag through export and run payloads
- objective: Ensure the new tag appears in run detail payloads and export outputs where required.
- files: `backend/app/services/export.py`, `backend/app/main.py`, `backend/app/schemas.py`
- checks: run export manifest and endpoint tests to confirm the new tag is serialized and validated.

### Step 4: Expose frontend contract and UX surfaces
- objective: Keep API client schemas, workflow payloads, and any visible UI tied to the tag in sync.
- files: `frontend/src/app/schemas/api.ts`, `frontend/src/services/api-client.ts`, route-level feature modules under `frontend/src/pages` and `frontend/src/features`
- checks: run frontend unit/integration/regression tests that parse or display the updated tag payload.

### Step 5: Add fixtures and automated regression coverage
- objective: Add representative fixtures for the new tag and cover unit, integration, and e2e contract behavior.
- files: `backend/tests/fixtures/`, `backend/tests/`, `frontend/tests/unit/`, `frontend/tests/e2e/backend-endpoint-contract.e2e.spec.ts`
- checks: add snapshot/assertion coverage so future changes fail fast when tag output shape drifts.

### Step 6: Document rollout and run local smoke
- objective: Update contributor-facing docs and validate the end-to-end workflow against a live backend.
- files: `README.md`, `backend/README.md`, `SRS_Expanded_Implementation_Checklist.md`
- checks: run `python3 backend/scripts_run_local_smoke.py` and confirm backend smoke + frontend live-backend contract smoke pass.
