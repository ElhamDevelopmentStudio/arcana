# NIPE Full SRS Expanded Implementation Checklist

Source of truth: [SRS.md](/Users/elhamdev/work/nipe/SRS.md)

Purpose:
- This checklist decomposes the full SRS into very small implementation tasks.
- Every task references the SRS section it comes from.
- Tasks are intentionally granular so a new chat/session can continue with minimal context.

Usage rules:
- Complete tasks in order unless a dependency explicitly allows parallel work.
- For each completed task, record PR/commit link and date in your tracker.
- If a task reveals new subtasks, append them under the same SRS section with the same reference style.

Definition of done for each task:
- Code/config/docs are committed.
- Tests for that task are added/updated.
- Logs/errors/metrics are visible where relevant.
- Backward compatibility and migration impact are explicitly checked.

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
- [ ] [INT-002] Add explicit non-goals list to prevent accidental feature creep.
- [ ] [INT-003] Define success criteria checklist for Shadow Slave end-to-end run.
- [ ] [INT-004] Add deterministic reproducibility objective to architecture doc.
- [ ] [INT-005] Add acceptance KPI for “clean chapterized corpus” verification.
- [ ] [INT-006] Add acceptance KPI for “validated character map”.
- [ ] [INT-007] Add acceptance KPI for “TTS-ready tagged export”.
- [ ] [INT-008] Add acceptance KPI for “basic time-series and charts”.

## 2. Personas and Use Cases (Ref: SRS.md §2)
- [ ] [USE-001] Create one end-to-end flow document per persona.
- [ ] [USE-002] Map Audiobook Creator flow to concrete UI steps and API endpoints.
- [ ] [USE-003] Map Academic Researcher flow to outputs and export formats.
- [ ] [USE-004] Map Author flow to diagnostic report requirements.
- [ ] [USE-005] Add “Community Reader” read-only dashboard flow.
- [ ] [USE-006] Implement UC-1 traceability test script (Shadow Slave -> Audiobook export).
- [ ] [USE-007] Implement UC-2 traceability test script (Any novel -> Academic export).
- [ ] [USE-008] Implement UC-3 traceability test script (Draft novel -> Author diagnostics).

## 3. System Modes and Selection (Ref: SRS.md §3)
- [ ] [MODE-001] Define mode enum: `audiobook`, `academic`, `author`, `custom`.
- [ ] [MODE-002] Persist selected mode on project record.
- [ ] [MODE-003] Add API endpoint to fetch available modes.
- [ ] [MODE-004] Build post-ingestion mode selection UI.
- [ ] [MODE-005] Block pipeline run until mode is selected.
- [ ] [MODE-006] Define default config profile object per mode.
- [ ] [MODE-007] Implement mode profile loader in backend service.
- [ ] [MODE-008] Store loaded profile snapshot in run config.
- [ ] [MODE-009] Add mode switching endpoint that reuses ingested corpus.
- [ ] [MODE-010] Ensure mode switching does not duplicate raw text rows.
- [ ] [MODE-011] Mark downstream artifacts stale after mode switch.
- [ ] [MODE-012] Add integration test: ingest once, run all three modes.

## 4.1 Ingestion and Project Setup (Ref: SRS.md §4.1)
- [ ] [ING-001] Extend project schema to include `ingestion_timestamp`.
- [ ] [ING-002] Add `selected_modes` field to project schema.
- [ ] [ING-003] Add `configuration_snapshot` reference on project creation.
- [ ] [ING-004] Implement title detection fallback when title is missing.
- [ ] [ING-005] Support TXT single-file ingestion path.
- [ ] [ING-006] Support chapter-directory ingestion path.
- [ ] [ING-007] Support Markdown file ingestion path.
- [ ] [ING-008] Add EPUB parser integration toggle (optional now, pluggable).
- [ ] [ING-009] Implement encoding detection before decode.
- [ ] [ING-010] Convert all accepted content to UTF-8 internal form.
- [ ] [ING-011] Persist encoding warnings in run/project logs.
- [ ] [ING-012] Add append-chapter endpoint for incremental ingestion.
- [ ] [ING-013] Implement chapter overlap/duplicate detector on append.
- [ ] [ING-014] Add “affected range” calculator for delta reprocessing.
- [ ] [ING-015] Add ingestion error types for unsupported format/encoding/missing chapters.
- [ ] [ING-016] Add tests for TXT/dir/md/encoding/incremental append paths.

