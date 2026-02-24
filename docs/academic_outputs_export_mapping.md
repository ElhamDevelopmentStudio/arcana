# Academic Researcher Outputs and Export Formats Mapping

Reference sources:
- [SRS.md](/Users/elhamdev/work/nipe/SRS.md) sections `### 2.1 Personas` and `### 2.2 Primary Use Cases`
- [SRS_Expanded_Implementation_Checklist.md](/Users/elhamdev/work/nipe/SRS_Expanded_Implementation_Checklist.md) item `USE-003`
- [persona_end_to_end_flows.md](/Users/elhamdev/work/nipe/docs/persona_end_to_end_flows.md) flow `FLOW-ACADEMIC-001`

Purpose:
- Map the Academic Researcher flow to concrete analysis outputs and export formats.
- Keep output contracts explicit for downstream research and reproducibility workflows.

## USE-003 Academic Outputs and Export Formats Mapping

### Output 01: Emotion Metrics Time Series
- output_id: AO-001
- source_flow_id: FLOW-ACADEMIC-001
- output_name: chapter_emotion_metrics_series
- purpose: Provide chapter-level emotional metrics for curve analysis and comparison.
- export_formats: json, csv, time_series_json
- expected_consumer: research_notebook_and_statistical_tools

### Output 02: Tension Curve Summary
- output_id: AO-002
- source_flow_id: FLOW-ACADEMIC-001
- output_name: chapter_tension_curve_summary
- purpose: Expose tension progression with peak/plateau markers for narrative structure analysis.
- export_formats: json, csv, time_series_json
- expected_consumer: narrative_structure_analysis_tools

### Output 03: Character Dominance Time Series
- output_id: AO-003
- source_flow_id: FLOW-ACADEMIC-001
- output_name: character_dominance_series
- purpose: Track dominance contribution trends across the corpus timeline.
- export_formats: json, csv, time_series_json
- expected_consumer: character_balance_and_dominance_analysis

### Output 04: Character Co-occurrence Graph
- output_id: AO-004
- source_flow_id: FLOW-ACADEMIC-001
- output_name: character_cooccurrence_graph
- purpose: Represent character relationship structure for graph/network analysis.
- export_formats: graph_json, csv
- expected_consumer: network_graph_analysis_tools

### Output 05: Comparative Run Metrics Snapshot
- output_id: AO-005
- source_flow_id: FLOW-ACADEMIC-001
- output_name: comparative_run_metrics_snapshot
- purpose: Enable cross-run reproducibility checks and quantitative comparison.
- export_formats: json, csv
- expected_consumer: reproducibility_and_comparison_workflows

### Output 06: Academic Export Manifest
- output_id: AO-006
- source_flow_id: FLOW-ACADEMIC-001
- output_name: academic_export_manifest
- purpose: Provide machine-readable inventory and provenance for all generated academic outputs.
- export_formats: json
- expected_consumer: pipeline_orchestration_and_archive_indexing
