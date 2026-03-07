import subprocess
import sys
from pathlib import Path

from app.release_rollback_plan_validation import (
    REQUIRED_SECTION_TITLES,
    extract_rollback_plan_section,
    parse_rollback_sections,
    validate_release_rollback_plan,
)

ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = ROOT / "docs" / "release_rollback_plan_template.md"
VALIDATION_SCRIPT_PATH = ROOT / "backend" / "scripts_validate_release_rollback_plan.py"

EXPECTED_SECTION_TITLES = [
    "Release identification and blast radius",
    "Rollback triggers and decision thresholds",
    "Pre-rollback safeguards and backups",
    "Step-by-step rollback execution commands",
    "Post-rollback verification checklist",
    "Incident log, communications, and follow-up actions",
]


def test_unit_extract_and_parse_rollback_plan_sections() -> None:
    sample = """
## Rollback Plan Template
### Section 1: Release identification and blast radius
- objective: Identify release.
- required_inputs: version and owners.
- completion_criteria: scope is clear.
### Section 2: Rollback triggers and decision thresholds
- objective: define triggers.
- required_inputs: thresholds.
- completion_criteria: decision criteria exist.
"""
    section = extract_rollback_plan_section(sample)
    items = parse_rollback_sections(section)
    assert len(items) == 2
    assert items[0]["number"] == 1
    assert items[1]["title"] == "Rollback triggers and decision thresholds"


def test_integration_rollback_plan_doc_has_required_sections() -> None:
    stats = validate_release_rollback_plan(DOC_PATH)
    assert stats["sections"] >= len(REQUIRED_SECTION_TITLES)
    assert stats["required_fields"] == 3


def test_e2e_rollback_plan_validation_cli_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATION_SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    assert "Release rollback plan validation succeeded" in result.stdout


def test_regression_rollback_plan_section_titles_snapshot() -> None:
    markdown = DOC_PATH.read_text(encoding="utf-8")
    items = parse_rollback_sections(extract_rollback_plan_section(markdown))
    titles = [str(item["title"]) for item in items]
    assert titles == EXPECTED_SECTION_TITLES