## 4.2 Deep Normalization (Ref: SRS.md §4.2)
- [ ] [NORM-001] Implement chapter detection from file boundaries.
- [ ] [NORM-002] Implement chapter detection from header patterns.
- [ ] [NORM-003] Implement fallback chapter heuristics for ambiguous text.
- [ ] [NORM-004] Add duplicate chapter-title detector.
- [ ] [NORM-005] Add unique internal chapter ID assignment while preserving original title.
- [ ] [NORM-006] Log chapter-title deduplication actions.
- [ ] [NORM-007] Normalize whitespace consistently.
- [ ] [NORM-008] Normalize Unicode variants to canonical form.
- [ ] [NORM-009] Normalize curly quotes to configured quote style.
- [ ] [NORM-010] Normalize ellipsis variants.
- [ ] [NORM-011] Normalize line breaks and paragraph separators.
- [ ] [NORM-012] Remove obvious copy artifacts via configurable pattern set.
- [ ] [NORM-013] Normalize em-dash dialogue style.
- [ ] [NORM-014] Implement best-effort quote mismatch repair.
- [ ] [NORM-015] Emit warning when quote repair confidence is low.
- [ ] [NORM-016] Store original text snapshot per chapter.
- [ ] [NORM-017] Store normalized text snapshot per chapter.
- [ ] [NORM-018] Create original->normalized offset map (chapter granularity).
- [ ] [NORM-019] Create original->normalized offset map (segment granularity).
- [ ] [NORM-020] Emit normalization report with counts and lossy-transformation flags.
- [ ] [NORM-021] Add regression tests for noisy OCR-like input and quote mismatch edge cases.

## 4.3 Character and Entity Extraction (Ref: SRS.md §4.3)
- [ ] [CHAR-001] Expand character schema: `name`, `verbalized_form`, `gender`, `aliases[]`, `notes`, `source`, `confidence`.
- [ ] [CHAR-002] Keep PoC JSON/CSV import backward-compatible with new schema.
- [ ] [CHAR-003] Implement manual row add/edit/delete UI for character map.
- [ ] [CHAR-004] Add auto-extraction job for candidate character names.
- [ ] [CHAR-005] Store extraction confidence and source trace for each candidate.
- [ ] [CHAR-006] Add optional web-scrape ingestion with explicit warning acknowledgement.
- [ ] [CHAR-007] Normalize and merge user-uploaded + auto + scraped candidates.
- [ ] [CHAR-008] Implement canonical-name merge suggestions.
- [ ] [CHAR-009] Create review screen for proposed characters.
- [ ] [CHAR-010] Create approve/reject actions per proposed character.
- [ ] [CHAR-011] Add “Finalize character map” gate action.
- [ ] [CHAR-012] Prevent downstream runs from using unfinalized proposed set unless override enabled.
- [ ] [CHAR-013] Implement alias list storage per character.
- [ ] [CHAR-014] Implement alias->canonical lookup service.
- [ ] [CHAR-015] Add alias collision detector when alias maps to multiple canonicals.
- [ ] [CHAR-016] Implement per-chapter mention counter.
- [ ] [CHAR-017] Compute first appearance chapter index.
- [ ] [CHAR-018] Compute last appearance chapter index.
- [ ] [CHAR-019] Compute mentions per 1,000 words metric.
- [ ] [CHAR-020] Compute dialogue line counts where speaker attribution exists.
- [ ] [CHAR-021] Add API endpoint for character occurrence analytics.
- [ ] [CHAR-022] Add tests for merge, alias conflict, and finalize workflow.

