from __future__ import annotations

from pathlib import Path
import re


DOC_SECTION_HEADING_PATTERN = re.compile(r"(?m)^##\s+USE-004 Author Diagnostic Report Requirements Mapping\s*$")
REQUIREMENT_HEADING_PATTERN = re.compile(r"(?m)^###\s+Requirement\s+(\d+):\s+(.+?)\s*$")
FIELD_PATTERN = re.compile(r"(?m)^\s*-\s+([a-z_]+):\s+(.+?)\s*$")

REQUIRED_FIELD_KEYS = {
    "requirement_id",
    "source_flow_id",
    "coverage_category",
    "requirement_name",
    "objective",
    "evidence_signals",
    "output_presentation",
}

EXPECTED_SOURCE_FLOW_ID = "FLOW-AUTHOR-001"
MIN_REQUIREMENTS = 5
REQUIRED_COVERAGE_CATEGORIES = {"pacing", "monotony", "character_imbalance"}


class AuthorDiagnosticMapValidationError(ValueError):
    pass


def _normalize_text(text: str) -> str:
    return " ".join(text.split())


def extract_use_004_section(markdown: str) -> str:
    section_match = DOC_SECTION_HEADING_PATTERN.search(markdown)
    if section_match is None:
        raise AuthorDiagnosticMapValidationError("Could not find 'USE-004 Author Diagnostic Report Requirements Mapping' section.")
    return markdown[section_match.end() :]


def parse_requirement_items(section_text: str) -> list[dict[str, object]]:
    headings = list(REQUIREMENT_HEADING_PATTERN.finditer(section_text))
    if not headings:
        raise AuthorDiagnosticMapValidationError("No requirement headings found in USE-004 mapping section.")

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


def validate_use_004_mapping(path: Path) -> dict[str, int]:
    markdown = path.read_text(encoding="utf-8")
    section = extract_use_004_section(markdown)
    items = parse_requirement_items(section)

    numbers = [int(item["number"]) for item in items]
    expected_numbers = list(range(1, len(items) + 1))
    if numbers != expected_numbers:
        raise AuthorDiagnosticMapValidationError(
            f"Requirement numbers must be contiguous starting at 1. expected={expected_numbers} actual={numbers}"
        )

    if len(items) < MIN_REQUIREMENTS:
        raise AuthorDiagnosticMapValidationError(
            f"USE-004 mapping must include at least {MIN_REQUIREMENTS} requirements, found {len(items)}."
        )

    seen_ids: set[str] = set()
    seen_names: set[str] = set()
    coverage: set[str] = set()

    for item in items:
        fields = item["fields"]
        missing = REQUIRED_FIELD_KEYS - set(fields.keys())
        if missing:
            raise AuthorDiagnosticMapValidationError(
                f"Requirement {item['number']} is missing required fields: {sorted(missing)}"
            )

        requirement_id = fields["requirement_id"]
        if requirement_id in seen_ids:
            raise AuthorDiagnosticMapValidationError(f"Duplicate requirement_id detected: {requirement_id}")
        seen_ids.add(requirement_id)

        requirement_name = fields["requirement_name"]
        if requirement_name in seen_names:
            raise AuthorDiagnosticMapValidationError(f"Duplicate requirement_name detected: {requirement_name}")
        seen_names.add(requirement_name)

        source_flow_id = fields["source_flow_id"]
        if source_flow_id != EXPECTED_SOURCE_FLOW_ID:
            raise AuthorDiagnosticMapValidationError(
                f"Requirement {item['number']} has invalid source_flow_id. expected={EXPECTED_SOURCE_FLOW_ID} actual={source_flow_id}"
            )

        coverage.add(fields["coverage_category"])

    missing_coverage = REQUIRED_COVERAGE_CATEGORIES - coverage
    if missing_coverage:
        raise AuthorDiagnosticMapValidationError(
            "USE-004 mapping is missing required coverage categories: " + ", ".join(sorted(missing_coverage))
        )

    return {
        "requirements": len(items),
        "coverage_categories": len(coverage),
    }
