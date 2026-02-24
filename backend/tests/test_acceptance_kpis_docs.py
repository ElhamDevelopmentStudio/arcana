import subprocess
import sys
from pathlib import Path

from app.acceptance_kpi_validation import (
    extract_kpi_001_section,
    load_kpi_001,
    parse_kpi_key_values,
    validate_kpi_001_against_srs,
)

ROOT = Path(__file__).resolve().parents[2]
SRS_PATH = ROOT / "SRS.md"
KPI_DOC_PATH = ROOT / "docs" / "acceptance_kpis.md"
VALIDATION_SCRIPT_PATH = ROOT / "backend" / "scripts_validate_acceptance_kpis.py"

EXPECTED_KPI_001 = {
    "linked_success_criterion": "SC-001",
    "srs_success_text": "a clean chapterized corpus",
    "minimum_chapter_count": ">= 1",
    "chapter_index_contiguity_rate": "= 1.00",
    "empty_chapter_count": "= 0",
    "unassigned_text_ratio": "<= 0.01",
    "rerun_chapter_count_delta_same_input_config": "= 0",
    "verification_artifacts_required": "run_summary_json, chapter_index_report, rerun_diff_report",
}


def test_unit_extract_kpi_section_stops_at_next_h2() -> None:
    sample = """
# KPIs
## KPI-001 Clean Chapterized Corpus Verification
- linked_success_criterion: SC-001
## KPI-002 Other
- linked_success_criterion: SC-002
"""
    section = extract_kpi_001_section(sample)
    assert "linked_success_criterion: SC-001" in section
    assert "linked_success_criterion: SC-002" not in section


def test_unit_parse_kpi_key_values_extracts_all_pairs() -> None:
    sample = """
- linked_success_criterion: SC-001
- minimum_chapter_count: >= 1
"""
    parsed = parse_kpi_key_values(sample)
    assert parsed == {
        "linked_success_criterion": "SC-001",
        "minimum_chapter_count": ">= 1",
    }


def test_integration_kpi_001_matches_srs_and_required_fields() -> None:
    parsed = validate_kpi_001_against_srs(SRS_PATH, KPI_DOC_PATH)
    assert parsed == EXPECTED_KPI_001


def test_e2e_kpi_validation_cli_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATION_SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    assert "Acceptance KPI validation succeeded" in result.stdout


def test_regression_kpi_snapshot() -> None:
    parsed = load_kpi_001(KPI_DOC_PATH)
    assert parsed == EXPECTED_KPI_001
