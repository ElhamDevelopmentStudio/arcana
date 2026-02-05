# Release Checklist: Data Migrations and Backward Compatibility

Use this checklist before each release that changes schema, data layout, API contracts, or export payloads.

## Release Checklist: Data migrations and backward compatibility

### Item 1: Catalog schema and data-change impact
- objective: Document every table/column/index/constraint change and identify impacted services and endpoints.
- actions: Enumerate migration files, touched models, and API/export surfaces; mark additive vs breaking changes explicitly.
- evidence: Linked migration plan note with requirement IDs and owner sign-off.

### Item 2: Validate migration ordering and idempotence assumptions
- objective: Ensure migrations apply in expected sequence without hidden environment coupling.
- actions: Verify migration naming/order conventions, confirm forward-apply behavior, and test fresh-db plus existing-db upgrade paths.
- evidence: CI or local execution logs showing ordered migration success on clean and upgraded databases.

### Item 3: Define compatibility window and fallback behavior
- objective: Preserve backward compatibility for clients and runs still operating on previous payload expectations.
- actions: Identify temporary dual-read/dual-write or default-value behavior, declare deprecation windows, and gate breaking changes behind explicit version markers.
- evidence: Compatibility matrix covering backend schema, export payload shape, and frontend parser expectations.

### Item 4: Execute contract and regression coverage for changed surfaces
- objective: Prove that migration-adjacent behavior remains stable across backend and frontend integration paths.
- actions: Run targeted backend unit/integration tests, export/manifest regression suites, and frontend backend-contract e2e checks.
- evidence: Test run summary capturing pass/fail status for all migration-impacted suites.

### Item 5: Capture rollout and rollback readiness
- objective: Confirm release can be safely deployed and reversed if production validation fails.
- actions: Record rollout order, pre-deploy backup checkpoints, and rollback trigger thresholds; include command-level runbook references.
- evidence: Release note section with named owner, rollback command references, and go/no-go approval timestamp.

### Item 6: Perform post-release verification and closeout
- objective: Validate production health after migration and close temporary compatibility scaffolding only when safe.
- actions: Verify health metrics, audit migration side effects, review error/warning deltas, and create follow-up tasks for deferred cleanup.
- evidence: Post-release verification log with monitoring snapshot and closure decision.
