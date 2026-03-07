import subprocess
import sys
from pathlib import Path

from app.ui_impact_matrix_validation import (
    REQUIRED_SRS_SECTION_TOKENS,
    extract_ui_impact_matrix_section,
    parse_ui_impact_matrix_entries,
    validate_ui_impact_matrix,
)

ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = ROOT / "docs" / "frontend_ui_impact_matrix.md"
VALIDATION_SCRIPT_PATH = ROOT / "backend" / "scripts_validate_ui_impact_matrix.py"

EXPECTED_MAPPING_IDS = [
    "FEUI-001",
    "FEUI-002",
    "FEUI-003",
    "FEUI-004",
    "FEUI-005",
    "FEUI-006",
    "FEUI-007",
    "FEUI-008",
]


def test_unit_extract_and_parse_ui_impact_matrix_entries() -> None:
    sample = """
## UI Impact Matrix: SRS sections to frontend pages/components
| Mapping ID | SRS section | Product scope | Routes/pages | Key components/modules | Evidence artifact | Status |
| --- | --- | --- | --- | --- | --- | --- |
| FEUI-001 | §3 | Scope A | /a | PageA | tests/a.ts | implemented |
| FEUI-002 | §5 | Scope B | /b | PageB | tests/b.ts | partial |
"""
    section = extract_ui_impact_matrix_section(sample)
    entries = parse_ui_impact_matrix_entries(section)
    assert len(entries) == 2
    assert entries[0]["Mapping ID"] == "FEUI-001"
    assert entries[1]["Status"] == "partial"


def test_integration_ui_impact_matrix_doc_is_valid() -> None:
    stats = validate_ui_impact_matrix(DOC_PATH)
    assert stats["entries"] >= 8
    assert stats["required_srs_sections"] == len(REQUIRED_SRS_SECTION_TOKENS)


def test_e2e_ui_impact_matrix_validation_cli_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATION_SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    assert "UI impact matrix validation succeeded" in result.stdout


def test_regression_ui_impact_matrix_ids_snapshot() -> None:
    markdown = DOC_PATH.read_text(encoding="utf-8")
    entries = parse_ui_impact_matrix_entries(extract_ui_impact_matrix_section(markdown))
    ids = [entry["Mapping ID"] for entry in entries]
    assert ids == EXPECTED_MAPPING_IDS
