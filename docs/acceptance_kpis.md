# NIPE Acceptance KPIs

Reference sources:
- [SRS.md](/Users/elhamdev/work/nipe/SRS.md) section `### 1.3 Success Criteria (Product-Level)`
- [SRS_Expanded_Implementation_Checklist.md](/Users/elhamdev/work/nipe/SRS_Expanded_Implementation_Checklist.md) item `INT-005`

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