## 4.4 Gender Tagging and Ambiguity (Ref: SRS.md §4.4)
- [ ] [GEN-001] Restrict gender values to `male/female/neutral/unknown/custom`.
- [ ] [GEN-002] Add DB constraint/validation for permitted values.
- [ ] [GEN-003] Treat manual gender as authoritative in resolver logic.
- [ ] [GEN-004] Implement optional gender inference module.
- [ ] [GEN-005] Persist inferred gender + confidence + evidence trace.
- [ ] [GEN-006] Add manual/inferred comparison service.
- [ ] [GEN-007] Add contradiction severity score.
- [ ] [GEN-008] Add threshold config for contradiction review requirement.
- [ ] [GEN-009] Block final export only when contradiction threshold rule requires review.
- [ ] [GEN-010] Implement unknown/neutral fallback mapping to neutral/unknown voice bucket.
- [ ] [GEN-011] Ensure unknown gender never hard-fails export.
- [ ] [GEN-012] Emit low/undefined confidence in export for unknown gender.
- [ ] [GEN-013] Mark dependent outputs stale when gender is edited.
- [ ] [GEN-014] Trigger voice preview recomputation after gender edits.
- [ ] [GEN-015] Add test cases for manual override precedence.
- [ ] [GEN-016] Add test cases for contradiction flags and export gating.

## 4.5 Pronunciation and Verbalization (Ref: SRS.md §4.5)
- [ ] [VERB-001] Enforce canonical name + verbalized form as required fields.
- [ ] [VERB-002] Add pronunciation dictionary table for non-character terms.
- [ ] [VERB-003] Support global scope term overrides.
- [ ] [VERB-004] Support per-character scope term overrides.
- [ ] [VERB-005] Implement before/after substitution preview endpoint.
- [ ] [VERB-006] Build UI preview panel for pronunciation checks.
- [ ] [VERB-007] Implement whole-word matching mode.
- [ ] [VERB-008] Implement case sensitivity toggle.
- [ ] [VERB-009] Implement alias-aware substitution mode.
- [ ] [VERB-010] Emit warnings for ambiguous replacement candidates.
- [ ] [VERB-011] Support place-name verbalizations.
- [ ] [VERB-012] Support artifact terminology verbalizations.
- [ ] [VERB-013] Support invented word verbalizations.
- [ ] [VERB-014] Add tests for false positive replacement prevention.

## 4.6 Segmentation for TTS and Analysis (Ref: SRS.md §4.6)
- [ ] [SEG-001] Add chapter->paragraph segmentation layer.
- [ ] [SEG-002] Add paragraph->sentence segmentation layer.
- [ ] [SEG-003] Add dialogue block detector.
- [ ] [SEG-004] Add narration block detector.
- [ ] [SEG-005] Implement audiobook max target length config.
- [ ] [SEG-006] Implement hard max segment length ceiling.
- [ ] [SEG-007] Add intelligibility heuristic to avoid random mid-thought splits.
- [ ] [SEG-008] Prefer punctuation boundaries when splitting.
- [ ] [SEG-009] Avoid split inside quoted utterance where possible.
- [ ] [SEG-010] Add abbreviation/initial-aware split protection.
- [ ] [SEG-011] Add metadata: chapter id.
- [ ] [SEG-012] Add metadata: segment index.
- [ ] [SEG-013] Add metadata: original span pointer.
- [ ] [SEG-014] Add metadata: normalized text.
- [ ] [SEG-015] Add metadata: phonetic-ready text.
- [ ] [SEG-016] Add metadata: parent paragraph reference.
- [ ] [SEG-017] Add metadata: parent sentence reference.
- [ ] [SEG-018] Implement chapter reconstruction from segments.
- [ ] [SEG-019] Implement corpus reconstruction from chapter artifacts.
- [ ] [SEG-020] Add round-trip audit test (reconstructed text consistency).

