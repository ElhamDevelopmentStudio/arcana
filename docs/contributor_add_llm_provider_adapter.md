# Contributor Guide: Add a New LLM Provider Adapter

Use this guide when introducing a new LLM provider adapter so routing, config, UI, and run reproducibility stay aligned.

## Contributor Guide: How to add a new LLM provider adapter

### Step 1: Register provider metadata and adapter hooks
- objective: Add provider metadata, payload/header builders, and registration in the LLM router.
- files: `backend/app/services/llm_router.py`
- checks: verify `register_llm_provider` and `is_supported_provider` include the new provider and reject duplicate registrations unless overwrite is explicit.

### Step 2: Extend settings and environment configuration
- objective: Add provider key/model/base-url settings and parse behavior for single-key and key-list modes.
- files: `backend/app/config.py`, `backend/.env.example`
- checks: confirm settings load cleanly from `.env` and parse both comma-separated and JSON-style key lists.

### Step 3: Wire run-level config propagation and API contracts
- objective: Ensure project/run request schemas can carry provider-specific config and per-run key overrides safely.
- files: `backend/app/schemas.py`, `backend/app/main.py`, `frontend/src/app/schemas/api.ts`
- checks: confirm run config snapshots persist normalized provider config and redact sensitive values in exported/report payloads where applicable.

### Step 4: Cover quota, failover, toggles, and audit behavior
- objective: Keep provider-selection reliability and operational auditing consistent with ADR-103 failover policy.
- files: `backend/app/services/llm_router.py`, `backend/app/services/provider_toggle.py`, `backend/app/models.py`
- checks: validate ordered failover, quota exhaustion handling, provider toggle gates, and provider API key usage audit rows.

### Step 5: Add backend + frontend regression coverage
- objective: Add deterministic tests for adapter registration, routing behavior, API contracts, and UI-facing payload shape.
- files: `backend/tests/test_llm_router.py`, `backend/tests/test_llm_provider_toggles.py`, `backend/tests/test_run_provider_api_keys.py`, `frontend/tests/unit/`, `frontend/tests/e2e/backend-endpoint-contract.e2e.spec.ts`
- checks: include unit/integration/e2e assertions for the new provider path and keep existing providers non-regressive.

### Step 6: Update contributor docs and run local smoke
- objective: Document the adapter procedure and verify end-to-end behavior against a live local backend.
- files: `README.md`, `backend/README.md`, `SRS_Expanded_Implementation_Checklist.md`
- checks: run `python3 backend/scripts_run_local_smoke.py` and confirm backend smoke plus frontend live-backend contract smoke pass.
