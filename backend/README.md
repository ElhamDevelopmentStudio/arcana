# NIPE PoC Backend

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## PostgreSQL

Expected default local DSN:

```text
postgresql+psycopg://postgres@localhost:5432/nipe_poc
```

Create database if needed:

```bash
createdb -U postgres nipe_poc
```

## Run

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

## Optional SQL migration script

```bash
cd backend
python scripts_run_migration.py
```

## API Summary

- `POST /api/projects`
- `POST /api/projects/{project_id}/ingest/txt`
- `POST /api/projects/{project_id}/characters/import`
- `PUT /api/projects/{project_id}/voices`
- `POST /api/projects/{project_id}/runs`
- `GET /api/projects/{project_id}/runs/{run_id}`
- `GET /api/projects/{project_id}/exports/{run_id}.json`

## API Domain Terms

Definitions and examples for API-facing domain terms are documented in:

- [docs/api_domain_terms.md](/Users/elhamdev/work/nipe/docs/api_domain_terms.md)
  (currently: `Novel`, `Corpus`, `Chapter Unit`, `Segment`, `Sub-segment`, `Character Map`, `Voice Map`, `Confidence`, `Evidence Trace`, `Mode`)

## Docs CI Lint

Glossary key existence lint (used in docs CI workflow):

```bash
python scripts_lint_glossary_keys.py
```

Scope validation (`SRS.md §1.2` SHALL/SHALL NOT vs `docs/scope.md`):

```bash
python scripts_validate_scope.py
```

Non-goals validation (`SRS.md §1.2 NIPE SHALL NOT` vs `docs/non_goals.md`):

```bash
python scripts_validate_non_goals.py
```

Shadow Slave success checklist validation (`SRS.md §1.3` vs `docs/shadow_slave_success_checklist.md`):

```bash
python scripts_validate_shadow_slave_success.py
```

Architecture deterministic objective validation (`SRS.md §1.3` vs `docs/architecture.md`):

```bash
python scripts_validate_architecture.py
```

Acceptance KPI validation (`SRS.md §1.3` criteria mapping vs `docs/acceptance_kpis.md`, currently SC-001, SC-002, SC-003, and SC-004):

```bash
python scripts_validate_acceptance_kpis.py
```

Persona flow validation (`SRS.md §2.1` vs `docs/persona_end_to_end_flows.md`):

```bash
python scripts_validate_persona_flows.py
```

Audiobook UI/API mapping validation (`USE-002` doc completeness and endpoint sequence):

```bash
python scripts_validate_audiobook_flow_map.py
```

Academic outputs/export mapping validation (`USE-003` output definitions and format coverage):

```bash
python scripts_validate_academic_outputs_map.py
```

Author diagnostics mapping validation (`USE-004` requirement definitions and coverage categories):

```bash
python scripts_validate_author_diagnostics_map.py
```

Community reader flow validation (`USE-005` read-only steps and dashboard coverage):

```bash
python scripts_validate_community_reader_flow.py
```
