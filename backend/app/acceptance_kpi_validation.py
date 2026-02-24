from __future__ import annotations

from pathlib import Path
import re

from app.success_criteria_validation import load_srs_success_criteria


KPI_001_SECTION_HEADING_PATTERN = re.compile(r"(?m)^##\s+KPI-001 Clean Chapterized Corpus Verification\s*$")
KPI_002_SECTION_HEADING_PATTERN = re.compile(r"(?m)^##\s+KPI-002 Validated Character Map Verification\s*$")
KPI_003_SECTION_HEADING_PATTERN = re.compile(r"(?m)^##\s+KPI-003 TTS-Ready Tagged Export Verification\s*$")
KPI_004_SECTION_HEADING_PATTERN = re.compile(r"(?m)^##\s+KPI-004 Basic Time-Series and Charts Verification\s*$")
H2_HEADING_PATTERN = re.compile(r"(?m)^##\s+.+$")
KEY_VALUE_BULLET_PATTERN = re.compile(r"^\s*-\s+([a-z0-9_]+):\s+(.+?)\s*$")

REQUIRED_KPI_001_FIELDS = {
    "linked_success_criterion",
    "srs_success_text",
    "minimum_chapter_count",
    "chapter_index_contiguity_rate",
    "empty_chapter_count",
    "unassigned_text_ratio",
    "rerun_chapter_count_delta_same_input_config",
    "verification_artifacts_required",
}

REQUIRED_KPI_002_FIELDS = {
    "linked_success_criterion",
    "srs_success_text",
    "required_fields_per_character",
    "required_field_completeness_rate",
    "duplicate_canonical_name_count",
    "unresolved_alias_conflict_count",
    "invalid_gender_value_count",
    "rerun_character_count_delta_same_input_config",
    "verification_artifacts_required",
}

REQUIRED_KPI_003_FIELDS = {
    "linked_success_criterion",
    "srs_success_text",
    "max_segment_length_compliance_rate",
    "phonetic_text_presence_rate",
    "required_tag_fields",
    "required_tag_fields_presence_rate",
    "voice_resolution_presence_rate",
    "export_schema_validation_pass_rate",
    "rerun_export_segment_delta_same_input_config",
    "verification_artifacts_required",
}

REQUIRED_KPI_004_FIELDS = {
    "linked_success_criterion",
    "srs_success_text",
    "emotion_series_coverage_rate",
    "tension_series_coverage_rate",
    "dominance_series_coverage_rate",
    "chart_render_success_rate",
    "series_ordering_consistency_rate",
    "series_export_schema_validation_pass_rate",
    "rerun_series_point_delta_same_input_config",
    "verification_artifacts_required",
}

EXPECTED_KPI_001_FIXED_VALUES = {
    "linked_success_criterion": "SC-001",
    "minimum_chapter_count": ">= 1",
    "chapter_index_contiguity_rate": "= 1.00",
    "empty_chapter_count": "= 0",
    "unassigned_text_ratio": "<= 0.01",
    "rerun_chapter_count_delta_same_input_config": "= 0",
}

EXPECTED_KPI_002_FIXED_VALUES = {
    "linked_success_criterion": "SC-002",
    "required_fields_per_character": "name, verbalized_form, gender",
    "required_field_completeness_rate": "= 1.00",
    "duplicate_canonical_name_count": "= 0",
    "unresolved_alias_conflict_count": "= 0",
    "invalid_gender_value_count": "= 0",
    "rerun_character_count_delta_same_input_config": "= 0",
}

EXPECTED_KPI_003_FIXED_VALUES = {
    "linked_success_criterion": "SC-003",
    "max_segment_length_compliance_rate": "= 1.00",
    "phonetic_text_presence_rate": "= 1.00",
    "required_tag_fields": "type, speaker, gender, voice_id, emotion_valence, emotion_intensity",
    "required_tag_fields_presence_rate": "= 1.00",
    "voice_resolution_presence_rate": "= 1.00",
    "export_schema_validation_pass_rate": "= 1.00",
    "rerun_export_segment_delta_same_input_config": "= 0",
}

EXPECTED_KPI_004_FIXED_VALUES = {
    "linked_success_criterion": "SC-004",
    "emotion_series_coverage_rate": "= 1.00",
    "tension_series_coverage_rate": "= 1.00",
    "dominance_series_coverage_rate": "= 1.00",
    "chart_render_success_rate": "= 1.00",
    "series_ordering_consistency_rate": "= 1.00",
    "series_export_schema_validation_pass_rate": "= 1.00",
    "rerun_series_point_delta_same_input_config": "= 0",
}


class AcceptanceKPIValidationError(ValueError):
    pass


def _normalize_text(text: str) -> str:
    return " ".join(text.replace("→", "->").split())


def _extract_kpi_section(markdown: str, heading_pattern: re.Pattern[str], section_name: str) -> str:
    heading_match = heading_pattern.search(markdown)
    if heading_match is None:
        raise AcceptanceKPIValidationError(f"Could not find '{section_name}' section in acceptance KPI doc.")

    search_tail = markdown[heading_match.end() :]
    next_h2 = H2_HEADING_PATTERN.search(search_tail)

    if next_h2 is None:
        section_end = len(markdown)
    else:
        section_end = heading_match.end() + next_h2.start()

    return markdown[heading_match.end() : section_end]


def extract_kpi_001_section(markdown: str) -> str:
    return _extract_kpi_section(markdown, KPI_001_SECTION_HEADING_PATTERN, "KPI-001 Clean Chapterized Corpus Verification")


