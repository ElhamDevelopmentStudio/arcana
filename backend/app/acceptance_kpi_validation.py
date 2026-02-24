from __future__ import annotations

from pathlib import Path
import re

from app.success_criteria_validation import load_srs_success_criteria


KPI_SECTION_HEADING_PATTERN = re.compile(r"(?m)^##\s+KPI-001 Clean Chapterized Corpus Verification\s*$")
H2_HEADING_PATTERN = re.compile(r"(?m)^##\s+.+$")
KEY_VALUE_BULLET_PATTERN = re.compile(r"^\s*-\s+([a-z0-9_]+):\s+(.+?)\s*$")

REQUIRED_KPI_FIELDS = {
    "linked_success_criterion",
    "srs_success_text",
    "minimum_chapter_count",
    "chapter_index_contiguity_rate",
    "empty_chapter_count",
    "unassigned_text_ratio",
    "rerun_chapter_count_delta_same_input_config",
    "verification_artifacts_required",
}

EXPECTED_FIXED_VALUES = {
    "linked_success_criterion": "SC-001",
    "minimum_chapter_count": ">= 1",
    "chapter_index_contiguity_rate": "= 1.00",
    "empty_chapter_count": "= 0",
    "unassigned_text_ratio": "<= 0.01",
    "rerun_chapter_count_delta_same_input_config": "= 0",
}


class AcceptanceKPIValidationError(ValueError):
    pass


def _normalize_text(text: str) -> str:
    return " ".join(text.replace("→", "->").split())


def extract_kpi_001_section(markdown: str) -> str:
    heading_match = KPI_SECTION_HEADING_PATTERN.search(markdown)
    if heading_match is None:
        raise AcceptanceKPIValidationError(
            "Could not find '## KPI-001 Clean Chapterized Corpus Verification' section in acceptance KPI doc."
        )

    search_tail = markdown[heading_match.end() :]
    next_h2 = H2_HEADING_PATTERN.search(search_tail)

    if next_h2 is None:
        section_end = len(markdown)
    else:
        section_end = heading_match.end() + next_h2.start()

    return markdown[heading_match.end() : section_end]


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
        raise AcceptanceKPIValidationError("No KPI key/value bullet lines found in KPI-001 section.")

    return key_values


def load_kpi_001(path: Path) -> dict[str, str]:
    markdown = path.read_text(encoding="utf-8")
    section = extract_kpi_001_section(markdown)
    return parse_kpi_key_values(section)


def validate_kpi_001_against_srs(srs_path: Path, kpi_doc_path: Path) -> dict[str, str]:
    kpi = load_kpi_001(kpi_doc_path)

    missing_fields = REQUIRED_KPI_FIELDS - set(kpi.keys())
    if missing_fields:
        raise AcceptanceKPIValidationError(
            "KPI-001 section is missing required fields: " + ", ".join(sorted(missing_fields))
        )

    for key, expected_value in EXPECTED_FIXED_VALUES.items():
        actual = kpi.get(key)
        if actual != expected_value:
            raise AcceptanceKPIValidationError(
                f"KPI-001 field '{key}' mismatch. expected='{expected_value}' actual='{actual}'"
            )

    expected_srs_text = _normalize_text(load_srs_success_criteria(srs_path)[0])
    actual_srs_text = kpi["srs_success_text"]
    if actual_srs_text != expected_srs_text:
        raise AcceptanceKPIValidationError(
            "KPI-001 srs_success_text does not match SRS §1.3 clean chapterized corpus criterion."
        )

    return kpi
