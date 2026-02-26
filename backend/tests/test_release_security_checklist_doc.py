import subprocess
import sys
from pathlib import Path

from app.release_security_checklist_validation import (
    REQUIRED_CONTROL_TITLES,
    extract_release_security_checklist_section,
    parse_security_controls,
    validate_release_security_checklist,
)

ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = ROOT / "docs" / "release_security_review_checklist.md"
VALIDATION_SCRIPT_PATH = ROOT / "backend" / "scripts_validate_release_security_checklist.py"

EXPECTED_CONTROL_TITLES = [
    "Threat model and scope revalidation",
    "Secrets and credential handling verification",
    "Authorization boundary and data isolation checks",
    "Dependency and supply-chain vulnerability review",
    "Security testing and abuse-case validation",
    "Security sign-off, incident readiness, and audit trail",
]


def test_unit_extract_and_parse_security_controls() -> None:
    sample = """
## Release Security Review Checklist
### Control 1: Threat model and scope revalidation
- objective: Revalidate threats.
- required_inputs: release impact map.
- completion_criteria: approved assumptions.
### Control 2: Secrets and credential handling verification
- objective: verify secret handling.
- required_inputs: secret inventory.
- completion_criteria: no exposed secrets.
"""
    section = extract_release_security_checklist_section(sample)
    items = parse_security_controls(section)
    assert len(items) == 2
    assert items[0]["number"] == 1
    assert items[1]["title"] == "Secrets and credential handling verification"


def test_integration_security_checklist_has_required_controls() -> None:
    stats = validate_release_security_checklist(DOC_PATH)
    assert stats["controls"] >= len(REQUIRED_CONTROL_TITLES)
    assert stats["required_fields"] == 3


def test_e2e_security_checklist_validation_cli_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATION_SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    assert "Release security checklist validation succeeded" in result.stdout


def test_regression_security_checklist_control_titles_snapshot() -> None:
    markdown = DOC_PATH.read_text(encoding="utf-8")
    items = parse_security_controls(extract_release_security_checklist_section(markdown))
    titles = [str(item["title"]) for item in items]
    assert titles == EXPECTED_CONTROL_TITLES
