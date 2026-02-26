from __future__ import annotations

from pathlib import Path
import re


DOC_SECTION_HEADING_PATTERN = re.compile(
    r"(?m)^##\s+Release Checklist: Data migrations and backward compatibility\s*$"
)
ITEM_HEADING_PATTERN = re.compile(r"(?m)^###\s+Item\s+(\d+):\s+(.+?)\s*$")
FIELD_PATTERN = re.compile(r"(?m)^\s*-\s+([a-z_]+):\s+(.+?)\s*$")

REQUIRED_FIELD_KEYS = {"objective", "actions", "evidence"}
MIN_ITEMS = 6
REQUIRED_ITEM_TITLES = [
    "Catalog schema and data-change impact",
    "Validate migration ordering and idempotence assumptions",
    "Define compatibility window and fallback behavior",
    "Execute contract and regression coverage for changed surfaces",
    "Capture rollout and rollback readiness",
    "Perform post-release verification and closeout",
]


class ReleaseMigrationChecklistValidationError(ValueError):
    pass


def _normalize_text(text: str) -> str:
    return " ".join(text.split())


def extract_release_checklist_section(markdown: str) -> str:
    section_match = DOC_SECTION_HEADING_PATTERN.search(markdown)
    if section_match is None:
        raise ReleaseMigrationChecklistValidationError(
            "Could not find 'Release Checklist: Data migrations and backward compatibility' section."
        )
    return markdown[section_match.end() :]


def parse_checklist_items(section_text: str) -> list[dict[str, object]]:
    headings = list(ITEM_HEADING_PATTERN.finditer(section_text))
    if not headings:
        raise ReleaseMigrationChecklistValidationError("No checklist item headings found in release checklist doc.")

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


def validate_release_migration_checklist(path: Path) -> dict[str, int]:
    markdown = path.read_text(encoding="utf-8")
    section = extract_release_checklist_section(markdown)
    items = parse_checklist_items(section)

    numbers = [int(item["number"]) for item in items]
    expected_numbers = list(range(1, len(items) + 1))
    if numbers != expected_numbers:
        raise ReleaseMigrationChecklistValidationError(
            f"Checklist item numbers must be contiguous starting at 1. expected={expected_numbers} actual={numbers}"
        )

    if len(items) < MIN_ITEMS:
        raise ReleaseMigrationChecklistValidationError(
            f"Release migration checklist must include at least {MIN_ITEMS} items, found {len(items)}."
        )

    titles = [str(item["title"]) for item in items]
    missing_titles = [title for title in REQUIRED_ITEM_TITLES if title not in titles]
    if missing_titles:
        raise ReleaseMigrationChecklistValidationError(
            "Release migration checklist is missing required item titles: " + ", ".join(missing_titles)
        )

    for item in items:
        fields = item["fields"]
        missing = REQUIRED_FIELD_KEYS - set(fields.keys())
        if missing:
            raise ReleaseMigrationChecklistValidationError(
                f"Item {item['number']} is missing required fields: {sorted(missing)}"
            )

    return {
        "items": len(items),
        "required_fields": len(REQUIRED_FIELD_KEYS),
    }
