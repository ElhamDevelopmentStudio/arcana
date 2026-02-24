import subprocess
import sys
from pathlib import Path

from app.author_diagnostic_map_validation import (
    REQUIRED_COVERAGE_CATEGORIES,
    extract_use_004_section,
    parse_requirement_items,
    validate_use_004_mapping,
)

ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = ROOT / "docs" / "author_diagnostic_requirements_mapping.md"
VALIDATION_SCRIPT_PATH = ROOT / "backend" / "scripts_validate_author_diagnostics_map.py"

EXPECTED_REQUIREMENT_IDS = ["ADR-001", "ADR-002", "ADR-003", "ADR-004", "ADR-005", "ADR-006"]


def test_unit_extract_and_parse_requirements() -> None:
    sample = """
## USE-004 Author Diagnostic Report Requirements Mapping
### Requirement 01: Item A
- requirement_id: ADR-001
- source_flow_id: FLOW-AUTHOR-001
- coverage_category: pacing
- requirement_name: item_a
- objective: Objective A
- evidence_signals: signal_a
- output_presentation: report_json
### Requirement 02: Item B
- requirement_id: ADR-002
- source_flow_id: FLOW-AUTHOR-001
- coverage_category: monotony
- requirement_name: item_b
- objective: Objective B
- evidence_signals: signal_b
- output_presentation: report_json
"""
    section = extract_use_004_section(sample)
    items = parse_requirement_items(section)
    assert len(items) == 2
    assert items[0]["number"] == 1
    assert items[1]["fields"]["requirement_id"] == "ADR-002"


def test_integration_use_004_mapping_contains_required_coverage() -> None:
    stats = validate_use_004_mapping(DOC_PATH)
    assert stats["requirements"] >= 6
    assert stats["coverage_categories"] >= len(REQUIRED_COVERAGE_CATEGORIES)


def test_e2e_author_diagnostics_mapping_validation_cli_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATION_SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    assert "Author diagnostics mapping validation succeeded" in result.stdout


def test_regression_requirement_id_snapshot() -> None:
    markdown = DOC_PATH.read_text(encoding="utf-8")
    items = parse_requirement_items(extract_use_004_section(markdown))
    requirement_ids = [item["fields"]["requirement_id"] for item in items]
    assert requirement_ids == EXPECTED_REQUIREMENT_IDS
