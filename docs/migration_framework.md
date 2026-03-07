# Migration Framework and Naming Convention

Reference sources:
- [SRS_Expanded_Implementation_Checklist.md](/Users/elhamdev/work/nipe/SRS_Expanded_Implementation_Checklist.md) item `X-001`

Purpose:
- Define the baseline migration framework for NIPE backend schema evolution.
- Enforce a deterministic migration naming convention for ordering and reviewability.

## Framework

- Migration files are SQL files in `backend/migrations/`.
- Migrations are applied in lexical order by `backend/scripts_run_migration.py`.
- Every migration file must be idempotent-safe for repeated local application where possible.

## Required Naming Convention

- Filename pattern: `NNN_snake_case_description.sql`
- `NNN` is a 3-digit zero-padded sequence starting at `001`.
- Sequence must be contiguous with no gaps (`001`, `002`, `003`, ...).
- `snake_case_description` uses lowercase letters, digits, and underscores only.

Examples:
- `001_initial.sql`
- `012_project_access_control.sql`
- `013_add_run_status_lifecycle.sql`

Invalid examples:
- `13_add_run_status.sql` (not zero-padded)
- `013-AddRunStatus.sql` (invalid casing/separators)
- `013_add-run-status.sql` (invalid `-`)

## Validation Command

```bash
python backend/scripts_validate_migration_framework.py
```

