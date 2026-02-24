# Community Reader Read-Only Dashboard Flow

Reference sources:
- [SRS.md](/Users/elhamdev/work/nipe/SRS.md) sections `### 2.1 Personas` and `### 2.2 Primary Use Cases`
- [SRS_Expanded_Implementation_Checklist.md](/Users/elhamdev/work/nipe/SRS_Expanded_Implementation_Checklist.md) item `USE-005`
- [persona_end_to_end_flows.md](/Users/elhamdev/work/nipe/docs/persona_end_to_end_flows.md) flow `FLOW-COMMUNITY-001`

Purpose:
- Define a concrete read-only dashboard flow for the Community Reader persona.
- Enforce non-mutating exploration behavior with explicit guardrails.

## USE-005 Community Reader Read-Only Dashboard Flow

### Step 01: Open Published Project Dashboard
- flow_id: FLOW-COMMUNITY-001
- ui_view: community_dashboard_home
- user_action: Open an already processed project in community reader mode.
- dashboard_focus: project_summary
- read_only_guardrail: no create/update/delete operations allowed
- expected_outcome: Reader lands on dashboard views without edit controls.

### Step 02: Review Chapter-Level Narrative Trends
- flow_id: FLOW-COMMUNITY-001
- ui_view: chapter_trends_panel
- user_action: Inspect chapter-by-chapter trend summaries.
- dashboard_focus: chapter_trends
- read_only_guardrail: no create/update/delete operations allowed
- expected_outcome: Reader can browse chapter trend signals in read-only mode.

### Step 03: Review Character Trend Views
- flow_id: FLOW-COMMUNITY-001
- ui_view: character_trends_panel
- user_action: Explore character-level presence and relative activity trends.
- dashboard_focus: character_trends
- read_only_guardrail: no create/update/delete operations allowed
- expected_outcome: Reader can inspect character trend slices without modifying source data.

### Step 04: Explore Emotion/Tension/Dominance Curves
- flow_id: FLOW-COMMUNITY-001
- ui_view: narrative_curves_panel
- user_action: Navigate combined emotional, tension, and dominance curve visualizations.
- dashboard_focus: emotion_tension_dominance_curves
- read_only_guardrail: no create/update/delete operations allowed
- expected_outcome: Reader can zoom/filter visualization layers while preserving read-only access.

### Step 05: Apply Arc and Chapter Filters
- flow_id: FLOW-COMMUNITY-001
- ui_view: filter_controls_panel
- user_action: Apply non-persistent filters for arcs, chapters, and character slices.
- dashboard_focus: arc_filters
- read_only_guardrail: no create/update/delete operations allowed
- expected_outcome: Reader can focus on targeted narrative windows without changing stored project artifacts.

### Step 06: Export Read-Only Insight Snapshot
- flow_id: FLOW-COMMUNITY-001
- ui_view: insight_export_panel
- user_action: Download/share a read-only insight snapshot generated from existing artifacts.
- dashboard_focus: insight_export
- read_only_guardrail: no create/update/delete operations allowed
- expected_outcome: Reader can export or share read-only insights without triggering pipeline mutations.
