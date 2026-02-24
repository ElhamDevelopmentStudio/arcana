import subprocess
import sys
from pathlib import Path

from app.community_reader_flow_validation import (
    REQUIRED_DASHBOARD_FOCUS,
    extract_use_005_section,
    parse_steps,
    validate_use_005_flow,
)

ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = ROOT / "docs" / "community_reader_readonly_dashboard_flow.md"
VALIDATION_SCRIPT_PATH = ROOT / "backend" / "scripts_validate_community_reader_flow.py"

EXPECTED_STEP_TITLES = [
    "Open Published Project Dashboard",
    "Review Chapter-Level Narrative Trends",
    "Review Character Trend Views",
    "Explore Emotion/Tension/Dominance Curves",
    "Apply Arc and Chapter Filters",
    "Export Read-Only Insight Snapshot",
]


def test_unit_extract_and_parse_steps() -> None:
    sample = """
## USE-005 Community Reader Read-Only Dashboard Flow
### Step 01: A
- flow_id: FLOW-COMMUNITY-001
- ui_view: v_a
- user_action: action_a
- dashboard_focus: project_summary
- read_only_guardrail: no create/update/delete operations allowed
- expected_outcome: outcome_a
### Step 02: B
- flow_id: FLOW-COMMUNITY-001
- ui_view: v_b
- user_action: action_b
- dashboard_focus: chapter_trends
- read_only_guardrail: no create/update/delete operations allowed
- expected_outcome: outcome_b
"""
    section = extract_use_005_section(sample)
    steps = parse_steps(section)
    assert len(steps) == 2
    assert steps[0]["number"] == 1
    assert steps[1]["fields"]["ui_view"] == "v_b"


def test_integration_use_005_flow_contains_required_focus_coverage() -> None:
    stats = validate_use_005_flow(DOC_PATH)
    assert stats["steps"] >= 6
    assert stats["focus_coverage"] >= len(REQUIRED_DASHBOARD_FOCUS)


def test_e2e_community_reader_flow_validation_cli_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATION_SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    assert "Community reader flow validation succeeded" in result.stdout


def test_regression_step_title_snapshot() -> None:
    markdown = DOC_PATH.read_text(encoding="utf-8")
    steps = parse_steps(extract_use_005_section(markdown))
    titles = [step["title"] for step in steps]
    assert titles == EXPECTED_STEP_TITLES
