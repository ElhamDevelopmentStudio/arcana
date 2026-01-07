# NIPE Full SRS Expanded Implementation Checklist

Source of truth: [SRS.md](/Users/elhamdev/work/nipe/SRS.md)

Purpose:
- This checklist decomposes the full SRS into very small implementation tasks.
- Every task references the SRS section it comes from.
- Tasks are intentionally granular so a new chat/session can continue with minimal context.

Usage rules:
- Execute tasks as small vertical slices: backend + frontend + integration evidence in the same slice when user-visible behavior is affected.
- Work from the earliest unresolved checklist items first; do not skip ahead unless an item is explicitly marked blocked with reason and follow-up task ID.
- For each completed task, record PR/commit link and date in your tracker.
- If a task reveals new subtasks, append them under the same SRS section with the same reference style.
- Implement backend and frontend in parallel for each feature slice; do not defer all frontend work until backend completion.
- For every API/data-model change, either implement matching frontend behavior in the same slice or log an explicit deferred FE task ID.

Definition of done for each task:
- Code/config/docs are committed.
- Tests for that task are added/updated.
- Logs/errors/metrics are visible where relevant.
- Backward compatibility and migration impact are explicitly checked.
- For user-visible behavior, API + frontend UX + integration evidence are all present (or explicitly deferred with task IDs).

---

## 0. Glossary Alignment (Ref: SRS.md §0)
- [x] [GLS-001] Create `docs/glossary.md` mirroring all SRS glossary terms exactly.
- [x] [GLS-002] Add each glossary term to a shared constants/types file for developer discoverability.
- [x] [GLS-003] Define `Novel` and `Corpus` terms in API docs with examples.
- [x] [GLS-004] Define `Chapter Unit` and `Segment` JSON examples in docs.
- [x] [GLS-005] Define `Sub-segment` storage representation with parent pointers.
- [x] [GLS-006] Define `Character Map` schema examples (minimum + expanded).
- [x] [GLS-007] Define `Voice Map` schema examples and fallback behavior.
- [x] [GLS-008] Define `Confidence` and `Evidence Trace` semantics and range checks.
- [x] [GLS-009] Define `Mode` enum and where it is persisted.
- [x] [GLS-010] Add glossary consistency lint/check in docs CI (simple key existence check).

## 1. Product Intent Baseline (Ref: SRS.md §1)
- [x] [INT-001] Create `docs/scope.md` with SRS “SHALL/SHALL NOT” copied into implementation scope.
- [x] [INT-002] Add explicit non-goals list to prevent accidental feature creep.
- [x] [INT-003] Define success criteria checklist for Shadow Slave end-to-end run.
- [x] [INT-004] Add deterministic reproducibility objective to architecture doc.
- [x] [INT-005] Add acceptance KPI for “clean chapterized corpus” verification.
- [x] [INT-006] Add acceptance KPI for “validated character map”.
- [x] [INT-007] Add acceptance KPI for “TTS-ready tagged export”.
- [x] [INT-008] Add acceptance KPI for “basic time-series and charts”.

## 2. Personas and Use Cases (Ref: SRS.md §2)
- [x] [USE-001] Create one end-to-end flow document per persona.
- [x] [USE-002] Map Audiobook Creator flow to concrete UI steps and API endpoints.
- [x] [USE-003] Map Academic Researcher flow to outputs and export formats.
- [x] [USE-004] Map Author flow to diagnostic report requirements.
- [x] [USE-005] Add “Community Reader” read-only dashboard flow.
- [x] [USE-006] Implement UC-1 traceability test script (Shadow Slave -> Audiobook export).
- [x] [USE-007] Implement UC-2 traceability test script (Any novel -> Academic export).
- [x] [USE-008] Implement UC-3 traceability test script (Draft novel -> Author diagnostics).
- [x] [USE-009] Add optional slow large-corpus regression suite for UC-1/UC-2/UC-3 using `novels_extra_chapter_0_to_22.txt` (real-data traceability + deterministic rerun checks).

## 3. System Modes and Selection (Ref: SRS.md §3)
- [x] [MODE-001] Define mode enum: `audiobook`, `academic`, `author`, `custom`.
- [x] [MODE-002] Persist selected mode on project record.
- [x] [MODE-003] Add API endpoint to fetch available modes.
- [x] [MODE-004] Build post-ingestion mode selection UI.
- [x] [MODE-005] Block pipeline run until mode is selected.
- [x] [MODE-006] Define default config profile object per mode.
- [x] [MODE-007] Implement mode profile loader in backend service.
- [x] [MODE-008] Store loaded profile snapshot in run config.
- [x] [MODE-009] Add mode switching endpoint that reuses ingested corpus.
- [x] [MODE-010] Ensure mode switching does not duplicate raw text rows.
- [x] [MODE-011] Mark downstream artifacts stale after mode switch.
- [x] [MODE-012] Add integration test: ingest once, run all three modes.

## 4.1 Ingestion and Project Setup (Ref: SRS.md §4.1)
- [x] [ING-001] Extend project schema to include `ingestion_timestamp`.
- [x] [ING-002] Add `selected_modes` field to project schema.
- [x] [ING-003] Add `configuration_snapshot` reference on project creation.
- [x] [ING-004] Implement title detection fallback when title is missing.
- [x] [ING-005] Support TXT single-file ingestion path.
- [x] [ING-006] Support chapter-directory ingestion path.
- [x] [ING-007] Support Markdown file ingestion path.
- [x] [ING-008] Add EPUB parser integration toggle (optional now, pluggable).
- [x] [ING-009] Implement encoding detection before decode.
- [x] [ING-010] Convert all accepted content to UTF-8 internal form.
- [x] [ING-011] Persist encoding warnings in run/project logs.
- [x] [ING-012] Add append-chapter endpoint for incremental ingestion.
- [x] [ING-013] Implement chapter overlap/duplicate detector on append.
- [x] [ING-014] Add “affected range” calculator for delta reprocessing.
- [x] [ING-015] Add ingestion error types for unsupported format/encoding/missing chapters.
- [x] [ING-016] Add tests for TXT/dir/md/encoding/incremental append paths.

