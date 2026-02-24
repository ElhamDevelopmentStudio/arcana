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
- Mode catalog endpoint for UI mode selection bootstrap (`GET /api/modes`)
- Minimal LLM router scaffold + quota tracking
- Minimal React UI for project/run/export flow

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
- `docs/persona_end_to_end_flows.md`: one end-to-end flow per SRS persona
- `docs/system_modes.md`: canonical MODE-001 enum contract for SRS section 3 mode values
- `docs/audiobook_ui_api_mapping.md`: USE-002 mapping from audiobook UI steps to concrete API endpoints
- `docs/academic_outputs_export_mapping.md`: USE-003 mapping from academic flow to outputs and export formats
- `docs/author_diagnostic_requirements_mapping.md`: USE-004 mapping from author flow to diagnostic report requirements
- `docs/community_reader_readonly_dashboard_flow.md`: USE-005 read-only dashboard flow for community reader
- `docs/reference_feature_overlap.md`: overlap map to the external read-only reference project
- `AGENTS.md`: repository execution rules for small-task delivery and testing discipline
- `sample_character_map_shadow_slave.json`: sample character map import file
- `shadow_slave_chapter_1_to_95.txt`: sample source text corpus

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

## Notes

- The project is currently in PoC stage and intentionally excludes full SRS mode expansion.
- Full-scale implementation work should follow `SRS_Expanded_Implementation_Checklist.md`.