## 4.7 Tagging System (Ref: SRS.md §4.7)
- [ ] [TAG-001] Implement structural type tag set (`narration/dialogue/internal thought/mixed/description/action`).
- [ ] [TAG-002] Implement speaker attribution output (`speaker_id`, confidence).
- [ ] [TAG-003] Implement emotion outputs (`valence`, `intensity`, primary label, secondary label, confidence).
- [ ] [TAG-004] Implement shift marker detector scaffolding.
- [ ] [TAG-005] Implement tension contribution tag per segment.
- [ ] [TAG-006] Implement dominance contribution tag per segment.
- [ ] [TAG-007] Detect emotion shift within a segment.
- [ ] [TAG-008] Detect narration<->internal thought shift.
- [ ] [TAG-009] Detect internal<->external speech shift.
- [ ] [TAG-010] Add tone reversal/dark irony marker when triggered.
- [ ] [TAG-011] Create sub-segment boundary records on shift.
- [ ] [TAG-012] Store sub-segment tags independently.
- [ ] [TAG-013] Store parent segment summary tag (dominant tone/state).
- [ ] [TAG-014] Add confidence field for every tag category.
- [ ] [TAG-015] Add evidence pointer store for every tag category.
- [ ] [TAG-016] Add explicit `unknown/uncertain` states for low confidence.
- [ ] [TAG-017] Build optional review UI for speaker tags.
- [ ] [TAG-018] Build optional review UI for emotional peaks/troughs.
- [ ] [TAG-019] Build optional review UI for low-confidence regions.
- [ ] [TAG-020] Ensure pipeline can run fully without any manual review step.
- [ ] [TAG-021] Add evaluation fixtures for rapid emotional shifts.
- [ ] [TAG-022] Add evaluation fixtures for mixed narration/dialogue segments.

## 4.8 Voice Mapping (Ref: SRS.md §4.8)
- [ ] [VOICE-001] Add voice map table with per-character assignment.
- [ ] [VOICE-002] Add default narrator voice field.
- [ ] [VOICE-003] Add default male/female/neutral/unknown voice fields.
- [ ] [VOICE-004] Add per-character override field and precedence rule.
- [ ] [VOICE-005] Implement resolver output for each dialogue segment.
- [ ] [VOICE-006] Include `resolved_voice_id` in export.
- [ ] [VOICE-007] Include `speaker_id` used in resolution in export.
- [ ] [VOICE-008] Include gender used for resolution in export.
- [ ] [VOICE-009] Include speaker+gender confidence in export.
- [ ] [VOICE-010] Implement internal-thought voice policy options.
- [ ] [VOICE-011] Persist selected thought policy in mode setup.
- [ ] [VOICE-012] Add tests for every fallback path.

## 4.9 Audiobook Outputs (Ref: SRS.md §4.9)
- [ ] [AUD-001] Define audiobook export package manifest structure.
- [ ] [AUD-002] Include ordered segment list for entire corpus.
- [ ] [AUD-003] Include phonetic-ready text per segment.
- [ ] [AUD-004] Include per-segment voice resolution outputs.
- [ ] [AUD-005] Include per-segment tag bundle and confidence.
- [ ] [AUD-006] Include project config snapshot in export package.
- [ ] [AUD-007] Include logs/reports in export package.
- [ ] [AUD-008] Implement JSON export writer.
- [ ] [AUD-009] Implement CSV export writer.
- [ ] [AUD-010] Implement time-series export arrays.
- [ ] [AUD-011] Enforce stable chapter->segment ordering.
- [ ] [AUD-012] Implement resumable export by chapter/segment cursor.
- [ ] [AUD-013] Guarantee stable segment IDs across equivalent reruns.
- [ ] [AUD-014] Emit emotional delta metadata between adjacent segments.
- [ ] [AUD-015] Emit scene state and volatility markers.
- [ ] [AUD-016] Emit “avoid abrupt change” smoothing hints while preserving raw tags.

