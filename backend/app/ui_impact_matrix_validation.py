from __future__ import annotations

from pathlib import Path
import re


SECTION_HEADING_PATTERN = re.compile(r"(?m)^##\s+UI Impact Matrix: SRS sections to frontend pages/components\s*$")
MAPPING_ID_PATTERN = re.compile(r"^FEUI-(\d{3})$")

EXPECTED_HEADER = [
    "Mapping ID",
    "SRS section",
    "Product scope",
    "Routes/pages",
    "Key components/modules",
    "Evidence artifact",
    "Status",
]
ALLOWED_STATUSES = {"implemented", "partial", "planned"}
MIN_ENTRIES = 8
REQUIRED_SRS_SECTION_TOKENS = ("§2.1", "§3", "§4.1", "§4.3", "§4.6", "§4.9", "§4.12", "§5")


class UIImpactMatrixValidationError(ValueError):
    pass


def _split_table_row(row: str) -> list[str]:
    stripped = row.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        raise UIImpactMatrixValidationError(f"Invalid table row format: {row}")
    return [cell.strip() for cell in stripped[1:-1].split("|")]


def extract_ui_impact_matrix_section(markdown: str) -> str:
    match = SECTION_HEADING_PATTERN.search(markdown)
    if match is None:
        raise UIImpactMatrixValidationError(
            "Could not find 'UI Impact Matrix: SRS sections to frontend pages/components' section."
        )
    return markdown[match.end() :]


def parse_ui_impact_matrix_entries(section: str) -> list[dict[str, str]]:
    table_lines = [line.strip() for line in section.splitlines() if line.strip().startswith("|")]
    if len(table_lines) < 3:
        raise UIImpactMatrixValidationError("UI impact matrix must include a markdown table with entries.")

    header = _split_table_row(table_lines[0])
    if header != EXPECTED_HEADER:
        raise UIImpactMatrixValidationError(
            f"UI impact matrix header mismatch. expected={EXPECTED_HEADER} actual={header}"
        )

    entries: list[dict[str, str]] = []
    for raw_line in table_lines[2:]:
        cells = _split_table_row(raw_line)
        if len(cells) != len(EXPECTED_HEADER):
            raise UIImpactMatrixValidationError(
                f"UI impact matrix row has {len(cells)} columns; expected {len(EXPECTED_HEADER)}."
            )
        entries.append(dict(zip(EXPECTED_HEADER, cells, strict=True)))

    return entries


def validate_ui_impact_matrix(path: Path) -> dict[str, int]:
    markdown = path.read_text(encoding="utf-8")
    section = extract_ui_impact_matrix_section(markdown)
    entries = parse_ui_impact_matrix_entries(section)

    if len(entries) < MIN_ENTRIES:
        raise UIImpactMatrixValidationError(
            f"UI impact matrix must include at least {MIN_ENTRIES} entries, found {len(entries)}."
        )

    mapping_ids: list[int] = []
    srs_coverage_blob = ""
    for entry in entries:
        mapping_id = entry["Mapping ID"]
        id_match = MAPPING_ID_PATTERN.match(mapping_id)
        if id_match is None:
            raise UIImpactMatrixValidationError(f"Invalid Mapping ID format: {mapping_id}")
        mapping_ids.append(int(id_match.group(1)))

        for required_field in ("SRS section", "Product scope", "Routes/pages", "Key components/modules", "Evidence artifact"):
            if not entry[required_field] or entry[required_field] == "-":
                raise UIImpactMatrixValidationError(f"{required_field} must be populated for {mapping_id}.")

        status = entry["Status"].lower()
        if status not in ALLOWED_STATUSES:
            raise UIImpactMatrixValidationError(
                f"Invalid status '{entry['Status']}' for {mapping_id}; allowed={sorted(ALLOWED_STATUSES)}."
            )

        srs_coverage_blob = f"{srs_coverage_blob} {entry['SRS section']}"

    expected_ids = list(range(1, len(entries) + 1))
    if mapping_ids != expected_ids:
        raise UIImpactMatrixValidationError(
            f"Mapping IDs must be contiguous from FEUI-001. expected={expected_ids} actual={mapping_ids}"
        )

    missing_sections = [token for token in REQUIRED_SRS_SECTION_TOKENS if token not in srs_coverage_blob]
    if missing_sections:
        raise UIImpactMatrixValidationError(
            "UI impact matrix is missing required SRS section coverage: " + ", ".join(missing_sections)
        )

    return {
        "entries": len(entries),
        "required_srs_sections": len(REQUIRED_SRS_SECTION_TOKENS),
    }
