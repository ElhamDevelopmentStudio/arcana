# ADR-102: Tagging Pipeline Uses Deterministic Rule-First Enrichment Contracts

Reference sources:
- [SRS.md](/Users/elhamdev/work/nipe/SRS.md) section `### 4.7 Tagging System`
- [SRS.md](/Users/elhamdev/work/nipe/SRS.md) section `### 4.4 Gender Tagging and Ambiguity Handling`

## Status

accepted

## Context

- Tagging output drives downstream exports, voice mapping, analytics, and review workflows.
- Output contracts must remain stable and machine-checkable across runs and modes.
- Contradiction and ambiguity cases must produce explicit warnings instead of silent fallthrough.

## Decision

- Use deterministic rule-first tagging as the baseline path across pipeline execution.
- Emit structured per-segment tags with confidence and evidence-oriented fields.
- Persist tagging warnings in run config artifacts for traceability.
- Keep export contracts explicit for speaker, emotion, tension, dominance, and shift-related metadata.

## Consequences

- Exports are consistently consumable by frontend and external automation.
- Heuristic improvements can be introduced without breaking schema compatibility.
- Review workflows can target low-confidence or contradictory tags with explicit evidence pointers.

## Backend Impact

- `backend/app/services/tagging.py`
- `backend/app/services/pipeline.py`
- `backend/app/services/export.py`

## Frontend Impact

- Export and diagnostics views can reliably render tag-driven metadata and confidence fields
- QA/regression tests can assert stable tagging fields across representative pipeline runs
- Warning displays can surface contradiction and low-confidence conditions for user review

