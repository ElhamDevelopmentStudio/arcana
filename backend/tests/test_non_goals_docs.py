import subprocess
import sys
from pathlib import Path

from app.non_goals_validation import extract_non_goals_section, load_non_goals, parse_non_goal_items
from app.scope_validation import load_and_parse_scope

ROOT = Path(__file__).resolve().parents[2]
SRS_PATH = ROOT / "SRS.md"
NON_GOALS_DOC_PATH = ROOT / "docs" / "non_goals.md"
VALIDATION_SCRIPT_PATH = ROOT / "backend" / "scripts_validate_non_goals.py"

EXPECTED_NON_GOALS = [
    "rewrite or generate new story text",
    "produce final audio output directly (optional integration later, but not required in v1)",
    "claim emotional labels are ground-truth",
    "require manual per-chapter labeling",
]


def test_unit_extract_non_goals_section_stops_at_next_h2() -> None:
    sample = """
# Sample
## Explicit Non-Goals
- a
- b
## Next Heading
- c
"""
    section = extract_non_goals_section(sample)
    assert "- a" in section
    assert "- b" in section
    assert "- c" not in section


def test_unit_parse_non_goal_items_extracts_bullets() -> None:
    sample = """
- one
- two
"""
    items = parse_non_goal_items(sample)
    assert items == ["one", "two"]


def test_integration_non_goals_match_srs_shall_not() -> None:
    srs_non_goals = load_and_parse_scope(SRS_PATH, already_scope_section=False)["shall_not"]
    docs_non_goals = load_non_goals(NON_GOALS_DOC_PATH)
    assert docs_non_goals == srs_non_goals


def test_e2e_non_goals_validation_cli_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATION_SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    assert "Non-goals validation succeeded" in result.stdout


def test_regression_non_goals_snapshot() -> None:
    docs_non_goals = load_non_goals(NON_GOALS_DOC_PATH)
    assert docs_non_goals == EXPECTED_NON_GOALS