## 4.2 Deep Normalization (Ref: SRS.md §4.2)
- [x] [NORM-001] Implement chapter detection from file boundaries.
- [x] [NORM-002] Implement chapter detection from header patterns.
- [x] [NORM-003] Implement fallback chapter heuristics for ambiguous text.
- [x] [NORM-004] Add duplicate chapter-title detector.
- [x] [NORM-005] Add unique internal chapter ID assignment while preserving original title.
- [x] [NORM-006] Log chapter-title deduplication actions.
- [x] [NORM-007] Normalize whitespace consistently.
- [x] [NORM-008] Normalize Unicode variants to canonical form.
- [x] [NORM-009] Normalize curly quotes to configured quote style.
- [x] [NORM-010] Normalize ellipsis variants.
- [x] [NORM-011] Normalize line breaks and paragraph separators.
- [x] [NORM-012] Remove obvious copy artifacts via configurable pattern set.
- [x] [NORM-013] Normalize em-dash dialogue style.
- [x] [NORM-014] Implement best-effort quote mismatch repair.
- [x] [NORM-015] Emit warning when quote repair confidence is low.
- [x] [NORM-016] Store original text snapshot per chapter.
- [x] [NORM-017] Store normalized text snapshot per chapter.
- [x] [NORM-018] Create original->normalized offset map (chapter granularity).
- [x] [NORM-019] Create original->normalized offset map (segment granularity).
- [x] [NORM-020] Emit normalization report with counts and lossy-transformation flags.
- [x] [NORM-021] Add regression tests for noisy OCR-like input and quote mismatch edge cases.

## 4.3 Character and Entity Extraction (Ref: SRS.md §4.3)
- [x] [CHAR-001] Expand character schema: `name`, `verbalized_form`, `gender`, `aliases[]`, `notes`, `source`, `confidence`.
- [x] [CHAR-002] Keep PoC JSON/CSV import backward-compatible with new schema.
- [x] [CHAR-003] Implement manual row add/edit/delete UI for character map.
- [x] [CHAR-004] Add auto-extraction job for candidate character names.
- [x] [CHAR-005] Store extraction confidence and source trace for each candidate.
- [x] [CHAR-006] Add optional web-scrape ingestion with explicit warning acknowledgement.
- [x] [CHAR-007] Normalize and merge user-uploaded + auto + scraped candidates.
- [x] [CHAR-008] Implement canonical-name merge suggestions.
- [x] [CHAR-009] Create review screen for proposed characters.
- [x] [CHAR-010] Create approve/reject actions per proposed character.
- [x] [CHAR-011] Add “Finalize character map” gate action.
- [x] [CHAR-012] Prevent downstream runs from using unfinalized proposed set unless override enabled.
- [x] [CHAR-013] Implement alias list storage per character.
- [x] [CHAR-014] Implement alias->canonical lookup service.
- [x] [CHAR-015] Add alias collision detector when alias maps to multiple canonicals.
- [x] [CHAR-016] Implement per-chapter mention counter.
- [x] [CHAR-017] Compute first appearance chapter index.
- [x] [CHAR-018] Compute last appearance chapter index.
- [x] [CHAR-019] Compute mentions per 1,000 words metric.
- [x] [CHAR-020] Compute dialogue line counts where speaker attribution exists.
- [x] [CHAR-021] Add API endpoint for character occurrence analytics.
- [x] [CHAR-022] Add tests for merge, alias conflict, and finalize workflow.

## 4.4 Gender Tagging and Ambiguity (Ref: SRS.md §4.4)
- [x] [GEN-001] Restrict gender values to `male/female/neutral/unknown/custom`.
- [x] [GEN-002] Add DB constraint/validation for permitted values.
- [x] [GEN-003] Treat manual gender as authoritative in resolver logic.
- [x] [GEN-004] Implement optional gender inference module.
- [x] [GEN-005] Persist inferred gender + confidence + evidence trace.
- [x] [GEN-006] Add manual/inferred comparison service.
- [x] [GEN-007] Add contradiction severity score.
- [x] [GEN-008] Add threshold config for contradiction review requirement.
- [x] [GEN-009] Block final export only when contradiction threshold rule requires review.
- [x] [GEN-010] Implement unknown/neutral fallback mapping to neutral/unknown voice bucket.
- [x] [GEN-011] Ensure unknown gender never hard-fails export.
- [x] [GEN-012] Emit low/undefined confidence in export for unknown gender.
- [x] [GEN-013] Mark dependent outputs stale when gender is edited.
- [x] [GEN-014] Trigger voice preview recomputation after gender edits.
- [x] [GEN-015] Add test cases for manual override precedence.
- [x] [GEN-016] Add test cases for contradiction flags and export gating.

## 4.5 Pronunciation and Verbalization (Ref: SRS.md §4.5)
- [x] [VERB-001] Enforce canonical name + verbalized form as required fields.
- [x] [VERB-002] Add pronunciation dictionary table for non-character terms.
- [x] [VERB-003] Support global scope term overrides.
- [x] [VERB-004] Support per-character scope term overrides.
- [x] [VERB-005] Implement before/after substitution preview endpoint.
- [x] [VERB-006] Build UI preview panel for pronunciation checks.
- [x] [VERB-007] Implement whole-word matching mode.
- [x] [VERB-008] Implement case sensitivity toggle.
- [x] [VERB-009] Implement alias-aware substitution mode.
- [x] [VERB-010] Emit warnings for ambiguous replacement candidates.
- [x] [VERB-011] Support place-name verbalizations.
- [x] [VERB-012] Support artifact terminology verbalizations.
- [x] [VERB-013] Support invented word verbalizations.
- [x] [VERB-014] Add tests for false positive replacement prevention.

