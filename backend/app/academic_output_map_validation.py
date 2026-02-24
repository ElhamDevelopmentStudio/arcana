from __future__ import annotations

from pathlib import Path
import re


DOC_SECTION_HEADING_PATTERN = re.compile(r"(?m)^##\s+USE-003 Academic Outputs and Export Formats Mapping\s*$")
OUTPUT_HEADING_PATTERN = re.compile(r"(?m)^###\s+Output\s+(\d+):\s+(.+?)\s*$")
FIELD_PATTERN = re.compile(r"(?m)^\s*-\s+([a-z_]+):\s+(.+?)\s*$")

REQUIRED_FIELD_KEYS = {"output_id", "source_flow_id", "output_name", "purpose", "export_formats", "expected_consumer"}
EXPECTED_SOURCE_FLOW_ID = "FLOW-ACADEMIC-001"
MIN_OUTPUT_ITEMS = 5

REQUIRED_FORMAT_COVERAGE = {"json", "csv", "time_series_json", "graph_json"}


class AcademicOutputMapValidationError(ValueError):
    pass


def _normalize_text(text: str) -> str:
    return " ".join(text.split())


def _parse_formats(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]


def extract_use_003_section(markdown: str) -> str:
    section_match = DOC_SECTION_HEADING_PATTERN.search(markdown)
    if section_match is None:
        raise AcademicOutputMapValidationError("Could not find 'USE-003 Academic Outputs and Export Formats Mapping' section.")
    return markdown[section_match.end() :]


def parse_output_items(section_text: str) -> list[dict[str, object]]:
    headings = list(OUTPUT_HEADING_PATTERN.finditer(section_text))
    if not headings:
        raise AcademicOutputMapValidationError("No output headings found in USE-003 mapping section.")

    items: list[dict[str, object]] = []
    for idx, match in enumerate(headings):
        item_number = int(match.group(1))
        item_title = _normalize_text(match.group(2))

        start = match.end()
        end = headings[idx + 1].start() if idx + 1 < len(headings) else len(section_text)
        block = section_text[start:end]

        fields: dict[str, str] = {}
        for field_match in FIELD_PATTERN.finditer(block):
            key = _normalize_text(field_match.group(1))
            value = _normalize_text(field_match.group(2))
            fields[key] = value

        items.append(
            {
                "number": item_number,
                "title": item_title,
                "fields": fields,
            }
        )

    return items


def validate_use_003_mapping(path: Path) -> dict[str, int]:
    markdown = path.read_text(encoding="utf-8")
    section = extract_use_003_section(markdown)
    items = parse_output_items(section)

    item_numbers = [int(item["number"]) for item in items]
    expected_numbers = list(range(1, len(items) + 1))
    if item_numbers != expected_numbers:
        raise AcademicOutputMapValidationError(
            f"Output numbers must be contiguous starting at 1. expected={expected_numbers} actual={item_numbers}"
        )

    if len(items) < MIN_OUTPUT_ITEMS:
        raise AcademicOutputMapValidationError(
            f"USE-003 mapping must include at least {MIN_OUTPUT_ITEMS} outputs, found {len(items)}."
        )

    seen_output_ids: set[str] = set()
    seen_output_names: set[str] = set()
    format_coverage: set[str] = set()

    for item in items:
        fields = item["fields"]
        missing = REQUIRED_FIELD_KEYS - set(fields.keys())
        if missing:
            raise AcademicOutputMapValidationError(
                f"Output {item['number']} is missing required fields: {sorted(missing)}"
            )

        output_id = fields["output_id"]
        if output_id in seen_output_ids:
            raise AcademicOutputMapValidationError(f"Duplicate output_id detected: {output_id}")
        seen_output_ids.add(output_id)

        output_name = fields["output_name"]
        if output_name in seen_output_names:
            raise AcademicOutputMapValidationError(f"Duplicate output_name detected: {output_name}")
        seen_output_names.add(output_name)

        source_flow_id = fields["source_flow_id"]
        if source_flow_id != EXPECTED_SOURCE_FLOW_ID:
            raise AcademicOutputMapValidationError(
                f"Output {item['number']} has invalid source_flow_id. expected={EXPECTED_SOURCE_FLOW_ID} actual={source_flow_id}"
            )

        formats = _parse_formats(fields["export_formats"])
        if not formats:
            raise AcademicOutputMapValidationError(f"Output {item['number']} has empty export_formats.")
        format_coverage.update(formats)

    missing_formats = REQUIRED_FORMAT_COVERAGE - format_coverage
    if missing_formats:
        raise AcademicOutputMapValidationError(
            "USE-003 mapping is missing required format coverage: " + ", ".join(sorted(missing_formats))
        )

    return {
        "outputs": len(items),
        "format_coverage": len(format_coverage),
    }
