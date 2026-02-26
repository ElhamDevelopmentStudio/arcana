from __future__ import annotations

from pathlib import Path
import re


DOC_SECTION_HEADING_PATTERN = re.compile(
    r"(?m)^##\s+Contributor Guide: How to add a new LLM provider adapter\s*$"
)
STEP_HEADING_PATTERN = re.compile(r"(?m)^###\s+Step\s+(\d+):\s+(.+?)\s*$")
FIELD_PATTERN = re.compile(r"(?m)^\s*-\s+([a-z_]+):\s+(.+?)\s*$")

REQUIRED_FIELD_KEYS = {"objective", "files", "checks"}
MIN_STEPS = 6
REQUIRED_STEP_TITLES = [
    "Register provider metadata and adapter hooks",
    "Extend settings and environment configuration",
    "Wire run-level config propagation and API contracts",
    "Cover quota, failover, toggles, and audit behavior",
    "Add backend + frontend regression coverage",
    "Update contributor docs and run local smoke",
]


class LLMProviderAdapterContributorDocValidationError(ValueError):
    pass


def _normalize_text(text: str) -> str:
    return " ".join(text.split())


def extract_llm_provider_adapter_section(markdown: str) -> str:
    section_match = DOC_SECTION_HEADING_PATTERN.search(markdown)
    if section_match is None:
        raise LLMProviderAdapterContributorDocValidationError(
            "Could not find 'Contributor Guide: How to add a new LLM provider adapter' section."
        )
    return markdown[section_match.end() :]


def parse_step_items(section_text: str) -> list[dict[str, object]]:
    headings = list(STEP_HEADING_PATTERN.finditer(section_text))
    if not headings:
        raise LLMProviderAdapterContributorDocValidationError(
            "No step headings found in contributor LLM provider adapter guide."
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


def validate_llm_provider_adapter_guide(path: Path) -> dict[str, int]:
    markdown = path.read_text(encoding="utf-8")
    section = extract_llm_provider_adapter_section(markdown)
    items = parse_step_items(section)

    numbers = [int(item["number"]) for item in items]
    expected_numbers = list(range(1, len(items) + 1))
    if numbers != expected_numbers:
        raise LLMProviderAdapterContributorDocValidationError(
            f"Step numbers must be contiguous starting at 1. expected={expected_numbers} actual={numbers}"
        )

    if len(items) < MIN_STEPS:
        raise LLMProviderAdapterContributorDocValidationError(
            f"Contributor LLM provider adapter guide must include at least {MIN_STEPS} steps, found {len(items)}."
        )

    titles = [str(item["title"]) for item in items]
    missing_titles = [title for title in REQUIRED_STEP_TITLES if title not in titles]
    if missing_titles:
        raise LLMProviderAdapterContributorDocValidationError(
            "Contributor LLM provider adapter guide is missing required step titles: " + ", ".join(missing_titles)
        )

    for item in items:
        fields = item["fields"]
        missing = REQUIRED_FIELD_KEYS - set(fields.keys())
        if missing:
            raise LLMProviderAdapterContributorDocValidationError(
                f"Step {item['number']} is missing required fields: {sorted(missing)}"
            )

    return {
        "steps": len(items),
        "required_fields": len(REQUIRED_FIELD_KEYS),
    }