## 4.6 Segmentation for TTS and Analysis (Ref: SRS.md §4.6)
- [x] [SEG-001] Add chapter->paragraph segmentation layer.
- [x] [SEG-002] Add paragraph->sentence segmentation layer.
- [x] [SEG-003] Add dialogue block detector.
- [x] [SEG-004] Add narration block detector.
- [x] [SEG-005] Implement audiobook max target length config.
- [x] [SEG-006] Implement hard max segment length ceiling.
- [x] [SEG-007] Add intelligibility heuristic to avoid random mid-thought splits.
- [x] [SEG-008] Prefer punctuation boundaries when splitting.
- [x] [SEG-009] Avoid split inside quoted utterance where possible.
- [x] [SEG-010] Add abbreviation/initial-aware split protection.
- [x] [SEG-011] Add metadata: chapter id.
- [x] [SEG-012] Add metadata: segment index.
- [x] [SEG-013] Add metadata: original span pointer.
- [x] [SEG-014] Add metadata: normalized text.
- [x] [SEG-015] Add metadata: phonetic-ready text.
- [x] [SEG-016] Add metadata: parent paragraph reference.
- [x] [SEG-017] Add metadata: parent sentence reference.
- [x] [SEG-018] Implement chapter reconstruction from segments.
- [x] [SEG-019] Implement corpus reconstruction from chapter artifacts.
- [x] [SEG-020] Add round-trip audit test (reconstructed text consistency).

## 4.7 Tagging System (Ref: SRS.md §4.7)
- [x] [TAG-001] Implement structural type tag set (`narration/dialogue/internal thought/mixed/description/action`).
- [x] [TAG-002] Implement speaker attribution output (`speaker_id`, confidence).
- [x] [TAG-003] Implement emotion outputs (`valence`, `intensity`, primary label, secondary label, confidence).
- [x] [TAG-004] Implement shift marker detector scaffolding.
- [x] [TAG-005] Implement tension contribution tag per segment.
- [x] [TAG-006] Implement dominance contribution tag per segment.
- [x] [TAG-007] Detect emotion shift within a segment.
- [x] [TAG-008] Detect narration<->internal thought shift.
- [x] [TAG-009] Detect internal<->external speech shift.
- [x] [TAG-010] Add tone reversal/dark irony marker when triggered.
- [x] [TAG-011] Create sub-segment boundary records on shift.
- [x] [TAG-012] Store sub-segment tags independently.
- [x] [TAG-013] Store parent segment summary tag (dominant tone/state).
- [x] [TAG-014] Add confidence field for every tag category.
- [x] [TAG-015] Add evidence pointer store for every tag category.
- [x] [TAG-016] Add explicit `unknown/uncertain` states for low confidence.
- [x] [TAG-017] Build optional review UI for speaker tags.
- [x] [TAG-018] Build optional review UI for emotional peaks/troughs.
- [x] [TAG-019] Build optional review UI for low-confidence regions.
- [x] [TAG-020] Ensure pipeline can run fully without any manual review step.
- [x] [TAG-021] Add evaluation fixtures for rapid emotional shifts.
- [x] [TAG-022] Add evaluation fixtures for mixed narration/dialogue segments.

## 4.8 Voice Mapping (Ref: SRS.md §4.8)
- [x] [VOICE-001] Add voice map table with per-character assignment.
- [x] [VOICE-002] Add default narrator voice field.
- [x] [VOICE-003] Add default male/female/neutral/unknown voice fields.
- [x] [VOICE-004] Add per-character override field and precedence rule.
- [x] [VOICE-005] Implement resolver output for each dialogue segment.
- [x] [VOICE-006] Include `resolved_voice_id` in export.
- [x] [VOICE-007] Include `speaker_id` used in resolution in export.
- [x] [VOICE-008] Include gender used for resolution in export.
- [x] [VOICE-009] Include speaker+gender confidence in export.
- [x] [VOICE-010] Implement internal-thought voice policy options.
- [x] [VOICE-011] Persist selected thought policy in mode setup.
- [x] [VOICE-012] Add tests for every fallback path.

## 4.9 Audiobook Outputs (Ref: SRS.md §4.9)
- [x] [AUD-001] Define audiobook export package manifest structure.
- [x] [AUD-002] Include ordered segment list for entire corpus.
- [x] [AUD-003] Include phonetic-ready text per segment.
- [x] [AUD-004] Include per-segment voice resolution outputs.
- [x] [AUD-005] Include per-segment tag bundle and confidence.
- [x] [AUD-006] Include project config snapshot in export package.
- [x] [AUD-007] Include logs/reports in export package.
- [x] [AUD-008] Implement JSON export writer.
- [x] [AUD-009] Implement CSV export writer.
- [x] [AUD-010] Implement time-series export arrays.
- [x] [AUD-011] Enforce stable chapter->segment ordering.
- [x] [AUD-012] Implement resumable export by chapter/segment cursor.
- [x] [AUD-013] Guarantee stable segment IDs across equivalent reruns.
- [x] [AUD-014] Emit emotional delta metadata between adjacent segments.
- [x] [AUD-015] Emit scene state and volatility markers.
- [x] [AUD-016] Emit “avoid abrupt change” smoothing hints while preserving raw tags.

