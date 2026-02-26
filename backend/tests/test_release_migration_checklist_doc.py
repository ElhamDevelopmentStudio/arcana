import subprocess
import sys
from pathlib import Path

from app.release_migration_checklist_validation import (
    REQUIRED_ITEM_TITLES,
    extract_release_checklist_section,
    parse_checklist_items,
    validate_release_migration_checklist,
)

ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = ROOT / "docs" / "release_migration_backward_compatibility_checklist.md"
VALIDATION_SCRIPT_PATH = ROOT / "backend" / "scripts_validate_release_migration_checklist.py"

EXPECTED_ITEM_TITLES = [
    "Catalog schema and data-change impact",
    "Validate migration ordering and idempotence assumptions",
    "Define compatibility window and fallback behavior",
    "Execute contract and regression coverage for changed surfaces",
    "Capture rollout and rollback readiness",
    "Perform post-release verification and closeout",
]


def test_unit_extract_and_parse_release_checklist_items() -> None:
    sample = """
## Release Checklist: Data migrations and backward compatibility
### Item 1: Catalog schema and data-change impact
- objective: Map impact.
- actions: Enumerate migrations.
- evidence: Review notes.
### Item 2: Validate migration ordering and idempotence assumptions
- objective: Verify ordering.
- actions: Run migration path checks.
- evidence: Migration logs.
"""
    section = extract_release_checklist_section(sample)
    items = parse_checklist_items(section)
    assert len(items) == 2
    assert items[0]["number"] == 1
    assert items[1]["title"] == "Validate migration ordering and idempotence assumptions"


def test_integration_release_checklist_has_required_items() -> None:
    stats = validate_release_migration_checklist(DOC_PATH)
    assert stats["items"] >= len(REQUIRED_ITEM_TITLES)
    assert stats["required_fields"] == 3


def test_e2e_release_checklist_validation_cli_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATION_SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    assert "Release migration checklist validation succeeded" in result.stdout


def test_regression_release_checklist_item_titles_snapshot() -> None:
    markdown = DOC_PATH.read_text(encoding="utf-8")
    items = parse_checklist_items(extract_release_checklist_section(markdown))
    titles = [str(item["title"]) for item in items]
    assert titles == EXPECTED_ITEM_TITLES
