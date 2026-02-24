# Reference Feature Overlap (Read-Only External Project)

Source reference folder:
- `for_reference_only_not_for_copying/`

Important:
- This document is a mapping aid only.
- `SRS.md` and `SRS_Expanded_Implementation_Checklist.md` remain the source of truth.
- Do not copy code from the reference folder; re-implement based on current requirements.

## Overlap Matrix

| Overlap feature in NIPE | SRS reference | Checklist reference | Reference pointers |
| --- | --- | --- | --- |
| TXT ingestion entrypoint | `FR-ING-2` | `ING-005` | `scripts/02_ingest_raw.py` |
| Encoding decode + UTF handling | `FR-ING-3` | `ING-009`, `ING-010` | `scripts/02_ingest_raw.py` |
| Chapter split by headers | `FR-NORM-1` | `NORM-001`, `NORM-002` | `src/ri_attr/chaptering.py` |
| Raw text normalization (BOM/newlines/blank runs) | `FR-NORM-3` | `NORM-007`, `NORM-011` | `src/ri_attr/chaptering.py` |
| Chapter file persistence | `FR-ING-1`, `DR-1` | `ING-001`, `NORM-017` | `src/ri_attr/chaptering.py`, `scripts/02_ingest_raw.py` |
| Sentence segmentation with char offsets | `FR-SEG-1` | `SEG-001`, `SEG-002`, `SEG-013` | `scripts/03_split_sentences.py` |
| Context windows from sentence stream | `FR-TAG-1` (structural context support) | `TAG-001` (supporting pipeline) | `scripts/04_build_windows.py` |
| Character map validation + alias normalization | `FR-CHAR-1`, `FR-CHAR-4` | `CHAR-001`, `CHAR-014`, `CHAR-015` | `scripts/01_prepare_name_map.py` |
| Alias->canonical/gender/speaker derived maps | `FR-CHAR-4`, `FR-GEN-1` | `CHAR-014`, `GEN-001` | `scripts/01_prepare_name_map.py` |
| Mode classification (narration/internal/dialogue) | `FR-TAG-1` | `TAG-001` | `scripts/06_train_mode.py`, `scripts/07_infer_mode.py` |
| Dialogue block assembly from predictions | `FR-TAG-1`, `FR-SEG-3` | `TAG-001`, `SEG-003` | `src/ri_attr/blocking.py`, `scripts/08_block_dialogue.py` |
| Gender resolution with evidence | `FR-GEN-3`, `FR-GEN-4` | `GEN-004`, `GEN-005`, `GEN-006` | `src/ri_attr/gender_resolve.py`, `scripts/09_resolve_gender.py` |
| Deterministic segment ID generation | `FR-SEG-4`, `FR-AUD-3` | `SEG-012`, `AUD-013` | `src/ri_attr/final_segments.py`, `src/ri_attr/span_segments.py` |
| Segment boundary rules (speaker switch/strong boundary/length caps) | `FR-SEG-2`, `FR-SEG-3` | `SEG-005`, `SEG-006`, `SEG-008`, `SEG-009` | `src/ri_attr/final_segments.py`, `src/ri_attr/span_segments.py` |
| Quote-aware split and sub-span generation | `FR-TAG-2`, `FR-TAG-3` | `TAG-008`, `TAG-011`, `TAG-012` | `src/ri_attr/span_segments.py` |
| Speaker role assignment across chains | `FR-TAG-1`, `FR-VOICE-2` | `TAG-002`, `VOICE-005` | `src/ri_attr/span_segments.py` |
| Turn boundary modeling (`TURN_START` etc.) | `FR-TAG-2` | `TAG-011` (supporting) | `scripts/23_build_turn_dataset.py`, `scripts/24_train_turn_classifier.py`, `scripts/25_infer_turns.py` |
| Heuristic emotion tagging | `FR-TAG-1` | `TAG-003` | `src/ri_attr/span_segments.py` |
| Emotion confidence policy/gating | `FR-TAG-4` | `TAG-014`, `TAG-016` | `src/ri_attr/span_segments.py` |
| LLM fallback for speaker assignment | `§4.12`, `§4.13` | `TAG-002`, `MODE/LLM later tasks` | `src/ri_attr/span_segments.py`, `src/ri_attr/director_llm.py`, `scripts/10_build_span_segments.py` |
| LLM emotion classification fallback | `§4.12`, `§4.13` | `TAG-003`, `TAG-014` | `src/ri_attr/span_segments.py`, `src/ri_attr/director_llm.py` |
| LLM provider abstraction + multi-provider router | `§4.12.2`, `§4.13.1` | `LLM router tasks` | `src/ri_attr/director_llm.py` |
| LLM quota-like control (max calls/token budgets) | `§4.12.4` | `quota tasks` | `src/ri_attr/director_llm.py` |
| LLM caching behavior | `§4.12.6` | `cache tasks` | `scripts/10_build_span_segments.py` |
| Pronunciation lexicon generation and merging | `FR-VERB-2`, `FR-VERB-5` | `VERB-002`, `VERB-011`, `VERB-012`, `VERB-013` | `scripts/12_build_pronunciation_lexicon.py`, `src/ri_attr/tts_generate.py` |
| Safe text substitution via regex/whole-word style matching | `FR-VERB-4` | `VERB-007`, `VERB-010`, `VERB-014` | `src/ri_attr/tts_generate.py` |
| Prosody rewrite suggestions and application | `FR-AUD-4` (smoothing support) | `AUD-016` | `scripts/15_suggest_prosody_rewrites.py`, `src/ri_attr/tts_generate.py` |
| Voice mapping defaults and fallback by gender/role | `FR-VOICE-1`, `FR-VOICE-2` | `VOICE-001`..`VOICE-006` | `src/ri_attr/tts_generate.py` |
| Preflight quality checks for segments | `NFR-2`, `ER-5` | `test/quality tasks` | `src/ri_attr/preflight.py`, `scripts/13_preflight_segments.py` |
| Regression benchmark set generation (transitions/emotions) | `FR-TAG-5`, `NFR-4` | `TAG-021`, `TAG-022` | `scripts/16_make_benchmarks.py` |
| Basic self-check automation | `NFR-2` | `smoke/regression tasks` | `scripts/14_self_check.py` |
| Audiobook generation pipeline (optional integration path) | `FR-AUD-1` (integration-adjacent) | later audiobook integration tasks | `scripts/11_generate_audio.py`, `src/ri_attr/tts_generate.py` |
| GPU safety and runtime controls | `NFR-1`, `NFR-2` | performance/reliability tasks | `src/ri_attr/gpu_safety.py` |

## Explicit Non-Truth Reminder

If a mapped behavior differs from NIPE requirements:
1. Follow `SRS.md`.
2. Follow `SRS_Expanded_Implementation_Checklist.md`.
3. Treat this mapping as implementation inspiration only.