## 4.10 Academic Outputs (Ref: SRS.md §4.10)
- [x] [ACAD-001] Compute chapter-level valence mean.
- [x] [ACAD-002] Compute chapter-level valence variance.
- [x] [ACAD-003] Compute emotional volatility index.
- [x] [ACAD-004] Compute rolling-window emotional curves.
- [x] [ACAD-005] Compute raw tension per chapter.
- [x] [ACAD-006] Compute smoothed tension curve.
- [x] [ACAD-007] Detect and mark minor/major tension peaks.
- [x] [ACAD-008] Detect and mark plateau regions.
- [x] [ACAD-009] Compute chapter-level character dominance for key characters.
- [x] [ACAD-010] Build character co-occurrence graph nodes/edges.
- [x] [ACAD-011] Compute graph centrality metrics table.
- [x] [ACAD-012] Implement academic JSON export schema.
- [x] [ACAD-013] Implement academic CSV export schema.
- [x] [ACAD-014] Implement graph JSON export schema.
- [x] [ACAD-015] Include reproducible run snapshot in academic exports.
- [x] [ACAD-016] Implement multi-novel workspace comparison model.
- [x] [ACAD-017] Implement aligned curve comparison view data.
- [x] [ACAD-018] Implement normalized pacing signature comparison data.
- [x] [ACAD-019] Implement comparative dataset export.
- [x] [ACAD-020] Add tests using at least two corpora for comparison correctness.

## 4.11 Author Outputs (Ref: SRS.md §4.11)
- [x] [AUTH-001] Define narrative health report schema.
- [x] [AUTH-002] Implement tension flatline detector.
- [x] [AUTH-003] Implement emotional monotony detector.
- [x] [AUTH-004] Implement over-dominant character warning detector.
- [x] [AUTH-005] Implement disappearing character warning detector.
- [x] [AUTH-006] Implement dialogue density anomaly detector.
- [x] [AUTH-007] Define actionable flag schema (`location`, `trigger_metric`, `severity`, `evidence`).
- [x] [AUTH-008] Implement chapter-range locator for each flag.
- [x] [AUTH-009] Implement severity scoring for each flag.
- [x] [AUTH-010] Attach evidence trace to each flag.
- [x] [AUTH-011] Implement chapter type classifier (`setup/build-up/confrontation/resolution/transitional`).
- [x] [AUTH-012] Output confidence for chapter type classification.
- [x] [AUTH-013] Output reasons/features used for each chapter type.
- [x] [AUTH-014] Build author-mode report export endpoint.
- [x] [AUTH-015] Add test fixtures for each warning type.

## 4.12 LLM Routing and Quota (Ref: SRS.md §4.12)
- [X] [LLM-001] Add LLM usage feature flag per project.
- [x] [LLM-002] Enumerate supported task types (`emotion_refinement`, `speaker_resolution`, etc.).
- [x] [LLM-003] Enforce rule-based first pass before LLM escalation.
- [X] [LLM-004] Add confidence-threshold trigger for escalation.
- [X] [LLM-005] Add ambiguity-flag trigger for escalation.
- [X] [LLM-006] Add user “deep semantic refinement” opt-in trigger.
- [x] [LLM-007] Add provider registry entries for SiliconFlow.
- [x] [LLM-008] Add provider registry entries for Groq.
- [x] [LLM-009] Add provider registry entries for OpenRouter.
- [x] [LLM-010] Add per-provider request count tracking.
- [x] [LLM-011] Add estimated token usage tracking.
- [x] [LLM-012] Add last known rate-limit status tracking.
- [x] [LLM-013] Add last successful call timestamp tracking.
- [x] [LLM-014] Add last reset timestamp tracking if available.
- [x] [LLM-015] Stop calls on provider rate-limit/quota error.
- [x] [LLM-016] Mark provider temporarily unavailable after hard limit events.
- [x] [LLM-017] Resume provider usage after reset detection or manual enable.
- [x] [LLM-018] Add explicit guardrails: no bypass/circumvention behaviors.
- [x] [LLM-019] Add multiple API key support per provider.
- [x] [LLM-020] Add provider priority ordering config.
- [x] [LLM-021] Add manual provider enable/disable toggles.
- [X] [LLM-022] Implement failover to next provider when one is unavailable.
- [X] [LLM-023] Add deterministic mode logs: provider/model/timestamp/token usage.
- [X] [LLM-024] Add tests for quota exhaustion and recovery behavior.

## 4.12.6 Caching (Ref: SRS.md §4.12.6)
- [X] [CACHE-001] Add LLM cache table keyed by input text hash.
- [X] [CACHE-002] Include task type in cache key.
- [X] [CACHE-003] Include configuration snapshot ID in cache key.
- [X] [CACHE-004] Include model identifier in cache key.
- [X] [CACHE-005] Return cached result without provider call on exact key hit.
- [X] [CACHE-006] Track cache hit/miss metrics per task type.
- [X] [CACHE-007] Add cache invalidation policy docs.
- [X] [CACHE-008] Add tests for exact hit and near-miss behavior.

## 4.12.7 Deterministic Mode (Ref: SRS.md §4.12.7)
- [x] [DET-001] Add deterministic mode flag to run config.
- [x] [DET-002] Force deterministic processing order across all stages.
- [x] [DET-003] Pin model identifier/version in deterministic runs.
- [x] [DET-004] Persist deterministic seed and randomization config.
- [x] [DET-005] Add repeat-run equivalence tests for deterministic mode.
- [x] [DET-006] Emit explicit warning when provider nondeterminism may break exact replay.

