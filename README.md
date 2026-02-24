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
- Minimal LLM router scaffold + quota tracking
- Minimal React UI for project/run/export flow

## Repository Layout

- `backend/`: FastAPI app, pipeline services, DB models, tests, migrations
  - `backend/app/glossary_terms.py`: shared glossary constants/types synced to `SRS.md §0`
- `frontend/`: React + Vite client
- `PoC.md`: proof-of-concept requirements
- `SRS.md`: full requirements specification
- `SRS_Expanded_Implementation_Checklist.md`: detailed implementation backlog
- `docs/glossary.md`: canonical glossary synced to `SRS.md §0`
- `docs/api_domain_terms.md`: API-facing definitions/examples for key domain terms
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

Frontend build verification:

```bash
cd frontend
npm run build
```

## Notes

- The project is currently in PoC stage and intentionally excludes full SRS mode expansion.
- Full-scale implementation work should follow `SRS_Expanded_Implementation_Checklist.md`.
