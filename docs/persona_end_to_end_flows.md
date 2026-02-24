# NIPE Persona End-to-End Flows

Reference sources:
- [SRS.md](/Users/elhamdev/work/nipe/SRS.md) sections `### 2.1 Personas` and `### 2.2 Primary Use Cases`
- [SRS_Expanded_Implementation_Checklist.md](/Users/elhamdev/work/nipe/SRS_Expanded_Implementation_Checklist.md) item `USE-001`

Purpose:
- Define one end-to-end flow for each SRS persona.
- Provide session-resumable implementation context before persona-specific subtask expansion.

## Audiobook Creator (TTS) End-to-End Flow

- flow_id: FLOW-AUDIOBOOK-001
- objective: Generate a TTS-ready export from novel input with stable segmentation, pronunciation handling, and voice-ready tagging.
- expected_outcome: User receives a TTS-ready structured export package suitable for downstream narration tooling.

1. Create a project and ingest novel text into the system.
2. Confirm chapterization and normalization completed without blocking ingestion errors.
3. Provide or review character map entries and pronunciation forms needed for TTS.
4. Select audiobook-oriented processing configuration for segmentation and tagging depth.
5. Run the processing pipeline and wait for completion status.
6. Download and verify the generated TTS-ready structured export.

## Academic Researcher End-to-End Flow

- flow_id: FLOW-ACADEMIC-001
- objective: Produce reproducible narrative analytics outputs for study and comparison.
- expected_outcome: User receives structured metrics exports and analysis-ready artifacts for external research workflows.

1. Create a project and ingest the target novel corpus.
2. Confirm text normalization and chapter structure are persisted correctly.
3. Select the academic/research workflow configuration.
4. Run analysis processing for tagging and narrative metric generation.
5. Retrieve academic-oriented exports (metrics/time-series/graph-ready data).
6. Validate that run metadata and outputs are sufficient for repeatable comparison.

## Fiction Author End-to-End Flow

- flow_id: FLOW-AUTHOR-001
- objective: Generate narrative diagnostics that highlight pacing, emotional variation, and character balance signals.
- expected_outcome: User receives an actionable diagnostics report with supporting structured data.

1. Create a project and ingest draft novel material.
2. Confirm chapter and normalization outputs are available for diagnostic processing.
3. Select the author-oriented workflow configuration.
4. Run pipeline steps that compute tagging and narrative health indicators.
5. Review generated diagnostics and associated evidence in exported artifacts.
6. Capture follow-up revisions or review notes for the next iteration run.

## Community Reader End-to-End Flow

- flow_id: FLOW-COMMUNITY-001
- objective: Explore narrative insights through read-only dashboards and summary views.
- expected_outcome: User can navigate interactive narrative views without requiring authoring or administrative actions.

1. Open an existing processed project prepared for exploration.
2. Load available dashboard datasets and summary views.
3. Navigate chapter-level and character-level narrative trends.
4. Inspect high-level emotional/tension/dominance curves and notable transitions.
5. Filter or switch views to focus on arcs, chapters, or character slices.
6. Export or share read-only insights artifacts where available.