## 4.13 Provider Abstraction Layer (Ref: SRS.md §4.13)
- [x] [PAL-001] Define `LLMRouter` as sole provider access point.
- [x] [PAL-002] Implement provider selector using availability+quota+priority.
- [x] [PAL-003] Implement dispatch and response parser abstraction.
- [x] [PAL-004] Implement failure classification (`rate_limit`, `quota`, `timeout`, `service_unavailable`, `other`).
- [x] [PAL-005] Implement retry policy by error class.
- [x] [PAL-006] Implement failover handoff to next provider.
- [x] [PAL-007] Add usage metrics logging hooks in router.
- [x] [PAL-008] Define standardized request object fields exactly per SRS.
- [x] [PAL-009] Enforce request validation for required fields.
- [x] [PAL-010] Define standardized response object fields exactly per SRS.
- [x] [PAL-011] Enforce response validation and error mapping.
- [x] [PAL-012] Ensure core modules never import provider SDKs directly.
- [x] [PAL-013] Add architecture test to detect forbidden direct provider imports.
- [x] [PAL-014] Add extension interface for self-hosted local models.
- [x] [PAL-015] Add extension interface for user-supplied provider keys.
- [x] [PAL-016] Add per-project provider configuration support.

## 5. Visualization Requirements (Ref: SRS.md §5)
- [x] [VR-001] Define chart data contracts for tension graph.
- [x] [VR-002] Implement tension graph API payload endpoint.
- [x] [VR-003] Add smoothing toggle for tension graph display.
- [x] [VR-004] Add peak markers and plateau overlays to tension graph.
- [x] [VR-005] Define chart data contracts for emotional polarity graph.
- [x] [VR-006] Implement polarity graph API payload endpoint.
- [x] [VR-007] Add rolling-window control for polarity graph.
- [ ] [VR-008] Define character dashboard data contracts.
- [ ] [VR-009] Implement character prominence and trend widgets.
- [ ] [VR-010] Implement co-occurrence graph viewer payload and render.
- [ ] [VR-011] Define audiobook prep dashboard data contracts.
- [ ] [VR-012] Show unresolved speaker count in audiobook dashboard.
- [ ] [VR-013] Show unresolved voice mapping count in audiobook dashboard.
- [ ] [VR-014] Show low-confidence region count in audiobook dashboard.
- [ ] [VR-015] Show export readiness indicator with blocking reasons.
- [ ] [VR-016] Add dashboard snapshot export capability.

## 6. Data Persistence Requirements (Ref: SRS.md §6)
- [ ] [DR-001] Persist raw corpus blobs with project linkage.
- [ ] [DR-002] Persist normalized corpus blobs with run linkage.
- [ ] [DR-003] Persist chapterized representation with stable IDs.
- [ ] [DR-004] Persist versioned character map snapshots.
- [ ] [DR-005] Persist versioned pronunciation dictionary snapshots.
- [ ] [DR-006] Persist versioned voice map snapshots.
- [ ] [DR-007] Persist tagging outputs and sub-segment outputs.
- [ ] [DR-008] Persist time-series metric outputs for all modes.
- [ ] [DR-009] Persist configuration snapshot per run.
- [ ] [DR-010] Persist model/version metadata per run.
- [x] [DR-011] Persist deterministic seed settings per run.
- [ ] [DR-012] Persist run ID + timestamp + changelog entries.
- [ ] [DR-013] Ensure every tag/metric can resolve back to chapter and segment.
- [ ] [DR-014] Ensure evidence traces include original text offsets.

## 7. Non-Functional Requirements (Ref: SRS.md §7)

### NFR-1 Performance
- [ ] [NFR1-001] Define performance benchmark corpus set (including large scale profile).
- [ ] [NFR1-002] Implement chunked processing framework for long corpora.
- [ ] [NFR1-003] Add parallel-safe chunk scheduler with stable ordering.
- [ ] [NFR1-004] Add incremental-only recomputation mode for appended chapters.
- [ ] [NFR1-005] Add performance telemetry (step durations, memory usage).

### NFR-2 Reliability
- [ ] [NFR2-001] Add ordering integrity guard in every pipeline stage.
- [ ] [NFR2-002] Add chapter-content loss detector after normalization/segmentation.
- [ ] [NFR2-003] Add run-state recovery for interrupted jobs.
- [ ] [NFR2-004] Add idempotent rerun behavior checks.
- [ ] [NFR2-005] Add automated corruption checks on persisted artifacts.

### NFR-3 Usability
- [ ] [NFR3-001] Add pronunciation override UX with inline validation.
- [ ] [NFR3-002] Add gender override UX with contradiction visibility.
- [ ] [NFR3-003] Add character merge UX with undo support.
- [ ] [NFR3-004] Add voice mapping UX with default fallback preview.
- [ ] [NFR3-005] Add docs page “How to review low-confidence outputs”.

### NFR-4 Transparency
- [ ] [NFR4-001] Add UI disclaimer that outputs are probabilistic, not perfect.
- [ ] [NFR4-002] Show confidence score on all major tag outputs.
- [ ] [NFR4-003] Add filtering by confidence thresholds in UI.

### NFR-5 Security and Privacy (SaaS)
- [ ] [NFR5-001] Implement project-level access control model.
- [ ] [NFR5-002] Add project data isolation checks in data access layer.
- [ ] [NFR5-003] Encrypt sensitive uploaded text at rest in SaaS mode.
- [ ] [NFR5-004] Add least-privilege service role matrix for storage and DB.

### NFR-6 Compliance and Copyright Guardrails
- [ ] [NFR6-001] Keep user-upload flow as default ingestion path.
- [ ] [NFR6-002] Add explicit legal warning UI for scraping mode.
- [ ] [NFR6-003] Add “do not store source text” project option.
- [ ] [NFR6-004] Implement derived-metrics-only persistence mode.

### NFR-7 LLM Reliability
- [ ] [NFR7-001] Implement rule-only continuation when all providers unavailable.
- [ ] [NFR7-002] Mark segments refined by LLM vs rule-only.
- [ ] [NFR7-003] Add degraded-mode banner when LLM unavailable.
- [ ] [NFR7-004] Add tests for complete provider outage scenarios.