## 4.10 Academic Outputs (Ref: SRS.md §4.10)
- [ ] [ACAD-001] Compute chapter-level valence mean.
- [ ] [ACAD-002] Compute chapter-level valence variance.
- [ ] [ACAD-003] Compute emotional volatility index.
- [ ] [ACAD-004] Compute rolling-window emotional curves.
- [ ] [ACAD-005] Compute raw tension per chapter.
- [ ] [ACAD-006] Compute smoothed tension curve.
- [ ] [ACAD-007] Detect and mark minor/major tension peaks.
- [ ] [ACAD-008] Detect and mark plateau regions.
- [ ] [ACAD-009] Compute chapter-level character dominance for key characters.
- [ ] [ACAD-010] Build character co-occurrence graph nodes/edges.
- [ ] [ACAD-011] Compute graph centrality metrics table.
- [ ] [ACAD-012] Implement academic JSON export schema.
- [ ] [ACAD-013] Implement academic CSV export schema.
- [ ] [ACAD-014] Implement graph JSON export schema.
- [ ] [ACAD-015] Include reproducible run snapshot in academic exports.
- [ ] [ACAD-016] Implement multi-novel workspace comparison model.
- [ ] [ACAD-017] Implement aligned curve comparison view data.
- [ ] [ACAD-018] Implement normalized pacing signature comparison data.
- [ ] [ACAD-019] Implement comparative dataset export.
- [ ] [ACAD-020] Add tests using at least two corpora for comparison correctness.

## 4.11 Author Outputs (Ref: SRS.md §4.11)
- [ ] [AUTH-001] Define narrative health report schema.
- [ ] [AUTH-002] Implement tension flatline detector.
- [ ] [AUTH-003] Implement emotional monotony detector.
- [ ] [AUTH-004] Implement over-dominant character warning detector.
- [ ] [AUTH-005] Implement disappearing character warning detector.
- [ ] [AUTH-006] Implement dialogue density anomaly detector.
- [ ] [AUTH-007] Define actionable flag schema (`location`, `trigger_metric`, `severity`, `evidence`).
- [ ] [AUTH-008] Implement chapter-range locator for each flag.
- [ ] [AUTH-009] Implement severity scoring for each flag.
- [ ] [AUTH-010] Attach evidence trace to each flag.
- [ ] [AUTH-011] Implement chapter type classifier (`setup/build-up/confrontation/resolution/transitional`).
- [ ] [AUTH-012] Output confidence for chapter type classification.
- [ ] [AUTH-013] Output reasons/features used for each chapter type.
- [ ] [AUTH-014] Build author-mode report export endpoint.
- [ ] [AUTH-015] Add test fixtures for each warning type.

## 4.12 LLM Routing and Quota (Ref: SRS.md §4.12)
- [ ] [LLM-001] Add LLM usage feature flag per project.
- [ ] [LLM-002] Enumerate supported task types (`emotion_refinement`, `speaker_resolution`, etc.).
- [ ] [LLM-003] Enforce rule-based first pass before LLM escalation.
- [ ] [LLM-004] Add confidence-threshold trigger for escalation.
- [ ] [LLM-005] Add ambiguity-flag trigger for escalation.
- [ ] [LLM-006] Add user “deep semantic refinement” opt-in trigger.
- [ ] [LLM-007] Add provider registry entries for SiliconFlow.
- [ ] [LLM-008] Add provider registry entries for Groq.
- [ ] [LLM-009] Add provider registry entries for OpenRouter.
- [ ] [LLM-010] Add per-provider request count tracking.
- [ ] [LLM-011] Add estimated token usage tracking.
- [ ] [LLM-012] Add last known rate-limit status tracking.
- [ ] [LLM-013] Add last successful call timestamp tracking.
- [ ] [LLM-014] Add last reset timestamp tracking if available.
- [ ] [LLM-015] Stop calls on provider rate-limit/quota error.
- [ ] [LLM-016] Mark provider temporarily unavailable after hard limit events.
- [ ] [LLM-017] Resume provider usage after reset detection or manual enable.
- [ ] [LLM-018] Add explicit guardrails: no bypass/circumvention behaviors.
- [ ] [LLM-019] Add multiple API key support per provider.
- [ ] [LLM-020] Add provider priority ordering config.
- [ ] [LLM-021] Add manual provider enable/disable toggles.
- [ ] [LLM-022] Implement failover to next provider when one is unavailable.
- [ ] [LLM-023] Add deterministic mode logs: provider/model/timestamp/token usage.
- [ ] [LLM-024] Add tests for quota exhaustion and recovery behavior.

