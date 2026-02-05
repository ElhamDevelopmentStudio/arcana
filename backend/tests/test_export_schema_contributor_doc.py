import subprocess
import sys
from pathlib import Path

from app.export_schema_contributor_doc_validation import (
    REQUIRED_STEP_TITLES,
    extract_export_schema_contributor_section,
    parse_step_items,
    validate_export_schema_contributor_guide,
)

ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = ROOT / "docs" / "contributor_evolve_export_schema_safely.md"
VALIDATION_SCRIPT_PATH = ROOT / "backend" / "scripts_validate_export_schema_contributor_doc.py"

EXPECTED_STEP_TITLES = [
    "Define change scope and compatibility strategy",
    "Version schema and keep parser-safe defaults",
    "Update backend manifest/export builders",
    "Update frontend schema guards and consumers",
    "Add regression fixtures and contract coverage",
    "Document migration notes and run local smoke",
]


def test_unit_extract_and_parse_export_schema_steps() -> None:
    sample = """
## Contributor Guide: How to evolve export schema safely
### Step 1: Define change scope and compatibility strategy
- objective: Define compatibility.
- files: backend/app/schemas.py
- checks: requirement mapping
### Step 2: Version schema and keep parser-safe defaults
- objective: Add schema versioning.
- files: backend/app/services/export.py
- checks: parser compatibility tests
"""
    section = extract_export_schema_contributor_section(sample)
    items = parse_step_items(section)
    assert len(items) == 2
    assert items[0]["number"] == 1
    assert items[1]["title"] == "Version schema and keep parser-safe defaults"


def test_integration_export_schema_contributor_doc_has_required_steps() -> None:
    stats = validate_export_schema_contributor_guide(DOC_PATH)
    assert stats["steps"] >= len(REQUIRED_STEP_TITLES)
    assert stats["required_fields"] == 3


def test_e2e_export_schema_contributor_doc_validation_cli_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATION_SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    assert "Contributor export-schema guide validation succeeded" in result.stdout


def test_regression_export_schema_step_titles_snapshot() -> None:
    markdown = DOC_PATH.read_text(encoding="utf-8")
    items = parse_step_items(extract_export_schema_contributor_section(markdown))
    titles = [str(item["title"]) for item in items]
    assert titles == EXPECTED_STEP_TITLES