### NFR-8 API Key Security
- [ ] [NFR8-001] Store API keys server-side only.
- [ ] [NFR8-002] Ensure API keys never reach frontend payloads/logs.
- [ ] [NFR8-003] Scope key access per project/user context.
- [ ] [NFR8-004] Implement key rotation workflow.
- [ ] [NFR8-005] Add key usage audit logging with redaction.

## 8. Error Handling and Warnings (Ref: SRS.md §8)
- [ ] [ER-001] Implement ingestion error class: unsupported format.
- [ ] [ER-002] Implement ingestion error class: encoding failure.
- [ ] [ER-003] Implement ingestion error class: missing chapter content.
- [ ] [ER-004] Implement normalization warning: ambiguous chapter boundaries.
- [ ] [ER-005] Implement normalization warning: uncertain quote repair.
- [ ] [ER-006] Implement normalization warning: suspected duplicate content.
- [ ] [ER-007] Implement character warning: ambiguous alias collisions.
- [ ] [ER-008] Implement character warning: low-confidence extracted characters.
- [ ] [ER-009] Implement character warning: duplicate canonical candidates.
- [ ] [ER-010] Implement gender warning: manual vs inferred contradiction.
- [ ] [ER-011] Implement gender warning: insufficient inference evidence.
- [ ] [ER-012] Implement tagging warning: low-confidence speaker attribution.
- [ ] [ER-013] Implement tagging warning: high-ambiguity dialogue blocks.
- [ ] [ER-014] Implement tagging warning: unstable rapid emotion shifts.
- [ ] [ER-015] Add error/warning catalog page in docs with remediation guidance.

## 9. Configuration Requirements (Ref: SRS.md §9)
- [ ] [CFG-001] Add segmentation target length config.
- [ ] [CFG-002] Add emotion taxonomy config (`basic` vs `expanded`).
- [ ] [CFG-003] Add confidence thresholds config for warnings.
- [ ] [CFG-004] Add web scraping enable/disable config.
- [ ] [CFG-005] Add contradiction-review-required toggle config.
- [ ] [CFG-006] Add internal thought voice policy config.
- [ ] [CFG-007] Add export formats config.
- [ ] [CFG-008] Add export chunk-size config.
- [ ] [CFG-009] Add deterministic mode toggles config.
- [ ] [CFG-010] Define config schema versioning field.
- [ ] [CFG-011] Persist immutable config snapshot per run.
- [ ] [CFG-012] Add config diff viewer between runs.
- [ ] [CFG-013] Add config validation error messages with field-level details.
- [ ] [CFG-014] Add config preset import/export tooling.
- [ ] [CFG-015] Add integration tests for config compatibility across releases.

## 10. MVP Definition Coverage (Ref: SRS.md §10)

### MVP Includes coverage
- [ ] [MVP-001] Verify ingest supports TXT + chapter directory paths.
- [ ] [MVP-002] Verify normalization includes chapters/dedupe/quote normalization/reports.
- [ ] [MVP-003] Verify character map supports aliases and review UI.
- [ ] [MVP-004] Verify dual gender system with inference + contradiction flags.
- [ ] [MVP-005] Verify pronunciation overrides and preview.
- [ ] [MVP-006] Verify TTS segmentation target <=255.
- [ ] [MVP-007] Verify tagging includes structural + emotion + speaker + confidence.
- [ ] [MVP-008] Verify voice mapping includes character + defaults + narrator.
- [ ] [MVP-009] Verify audiobook JSON + CSV exports.
- [ ] [MVP-010] Verify basic dashboards (tension/polarity/prominence).
- [ ] [MVP-011] Verify incremental append update flow.

### MVP Excludes guardrails
- [ ] [MVP-012] Add explicit backlog labels for excluded “nice-to-have” features.
- [ ] [MVP-013] Add release gate preventing excluded features from blocking MVP sign-off.

## 11. Acceptance Criteria Execution (Ref: SRS.md §11)
- [ ] [ACC-001] Build acceptance test: ingest and chapterize Shadow Slave corpus.
- [ ] [ACC-002] Build acceptance test: edit character map with `name/verbalized/gender` fields.
- [ ] [ACC-003] Build acceptance test: pronunciation substitution preview correctness.
- [ ] [ACC-004] Build acceptance test: export contains phonetic-ready text.
- [ ] [ACC-005] Build acceptance test: export contains speaker/gender/voice tags where applicable.
- [ ] [ACC-006] Build acceptance test: export contains emotion + confidence tags.
- [ ] [ACC-007] Build acceptance test: gender contradiction detection and flagging.
- [ ] [ACC-008] Build acceptance test: identical input+config yields reproducible outputs.
- [ ] [ACC-009] Build acceptance test: incremental chapter append updates only affected outputs.
- [ ] [ACC-010] Create final acceptance report template with pass/fail per criterion.

## 12. Cross-Cutting Engineering Tasks (Supports all SRS sections)
- [ ] [X-001] Set up migration framework and migration naming convention.
- [ ] [X-002] Add architecture decision records (ADRs) for mode system, tagging, LLM router.
- [ ] [X-003] Add background job framework for long-running pipeline stages.
- [ ] [X-004] Add run status lifecycle (`queued/running/completed/failed/cancelled`).
- [ ] [X-005] Add cancellation API for running jobs.
- [ ] [X-006] Add structured log schema across all services.
- [ ] [X-007] Add correlation ID propagation across API -> worker -> export.
- [ ] [X-008] Add observability dashboards for pipeline stage durations.
- [ ] [X-009] Add unit-test coverage thresholds by module.
- [ ] [X-010] Add integration test suite per mode.
- [ ] [X-011] Add end-to-end golden dataset snapshots for regression.
- [ ] [X-012] Add smoke test script for local setup in one command.
- [ ] [X-013] Add seed fixtures for quick onboarding.
- [ ] [X-014] Add contributor docs for “How to add a new tag type”.
- [ ] [X-015] Add contributor docs for “How to add a new LLM provider adapter”.
- [ ] [X-016] Add contributor docs for “How to evolve export schema safely”.
- [ ] [X-017] Add release checklist for data migrations and backward compatibility.
- [ ] [X-018] Add rollback plan template for failed releases.
- [ ] [X-019] Add security review checklist per release.
- [ ] [X-020] Add performance regression gate in CI for core pipelines.

