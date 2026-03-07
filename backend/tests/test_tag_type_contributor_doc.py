import subprocess
import sys
from pathlib import Path

from app.tag_type_contributor_doc_validation import (
    REQUIRED_STEP_TITLES,
    extract_contributor_tag_type_section,
    parse_step_items,
    validate_contributor_tag_type_guide,
)

ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = ROOT / "docs" / "contributor_add_tag_type.md"
VALIDATION_SCRIPT_PATH = ROOT / "backend" / "scripts_validate_tag_type_contributor_doc.py"

EXPECTED_STEP_TITLES = [
    "Define the tag contract",
    "Implement backend tagging logic",
    "Propagate the tag through export and run payloads",
    "Expose frontend contract and UX surfaces",
    "Add fixtures and automated regression coverage",
    "Document rollout and run local smoke",
]


def test_unit_extract_and_parse_tag_type_contributor_steps() -> None:
    sample = """
## Contributor Guide: How to add a new tag type
### Step 1: Define the tag contract
- objective: Define contract.
- files: backend/app/schemas.py
- checks: schema tests
### Step 2: Implement backend tagging logic
- objective: Implement service logic.
- files: backend/app/services/tagging.py
- checks: unit tests
"""
    section = extract_contributor_tag_type_section(sample)
    items = parse_step_items(section)
    assert len(items) == 2
    assert items[0]["number"] == 1
    assert items[1]["title"] == "Implement backend tagging logic"


def test_integration_tag_type_contributor_doc_has_required_steps() -> None:
    stats = validate_contributor_tag_type_guide(DOC_PATH)
    assert stats["steps"] >= len(REQUIRED_STEP_TITLES)
    assert stats["required_fields"] == 3


def test_e2e_tag_type_contributor_doc_validation_cli_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATION_SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    assert "Contributor tag-type guide validation succeeded" in result.stdout


def test_regression_tag_type_contributor_step_titles_snapshot() -> None:
    markdown = DOC_PATH.read_text(encoding="utf-8")
    items = parse_step_items(extract_contributor_tag_type_section(markdown))
    titles = [str(item["title"]) for item in items]
    assert titles == EXPECTED_STEP_TITLES
