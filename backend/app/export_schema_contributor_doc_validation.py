from __future__ import annotations

from pathlib import Path
import re


DOC_SECTION_HEADING_PATTERN = re.compile(r"(?m)^##\s+Contributor Guide: How to evolve export schema safely\s*$")
STEP_HEADING_PATTERN = re.compile(r"(?m)^###\s+Step\s+(\d+):\s+(.+?)\s*$")
FIELD_PATTERN = re.compile(r"(?m)^\s*-\s+([a-z_]+):\s+(.+?)\s*$")

REQUIRED_FIELD_KEYS = {"objective", "files", "checks"}
MIN_STEPS = 6
REQUIRED_STEP_TITLES = [
    "Define change scope and compatibility strategy",
    "Version schema and keep parser-safe defaults",
    "Update backend manifest/export builders",
    "Update frontend schema guards and consumers",
    "Add regression fixtures and contract coverage",
    "Document migration notes and run local smoke",
]


class ExportSchemaContributorDocValidationError(ValueError):
    pass


def _normalize_text(text: str) -> str:
    return " ".join(text.split())


def extract_export_schema_contributor_section(markdown: str) -> str:
    section_match = DOC_SECTION_HEADING_PATTERN.search(markdown)
    if section_match is None:
        raise ExportSchemaContributorDocValidationError(
            "Could not find 'Contributor Guide: How to evolve export schema safely' section."
        )
    return markdown[section_match.end() :]


def parse_step_items(section_text: str) -> list[dict[str, object]]:
    headings = list(STEP_HEADING_PATTERN.finditer(section_text))
    if not headings:
        raise ExportSchemaContributorDocValidationError(
            "No step headings found in export schema contributor guide."
        )

    items: list[dict[str, object]] = []
    for idx, match in enumerate(headings):
        step_number = int(match.group(1))
        step_title = _normalize_text(match.group(2))

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
                "number": step_number,
                "title": step_title,
                "fields": fields,
            }
        )

    return items


def validate_export_schema_contributor_guide(path: Path) -> dict[str, int]:
    markdown = path.read_text(encoding="utf-8")
    section = extract_export_schema_contributor_section(markdown)
    items = parse_step_items(section)

    numbers = [int(item["number"]) for item in items]
    expected_numbers = list(range(1, len(items) + 1))
    if numbers != expected_numbers:
        raise ExportSchemaContributorDocValidationError(
            f"Step numbers must be contiguous starting at 1. expected={expected_numbers} actual={numbers}"
        )

    if len(items) < MIN_STEPS:
        raise ExportSchemaContributorDocValidationError(
            f"Export schema contributor guide must include at least {MIN_STEPS} steps, found {len(items)}."
        )

    titles = [str(item["title"]) for item in items]
    missing_titles = [title for title in REQUIRED_STEP_TITLES if title not in titles]
    if missing_titles:
        raise ExportSchemaContributorDocValidationError(
            "Export schema contributor guide is missing required step titles: " + ", ".join(missing_titles)
        )

    for item in items:
        fields = item["fields"]
        missing = REQUIRED_FIELD_KEYS - set(fields.keys())
        if missing:
            raise ExportSchemaContributorDocValidationError(
                f"Step {item['number']} is missing required fields: {sorted(missing)}"
            )

    return {
        "steps": len(items),
        "required_fields": len(REQUIRED_FIELD_KEYS),
    }