## 13. Frontend Parallel Delivery Track (Ref: SRS.md §§2–11)

### 13.1 Parallel Delivery Contract
- [ ] [FE-001] Add “paired frontend impact” note to PR template for all backend/API changes.
- [ ] [FE-002] Add checklist policy that every feature slice must include backend + frontend acceptance notes.
- [ ] [FE-003] Add API contract changelog section consumed by frontend maintainers.
- [ ] [FE-004] Add UI impact matrix mapping SRS sections to frontend pages/components.
- [ ] [FE-005] Add “deferred FE task ID required” policy when backend ships without UI.

### 13.2 App Shell, Routing, and State
- [x] [FE-010] Define route map for project setup, mode selection, run monitor, export viewer, dashboards.
- [x] [FE-011] Implement centralized API client layer with typed request/response helpers.
- [x] [FE-012] Implement shared query/mutation state strategy for project/run lifecycles.
- [x] [FE-013] Implement global loading/error toaster with consistent formatting.
- [x] [FE-014] Add client-side schema guards for critical API payloads.
- [x] [FE-015] Add frontend environment config loader for API base URL and feature flags.
- [ ] [FE-016] Add frontend telemetry hooks for key UX actions (create/ingest/run/export).
- [ ] [FE-017] Add resilient refresh behavior for page reload during active run.
- [ ] [FE-018] Add stale-state invalidation after run completion.
- [ ] [FE-019] Add frontend regression tests for route transitions and persisted UI state.

### 13.3 Mode and Ingestion UX (SRS §3, §4.1, §4.2)
- [x] [FE-020] Build mode-selection panel that loads mode catalog from API and displays default.
- [x] [FE-021] Lock mode-selection controls until ingestion completes successfully.
- [x] [FE-022] Display project-level selected mode and current run-mode snapshot together.
- [ ] [FE-023] Add mode-switch confirmation modal explaining downstream stale artifacts.
- [x] [FE-024] Build ingestion source selector UI for TXT/directory/Markdown/EPUB toggle.
- [ ] [FE-025] Build upload progress and parse summary card with chapter counts.
- [ ] [FE-026] Display normalization report summary (dedupe/quote-repair/warnings).
- [ ] [FE-027] Add “append chapters” UI path with overlap warning display.
- [ ] [FE-028] Add “affected range” UI display after incremental append.
- [ ] [FE-029] Add ingestion warning drawer with remediation tips.

### 13.4 Character, Pronunciation, Gender, and Voice UX (SRS §4.3–§4.8)
- [x] [FE-030] Build editable character map grid with add/edit/delete actions.
- [ ] [FE-031] Build character candidate review queue with approve/reject controls.
- [ ] [FE-032] Build alias conflict resolution modal with canonical selection.
- [ ] [FE-033] Build finalize-character-map gate UI and status indicator.
- [ ] [FE-034] Build pronunciation preview panel showing before/after text substitution.
- [ ] [FE-035] Build pronunciation dictionary management UI (global + per-character scope).
- [ ] [FE-036] Build gender override controls with manual/inferred side-by-side comparison.
- [ ] [FE-037] Build contradiction severity badge and filter controls.
- [ ] [FE-038] Build voice mapping panel for narrator/defaults/character overrides.
- [ ] [FE-039] Build thought-policy selector UI and preview of effective voice resolution.

### 13.5 Segmentation and Tagging Review UX (SRS §4.6–§4.7)
- [ ] [FE-040] Build segment inspector with chapter/segment navigation.
- [ ] [FE-041] Show original text, normalized text, and phonetic text side-by-side per segment.
- [ ] [FE-042] Show sub-segment boundaries with shift-type markers.
- [ ] [FE-043] Show structural tags (`dialogue/narration/internal/etc.`) with confidence chips.
- [ ] [FE-044] Build speaker attribution review UI for low-confidence items.
- [ ] [FE-045] Build emotion trend preview pane with per-segment valence/intensity bars.
- [ ] [FE-046] Build tension/dominance per-segment badges and filter controls.
- [ ] [FE-047] Add evidence-trace popover for each tag with source span pointers.
- [ ] [FE-048] Add unknown/uncertain tag filter with bulk review shortcuts.
- [ ] [FE-049] Add round-trip reconstruction preview from segment list to chapter text.

### 13.6 Audiobook, Academic, and Author Output UX (SRS §4.9–§4.11)
- [ ] [FE-050] Build audiobook export readiness panel with blocking reasons.
- [ ] [FE-051] Build audiobook export manifest viewer with stable ordering indicators.
- [ ] [FE-052] Build JSON/CSV export download center with chunked export status.
- [ ] [FE-053] Build academic metrics dashboard (emotion/tension/volatility summaries).
- [ ] [FE-054] Build character co-occurrence graph explorer (nodes/edges, focus filters).
- [ ] [FE-055] Build comparative analysis workspace view for multi-novel overlays.
- [ ] [FE-056] Build author narrative-health report screen with grouped warning categories.
- [ ] [FE-057] Build actionable-flag list with chapter-range links and evidence expansion.
- [ ] [FE-058] Build chapter-type classification panel with confidence + feature reasons.
- [ ] [FE-059] Build export provenance/manifest card for all three modes.

