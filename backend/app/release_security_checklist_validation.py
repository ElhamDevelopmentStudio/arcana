from __future__ import annotations

from pathlib import Path
import re


DOC_SECTION_HEADING_PATTERN = re.compile(r"(?m)^##\s+Release Security Review Checklist\s*$")
CONTROL_HEADING_PATTERN = re.compile(r"(?m)^###\s+Control\s+(\d+):\s+(.+?)\s*$")
FIELD_PATTERN = re.compile(r"(?m)^\s*-\s+([a-z_]+):\s+(.+?)\s*$")

REQUIRED_FIELD_KEYS = {"objective", "required_inputs", "completion_criteria"}
MIN_CONTROLS = 6
REQUIRED_CONTROL_TITLES = [
    "Threat model and scope revalidation",
    "Secrets and credential handling verification",
    "Authorization boundary and data isolation checks",
    "Dependency and supply-chain vulnerability review",
    "Security testing and abuse-case validation",
    "Security sign-off, incident readiness, and audit trail",
]


class ReleaseSecurityChecklistValidationError(ValueError):
    pass


def _normalize_text(text: str) -> str:
    return " ".join(text.split())


def extract_release_security_checklist_section(markdown: str) -> str:
    section_match = DOC_SECTION_HEADING_PATTERN.search(markdown)
    if section_match is None:
        raise ReleaseSecurityChecklistValidationError("Could not find 'Release Security Review Checklist' section.")
    return markdown[section_match.end() :]


def parse_security_controls(section_text: str) -> list[dict[str, object]]:
    headings = list(CONTROL_HEADING_PATTERN.finditer(section_text))
    if not headings:
        raise ReleaseSecurityChecklistValidationError("No security control headings found in checklist document.")

    items: list[dict[str, object]] = []
    for idx, match in enumerate(headings):
        control_number = int(match.group(1))
        control_title = _normalize_text(match.group(2))

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
                "number": control_number,
                "title": control_title,
                "fields": fields,
            }
        )

    return items


def validate_release_security_checklist(path: Path) -> dict[str, int]:
    markdown = path.read_text(encoding="utf-8")
    section = extract_release_security_checklist_section(markdown)
    items = parse_security_controls(section)

    numbers = [int(item["number"]) for item in items]
    expected_numbers = list(range(1, len(items) + 1))
    if numbers != expected_numbers:
        raise ReleaseSecurityChecklistValidationError(
            f"Control numbers must be contiguous starting at 1. expected={expected_numbers} actual={numbers}"
        )

    if len(items) < MIN_CONTROLS:
        raise ReleaseSecurityChecklistValidationError(
            f"Release security checklist must include at least {MIN_CONTROLS} controls, found {len(items)}."
        )

    titles = [str(item["title"]) for item in items]
    missing_titles = [title for title in REQUIRED_CONTROL_TITLES if title not in titles]
    if missing_titles:
        raise ReleaseSecurityChecklistValidationError(
            "Release security checklist is missing required control titles: " + ", ".join(missing_titles)
        )

    for item in items:
        fields = item["fields"]
        missing = REQUIRED_FIELD_KEYS - set(fields.keys())
        if missing:
            raise ReleaseSecurityChecklistValidationError(
                f"Control {item['number']} is missing required fields: {sorted(missing)}"
            )

    return {
        "controls": len(items),
        "required_fields": len(REQUIRED_FIELD_KEYS),
    }
