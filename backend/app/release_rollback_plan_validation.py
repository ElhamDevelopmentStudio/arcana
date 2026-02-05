from __future__ import annotations

from pathlib import Path
import re


DOC_SECTION_HEADING_PATTERN = re.compile(r"(?m)^##\s+Rollback Plan Template\s*$")
SECTION_HEADING_PATTERN = re.compile(r"(?m)^###\s+Section\s+(\d+):\s+(.+?)\s*$")
FIELD_PATTERN = re.compile(r"(?m)^\s*-\s+([a-z_]+):\s+(.+?)\s*$")

REQUIRED_FIELD_KEYS = {"objective", "required_inputs", "completion_criteria"}
MIN_SECTIONS = 6
REQUIRED_SECTION_TITLES = [
    "Release identification and blast radius",
    "Rollback triggers and decision thresholds",
    "Pre-rollback safeguards and backups",
    "Step-by-step rollback execution commands",
    "Post-rollback verification checklist",
    "Incident log, communications, and follow-up actions",
]


class ReleaseRollbackPlanValidationError(ValueError):
    pass


def _normalize_text(text: str) -> str:
    return " ".join(text.split())


def extract_rollback_plan_section(markdown: str) -> str:
    section_match = DOC_SECTION_HEADING_PATTERN.search(markdown)
    if section_match is None:
        raise ReleaseRollbackPlanValidationError("Could not find 'Rollback Plan Template' section.")
    return markdown[section_match.end() :]


def parse_rollback_sections(section_text: str) -> list[dict[str, object]]:
    headings = list(SECTION_HEADING_PATTERN.finditer(section_text))
    if not headings:
        raise ReleaseRollbackPlanValidationError("No rollback section headings found in rollback plan template.")

    items: list[dict[str, object]] = []
    for idx, match in enumerate(headings):
        section_number = int(match.group(1))
        section_title = _normalize_text(match.group(2))

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
                "number": section_number,
                "title": section_title,
                "fields": fields,
            }
        )

    return items


def validate_release_rollback_plan(path: Path) -> dict[str, int]:
    markdown = path.read_text(encoding="utf-8")
    section = extract_rollback_plan_section(markdown)
    items = parse_rollback_sections(section)

    numbers = [int(item["number"]) for item in items]
    expected_numbers = list(range(1, len(items) + 1))
    if numbers != expected_numbers:
        raise ReleaseRollbackPlanValidationError(
            f"Section numbers must be contiguous starting at 1. expected={expected_numbers} actual={numbers}"
        )

    if len(items) < MIN_SECTIONS:
        raise ReleaseRollbackPlanValidationError(
            f"Rollback plan template must include at least {MIN_SECTIONS} sections, found {len(items)}."
        )

    titles = [str(item["title"]) for item in items]
    missing_titles = [title for title in REQUIRED_SECTION_TITLES if title not in titles]
    if missing_titles:
        raise ReleaseRollbackPlanValidationError(
            "Rollback plan template is missing required section titles: " + ", ".join(missing_titles)
        )

    for item in items:
        fields = item["fields"]
        missing = REQUIRED_FIELD_KEYS - set(fields.keys())
        if missing:
            raise ReleaseRollbackPlanValidationError(
                f"Section {item['number']} is missing required fields: {sorted(missing)}"
            )

    return {
        "sections": len(items),
        "required_fields": len(REQUIRED_FIELD_KEYS),
    }
