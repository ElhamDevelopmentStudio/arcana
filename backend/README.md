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

- `GET /api/modes`
- `POST /api/projects`
- `PUT /api/projects/{project_id}/mode`
- `POST /api/projects/{project_id}/ingest/txt`
- `POST /api/projects/{project_id}/ingest/chapters-dir`
- `POST /api/projects/{project_id}/ingest/markdown`
- `POST /api/projects/{project_id}/ingest/epub`
- `POST /api/projects/{project_id}/ingest/append-chapter`
- `POST /api/projects/{project_id}/characters/import`
- `PUT /api/projects/{project_id}/voices`
- `POST /api/projects/{project_id}/runs`
- `GET /api/projects/{project_id}/runs/{run_id}`
- `GET /api/projects/{project_id}/exports/{run_id}.json`

Mode persistence behavior:
- Project-level selected mode is stored at `projects.selected_mode`.
- Project-level mode history/set is tracked in `projects.selected_modes`.
- Mode changes can be persisted before runs via `PUT /api/projects/{project_id}/mode`.
- Mode changes mark prior runs from different modes as stale via `runs.config_json.artifacts_stale=true`.
- Project records keep `ingestion_timestamp` (`null` until first ingestion, then UTC timestamp).
- Project creation sets `configuration_snapshot_id` reference (initial format: `project-<id>-config-initial`).
- Each run snapshots mode in `runs.config_json.mode`.
- Each run stores immutable defaults at `runs.config_json.mode_profile_snapshot`.

Ingestion title fallback behavior:
- If project title is a placeholder (`Untitled Project` / `New Project`), TXT ingestion attempts title detection from source text.
- If no title is detectable from text, ingestion falls back to filename stem, then `Untitled Novel`.
- Chapter-directory ingestion accepts multi-file `.txt` uploads and ingests files in natural filename order.
- Markdown ingestion accepts `.md`/`.markdown` files and normalizes markdown syntax before chapter detection.
- EPUB ingestion is toggle-controlled (`ENABLE_EPUB_INGESTION`) and currently wired to a pluggable parser stub.
- Incremental append ingestion supports one `.txt` chapter payload at a time (`/ingest/append-chapter`) without replacing existing chapters.
- Append ingestion rejects exact duplicates and high-overlap same-title content with HTTP `409` conflict.
- Text ingestion performs encoding detection before decode (BOM + UTF-8/UTF-16 heuristics + cp1252 fallback).
- All ingestion inputs are normalized to UTF-8-safe internal strings before chapter persistence (`chapter_title`, `raw_text`).
- Encoding anomalies are persisted in `projects.ingestion_log_json.warnings` and copied into `runs.config_json.ingestion_warnings`.
- Mode catalog includes `mode_profiles` with default run-config values per mode.

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

Mode enum contract validation (`MODE-001`, SRS system mode baseline):

```bash
python scripts_validate_mode_enum.py
```

Checklist frontend+Playwright coverage validation (parallel delivery guardrail):

```bash
python scripts_validate_checklist_frontend_coverage.py
```

UC-1 traceability execution (`USE-006`, Shadow Slave -> Audiobook export):

```bash
python scripts_run_uc1_traceability.py
```

UC-2 traceability execution (`USE-007`, Any novel -> Academic export):

```bash
python scripts_run_uc2_traceability.py
```

UC-3 traceability execution (`USE-008`, Draft novel -> Author diagnostics):

```bash
python scripts_run_uc3_traceability.py
```

USE-009 optional slow large-corpus regression suite (`novels_extra_chapter_0_to_22.txt`, UC1/UC2/UC3 deterministic re-run checks):

```bash
python scripts_run_large_corpus_traceability.py --allow-slow
```

Optional slow test execution for USE-009:

```bash
RUN_SLOW_TRACEABILITY=1 pytest tests/test_large_corpus_traceability_regression.py -q
```