### 13.7 LLM, Determinism, and Provider Controls UX (SRS §4.12–§4.13)
- [ ] [FE-060] Build provider status panel showing quota/rate-limit/availability.
- [ ] [FE-061] Build LLM feature-flag controls with per-task escalation toggles.
- [ ] [FE-062] Build provider priority ordering UI with drag-and-drop ranking.
- [ ] [FE-063] Build deterministic-mode toggle with explicit replay constraints.
- [ ] [FE-064] Show run-level deterministic metadata (`model`, `seed`, `snapshot_id`).
- [ ] [FE-065] Show cache hit/miss counters for LLM-assisted tasks.
- [ ] [FE-066] Show degraded-mode banner when running rule-only fallback.
- [ ] [FE-067] Build API key status UI (never exposing raw keys).
- [ ] [FE-068] Build provider failover event timeline in run logs.
- [ ] [FE-069] Add frontend tests for deterministic replay UX messaging.

### 13.8 Visualization and Dashboard UX (SRS §5)
- [ ] [FE-070] Build tension graph component with smoothing toggle and peak overlays.
- [ ] [FE-071] Build emotional polarity graph with rolling-window control.
- [ ] [FE-072] Build character prominence trend chart with chapter filters.
- [ ] [FE-073] Build audiobook prep dashboard cards for unresolved mappings.
- [ ] [FE-074] Build confidence heatmap across chapter timeline.
- [ ] [FE-075] Build dashboard snapshot export action.
- [ ] [FE-076] Build linked-hover interactions between charts and segment inspector.
- [ ] [FE-077] Build chart legend configuration panel per dashboard.
- [x] [FE-078] Build empty-state UI for projects lacking required run artifacts.
- [ ] [FE-079] Add frontend regression tests for chart payload contract handling.

### 13.9 Error Handling, Accessibility, and Performance UX (SRS §7–§9)
- [ ] [FE-080] Build standardized warning/error banner component with severity levels.
- [ ] [FE-081] Build remediation panel linking each warning code to “what to do next”.
- [ ] [FE-082] Add keyboard navigation and focus management for core workflows.
- [ ] [FE-083] Add WCAG contrast checks and semantic labels for charts/forms.
- [x] [FE-084] Add responsive layouts for desktop/tablet/mobile breakpoints.
- [ ] [FE-085] Add skeleton loading states for all major API-driven panels.
- [ ] [FE-086] Add client-side performance instrumentation (TTI, route latency, render cost).
- [ ] [FE-087] Add config editor UX for segmentation/emotion/confidence thresholds.
- [ ] [FE-088] Add config diff viewer between runs in frontend.
- [ ] [FE-089] Add frontend regression tests for error-state and warning-state rendering.

### 13.10 Playwright Visual and E2E Suite (Frontend + API Integration)
- [x] [PW-001] Set up Playwright test runner and browser project matrix.
- [ ] [PW-002] Add baseline visual snapshots for project creation and ingestion screens.
- [x] [PW-003] Add baseline visual snapshots for post-ingestion mode selection screen.
- [ ] [PW-004] Add baseline visual snapshots for character map and voice mapping screens.
- [ ] [PW-005] Add baseline visual snapshots for run monitor and export panels.
- [ ] [PW-006] Add baseline visual snapshots for tension/polarity/character dashboards.
- [ ] [PW-007] Add responsive visual snapshots (desktop/tablet/mobile) for core pages.
- [ ] [PW-008] Add end-to-end Playwright flow: create project -> ingest -> select mode -> run -> export.
- [ ] [PW-009] Add end-to-end Playwright flow for academic dashboard and export retrieval.
- [ ] [PW-010] Add end-to-end Playwright flow for author diagnostics review and flag inspection.
- [ ] [PW-011] Add visual diff thresholds and explicit allowlist for intentional UI changes.
- [x] [PW-012] Add deterministic test-data fixtures for Playwright runs.
- [ ] [PW-013] Add Playwright API mocking strategy for isolated frontend contract tests.
- [ ] [PW-014] Add Playwright “real backend” profile for integrated local E2E checks.
- [ ] [PW-015] Add flaky-test retry policy and trace/video artifact retention.
- [ ] [PW-016] Add CI job split: unit/integration vs Playwright visual/e2e.
- [ ] [PW-017] Add accessibility scan step (axe) inside Playwright critical flows.
- [ ] [PW-018] Add screenshot assertions for warning/error banners and degraded-mode states.
- [ ] [PW-019] Add visual regression coverage for theme/fonts/layout token changes.
- [ ] [PW-020] Add release gate requiring Playwright visual suite pass for UI-affecting PRs.

---

## Suggested Execution Order (for new sessions)
1. Resume rule first: scan from the top and pick the earliest unresolved task that is not blocked.
2. If an earlier task is unresolved, complete it (or mark blocked with reason + unblock task ID) before moving to later sections.
3. For the selected task, deliver a vertical slice: backend behavior, frontend behavior, and test coverage together.
4. Pair API/data-model work with corresponding FE and Playwright coverage in the same slice whenever UI behavior is impacted.
5. Apply the sequence bands below while still honoring the “earliest unresolved task first” rule:
6. Foundations: `GLS-*`, `INT-*`, `USE-*`, `MODE-*`.
7. Core pipeline: `ING-*`, `NORM-*`, `CHAR-*`, `GEN-*`, `VERB-*`, `SEG-*`, `TAG-*`, `VOICE-*`.
8. Mode outputs: `AUD-*`, `ACAD-*`, `AUTH-*`.
9. LLM platform: `LLM-*`, `CACHE-*`, `DET-*`, `PAL-*`.
10. Visualization and persistence: `VR-*`, `DR-*`.
11. Operational hardening: `NFR*`, `ER-*`, `CFG-*`, `X-*`.
12. Release gates: `MVP-*`, `ACC-*`.
