import subprocess
import sys
from pathlib import Path

from app.acceptance_kpi_validation import (
    extract_kpi_001_section,
    extract_kpi_002_section,
    extract_kpi_003_section,
    extract_kpi_004_section,
    load_kpi_001,
    load_kpi_002,
    load_kpi_003,
    load_kpi_004,
    parse_kpi_key_values,
    validate_kpi_001_against_srs,
    validate_kpi_002_against_srs,
    validate_kpi_003_against_srs,
    validate_kpi_004_against_srs,
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

EXPECTED_KPI_002 = {
    "linked_success_criterion": "SC-002",
    "srs_success_text": "a validated character map (name -> verbalized -> gender)",
    "required_fields_per_character": "name, verbalized_form, gender",
    "required_field_completeness_rate": "= 1.00",
    "duplicate_canonical_name_count": "= 0",
    "unresolved_alias_conflict_count": "= 0",
    "invalid_gender_value_count": "= 0",
    "rerun_character_count_delta_same_input_config": "= 0",
    "verification_artifacts_required": "character_map_export_json, character_validation_report, rerun_diff_report",
}

EXPECTED_KPI_003 = {
    "linked_success_criterion": "SC-003",
    "srs_success_text": "a segmented, phonetic-normalized, tagged export suitable to feed into a TTS pipeline",
    "max_segment_length_compliance_rate": "= 1.00",
    "phonetic_text_presence_rate": "= 1.00",
    "required_tag_fields": "type, speaker, gender, voice_id, emotion_valence, emotion_intensity",
    "required_tag_fields_presence_rate": "= 1.00",
    "voice_resolution_presence_rate": "= 1.00",
    "export_schema_validation_pass_rate": "= 1.00",
    "rerun_export_segment_delta_same_input_config": "= 0",
    "verification_artifacts_required": "export_json, export_schema_validation_report, segment_length_report, rerun_diff_report",
}

EXPECTED_KPI_004 = {
    "linked_success_criterion": "SC-004",
    "srs_success_text": "basic tension/emotion/dominance time-series and charts",
    "emotion_series_coverage_rate": "= 1.00",
    "tension_series_coverage_rate": "= 1.00",
    "dominance_series_coverage_rate": "= 1.00",
    "chart_render_success_rate": "= 1.00",
    "series_ordering_consistency_rate": "= 1.00",
    "series_export_schema_validation_pass_rate": "= 1.00",
    "rerun_series_point_delta_same_input_config": "= 0",
    "verification_artifacts_required": "emotion_series_export_json, tension_series_export_json, dominance_series_export_json, chart_render_report, rerun_diff_report",
}


def test_unit_extract_kpi_section_stops_at_next_h2() -> None:
    sample = """
# KPIs
## KPI-001 Clean Chapterized Corpus Verification
- linked_success_criterion: SC-001
## KPI-002 Validated Character Map Verification
- linked_success_criterion: SC-002
## KPI-003 TTS-Ready Tagged Export Verification
- linked_success_criterion: SC-003
## KPI-004 Basic Time-Series and Charts Verification
- linked_success_criterion: SC-004
## KPI-005 Other
- linked_success_criterion: SC-005
"""
    section_001 = extract_kpi_001_section(sample)
    assert "linked_success_criterion: SC-001" in section_001
    assert "linked_success_criterion: SC-002" not in section_001

    section_002 = extract_kpi_002_section(sample)
    assert "linked_success_criterion: SC-002" in section_002
    assert "linked_success_criterion: SC-003" not in section_002

    section_003 = extract_kpi_003_section(sample)
    assert "linked_success_criterion: SC-003" in section_003
    assert "linked_success_criterion: SC-004" not in section_003

    section_004 = extract_kpi_004_section(sample)
    assert "linked_success_criterion: SC-004" in section_004
    assert "linked_success_criterion: SC-005" not in section_004


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
    parsed_001 = validate_kpi_001_against_srs(SRS_PATH, KPI_DOC_PATH)
    parsed_002 = validate_kpi_002_against_srs(SRS_PATH, KPI_DOC_PATH)
    parsed_003 = validate_kpi_003_against_srs(SRS_PATH, KPI_DOC_PATH)
    parsed_004 = validate_kpi_004_against_srs(SRS_PATH, KPI_DOC_PATH)
    assert parsed_001 == EXPECTED_KPI_001
    assert parsed_002 == EXPECTED_KPI_002
    assert parsed_003 == EXPECTED_KPI_003
    assert parsed_004 == EXPECTED_KPI_004


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
    assert "SC-001, SC-002, SC-003, and SC-004" in result.stdout


def test_regression_kpi_snapshot() -> None:
    parsed_001 = load_kpi_001(KPI_DOC_PATH)
    parsed_002 = load_kpi_002(KPI_DOC_PATH)
    parsed_003 = load_kpi_003(KPI_DOC_PATH)
    parsed_004 = load_kpi_004(KPI_DOC_PATH)
    assert parsed_001 == EXPECTED_KPI_001
    assert parsed_002 == EXPECTED_KPI_002
    assert parsed_003 == EXPECTED_KPI_003
    assert parsed_004 == EXPECTED_KPI_004