def extract_kpi_002_section(markdown: str) -> str:
    return _extract_kpi_section(markdown, KPI_002_SECTION_HEADING_PATTERN, "KPI-002 Validated Character Map Verification")


def extract_kpi_003_section(markdown: str) -> str:
    return _extract_kpi_section(markdown, KPI_003_SECTION_HEADING_PATTERN, "KPI-003 TTS-Ready Tagged Export Verification")


def extract_kpi_004_section(markdown: str) -> str:
    return _extract_kpi_section(markdown, KPI_004_SECTION_HEADING_PATTERN, "KPI-004 Basic Time-Series and Charts Verification")


def parse_kpi_key_values(section_text: str) -> dict[str, str]:
    key_values: dict[str, str] = {}

    for line in section_text.splitlines():
        match = KEY_VALUE_BULLET_PATTERN.match(line)
        if match is None:
            continue

        key = match.group(1).strip()
        value = _normalize_text(match.group(2).strip())
        key_values[key] = value

    if not key_values:
        raise AcceptanceKPIValidationError("No KPI key/value bullet lines found in KPI section.")

    return key_values


def load_kpi_001(path: Path) -> dict[str, str]:
    markdown = path.read_text(encoding="utf-8")
    section = extract_kpi_001_section(markdown)
    return parse_kpi_key_values(section)


def load_kpi_002(path: Path) -> dict[str, str]:
    markdown = path.read_text(encoding="utf-8")
    section = extract_kpi_002_section(markdown)
    return parse_kpi_key_values(section)


def load_kpi_003(path: Path) -> dict[str, str]:
    markdown = path.read_text(encoding="utf-8")
    section = extract_kpi_003_section(markdown)
    return parse_kpi_key_values(section)


def load_kpi_004(path: Path) -> dict[str, str]:
    markdown = path.read_text(encoding="utf-8")
    section = extract_kpi_004_section(markdown)
    return parse_kpi_key_values(section)


def _validate_required_fields(kpi: dict[str, str], required_fields: set[str], label: str) -> None:
    missing_fields = required_fields - set(kpi.keys())
    if missing_fields:
        raise AcceptanceKPIValidationError(
            f"{label} section is missing required fields: " + ", ".join(sorted(missing_fields))
        )


def _validate_fixed_values(kpi: dict[str, str], expected_values: dict[str, str], label: str) -> None:
    for key, expected_value in expected_values.items():
        actual = kpi.get(key)
        if actual != expected_value:
            raise AcceptanceKPIValidationError(
                f"{label} field '{key}' mismatch. expected='{expected_value}' actual='{actual}'"
            )


def _expected_srs_success_text(srs_path: Path, index: int) -> str:
    return _normalize_text(load_srs_success_criteria(srs_path)[index])


def validate_kpi_001_against_srs(srs_path: Path, kpi_doc_path: Path) -> dict[str, str]:
    kpi = load_kpi_001(kpi_doc_path)

    _validate_required_fields(kpi, REQUIRED_KPI_001_FIELDS, "KPI-001")
    _validate_fixed_values(kpi, EXPECTED_KPI_001_FIXED_VALUES, "KPI-001")

    expected_srs_text = _expected_srs_success_text(srs_path, 0)
    actual_srs_text = kpi["srs_success_text"]
    if actual_srs_text != expected_srs_text:
        raise AcceptanceKPIValidationError(
            "KPI-001 srs_success_text does not match SRS §1.3 clean chapterized corpus criterion."
        )

    return kpi


def validate_kpi_002_against_srs(srs_path: Path, kpi_doc_path: Path) -> dict[str, str]:
    kpi = load_kpi_002(kpi_doc_path)

    _validate_required_fields(kpi, REQUIRED_KPI_002_FIELDS, "KPI-002")
    _validate_fixed_values(kpi, EXPECTED_KPI_002_FIXED_VALUES, "KPI-002")

    expected_srs_text = _expected_srs_success_text(srs_path, 1)
    actual_srs_text = kpi["srs_success_text"]
    if actual_srs_text != expected_srs_text:
        raise AcceptanceKPIValidationError(
            "KPI-002 srs_success_text does not match SRS §1.3 validated character map criterion."
        )

    return kpi


def validate_kpi_003_against_srs(srs_path: Path, kpi_doc_path: Path) -> dict[str, str]:
    kpi = load_kpi_003(kpi_doc_path)

    _validate_required_fields(kpi, REQUIRED_KPI_003_FIELDS, "KPI-003")
    _validate_fixed_values(kpi, EXPECTED_KPI_003_FIXED_VALUES, "KPI-003")

    expected_srs_text = _expected_srs_success_text(srs_path, 2)
    actual_srs_text = kpi["srs_success_text"]
    if actual_srs_text != expected_srs_text:
        raise AcceptanceKPIValidationError(
            "KPI-003 srs_success_text does not match SRS §1.3 TTS-ready tagged export criterion."
        )

    return kpi


def validate_kpi_004_against_srs(srs_path: Path, kpi_doc_path: Path) -> dict[str, str]:
    kpi = load_kpi_004(kpi_doc_path)

    _validate_required_fields(kpi, REQUIRED_KPI_004_FIELDS, "KPI-004")
    _validate_fixed_values(kpi, EXPECTED_KPI_004_FIXED_VALUES, "KPI-004")

    expected_srs_text = _expected_srs_success_text(srs_path, 3)
    actual_srs_text = kpi["srs_success_text"]
    if actual_srs_text != expected_srs_text:
        raise AcceptanceKPIValidationError(
            "KPI-004 srs_success_text does not match SRS §1.3 time-series/charts criterion."
        )

    return kpi