## 4.12.6 Caching (Ref: SRS.md §4.12.6)
- [ ] [CACHE-001] Add LLM cache table keyed by input text hash.
- [ ] [CACHE-002] Include task type in cache key.
- [ ] [CACHE-003] Include configuration snapshot ID in cache key.
- [ ] [CACHE-004] Include model identifier in cache key.
- [ ] [CACHE-005] Return cached result without provider call on exact key hit.
- [ ] [CACHE-006] Track cache hit/miss metrics per task type.
- [ ] [CACHE-007] Add cache invalidation policy docs.
- [ ] [CACHE-008] Add tests for exact hit and near-miss behavior.

## 4.12.7 Deterministic Mode (Ref: SRS.md §4.12.7)
- [ ] [DET-001] Add deterministic mode flag to run config.
- [ ] [DET-002] Force deterministic processing order across all stages.
- [ ] [DET-003] Pin model identifier/version in deterministic runs.
- [ ] [DET-004] Persist deterministic seed and randomization config.
- [ ] [DET-005] Add repeat-run equivalence tests for deterministic mode.
- [ ] [DET-006] Emit explicit warning when provider nondeterminism may break exact replay.

## 4.13 Provider Abstraction Layer (Ref: SRS.md §4.13)
- [ ] [PAL-001] Define `LLMRouter` as sole provider access point.
- [ ] [PAL-002] Implement provider selector using availability+quota+priority.
- [ ] [PAL-003] Implement dispatch and response parser abstraction.
- [ ] [PAL-004] Implement failure classification (`rate_limit`, `quota`, `timeout`, `service_unavailable`, `other`).
- [ ] [PAL-005] Implement retry policy by error class.
- [ ] [PAL-006] Implement failover handoff to next provider.
- [ ] [PAL-007] Add usage metrics logging hooks in router.
- [ ] [PAL-008] Define standardized request object fields exactly per SRS.
- [ ] [PAL-009] Enforce request validation for required fields.
- [ ] [PAL-010] Define standardized response object fields exactly per SRS.
- [ ] [PAL-011] Enforce response validation and error mapping.
- [ ] [PAL-012] Ensure core modules never import provider SDKs directly.
- [ ] [PAL-013] Add architecture test to detect forbidden direct provider imports.
- [ ] [PAL-014] Add extension interface for self-hosted local models.
- [ ] [PAL-015] Add extension interface for user-supplied provider keys.
- [ ] [PAL-016] Add per-project provider configuration support.

## 5. Visualization Requirements (Ref: SRS.md §5)
- [ ] [VR-001] Define chart data contracts for tension graph.
- [ ] [VR-002] Implement tension graph API payload endpoint.
- [ ] [VR-003] Add smoothing toggle for tension graph display.
- [ ] [VR-004] Add peak markers and plateau overlays to tension graph.
- [ ] [VR-005] Define chart data contracts for emotional polarity graph.
- [ ] [VR-006] Implement polarity graph API payload endpoint.
- [ ] [VR-007] Add rolling-window control for polarity graph.
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
- [ ] [DR-011] Persist deterministic seed settings per run.
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

---

## Suggested Execution Order (for new sessions)
1. Foundations: `GLS-*`, `INT-*`, `USE-*`, `MODE-*`.
2. Core pipeline: `ING-*`, `NORM-*`, `CHAR-*`, `GEN-*`, `VERB-*`, `SEG-*`, `TAG-*`, `VOICE-*`.
3. Mode outputs: `AUD-*`, `ACAD-*`, `AUTH-*`.
4. LLM platform: `LLM-*`, `CACHE-*`, `DET-*`, `PAL-*`.
5. Visualization and persistence: `VR-*`, `DR-*`.
6. Operational hardening: `NFR*`, `ER-*`, `CFG-*`, `X-*`.
7. Release gates: `MVP-*`, `ACC-*`.
