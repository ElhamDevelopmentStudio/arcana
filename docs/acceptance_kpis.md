# NIPE Acceptance KPIs

Reference sources:
- [SRS.md](/Users/elhamdev/work/nipe/SRS.md) section `### 1.3 Success Criteria (Product-Level)`
- [SRS_Expanded_Implementation_Checklist.md](/Users/elhamdev/work/nipe/SRS_Expanded_Implementation_Checklist.md) items `INT-005`, `INT-006`, `INT-007`, `INT-008`

Purpose:
- Define concrete acceptance KPIs for product-level success criteria.
- Keep KPI definitions implementation-ready and verifiable.

## KPI-001 Clean Chapterized Corpus Verification

- linked_success_criterion: SC-001
- srs_success_text: a clean chapterized corpus
- minimum_chapter_count: >= 1
- chapter_index_contiguity_rate: = 1.00
- empty_chapter_count: = 0
- unassigned_text_ratio: <= 0.01
- rerun_chapter_count_delta_same_input_config: = 0
- verification_artifacts_required: run_summary_json, chapter_index_report, rerun_diff_report

## KPI-002 Validated Character Map Verification

- linked_success_criterion: SC-002
- srs_success_text: a validated character map (name -> verbalized -> gender)
- required_fields_per_character: name, verbalized_form, gender
- required_field_completeness_rate: = 1.00
- duplicate_canonical_name_count: = 0
- unresolved_alias_conflict_count: = 0
- invalid_gender_value_count: = 0
- rerun_character_count_delta_same_input_config: = 0
- verification_artifacts_required: character_map_export_json, character_validation_report, rerun_diff_report

## KPI-003 TTS-Ready Tagged Export Verification

- linked_success_criterion: SC-003
- srs_success_text: a segmented, phonetic-normalized, tagged export suitable to feed into a TTS pipeline
- max_segment_length_compliance_rate: = 1.00
- phonetic_text_presence_rate: = 1.00
- required_tag_fields: type, speaker, gender, voice_id, emotion_valence, emotion_intensity
- required_tag_fields_presence_rate: = 1.00
- voice_resolution_presence_rate: = 1.00
- export_schema_validation_pass_rate: = 1.00
- rerun_export_segment_delta_same_input_config: = 0
- verification_artifacts_required: export_json, export_schema_validation_report, segment_length_report, rerun_diff_report

## KPI-004 Basic Time-Series and Charts Verification

- linked_success_criterion: SC-004
- srs_success_text: basic tension/emotion/dominance time-series and charts
- emotion_series_coverage_rate: = 1.00
- tension_series_coverage_rate: = 1.00
- dominance_series_coverage_rate: = 1.00
- chart_render_success_rate: = 1.00
- series_ordering_consistency_rate: = 1.00
- series_export_schema_validation_pass_rate: = 1.00
- rerun_series_point_delta_same_input_config: = 0
- verification_artifacts_required: emotion_series_export_json, tension_series_export_json, dominance_series_export_json, chart_render_report, rerun_diff_report
