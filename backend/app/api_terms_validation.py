from __future__ import annotations

import json
import re
from pathlib import Path


REQUIRED_TERMS = ("Novel", "Corpus", "Chapter Unit", "Segment", "Sub-segment", "Character Map")


class APITermsValidationError(ValueError):
    pass


def _split_sections(markdown: str) -> dict[str, str]:
    heading_pattern = re.compile(
        r"(?m)^##\s+(Novel|Corpus|Chapter Unit|Segment|Sub-segment|Character Map)\s*$"
    )
    matches = list(heading_pattern.finditer(markdown))
    if not matches:
        raise APITermsValidationError("No API term sections found for required terms.")

    sections: dict[str, str] = {}
    for idx, match in enumerate(matches):
        term = match.group(1)
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(markdown)
        sections[term] = markdown[start:end].strip()
    return sections


def parse_term_definition(section: str) -> str:
    definition_match = re.search(r"(?m)^Definition:\s*(.+)$", section)
    if not definition_match:
        raise APITermsValidationError("Missing `Definition:` line in API term section.")
    return definition_match.group(1).strip()


def parse_term_json_example(section: str) -> dict:
    json_match = re.search(r"```json\s*(\{.*?\})\s*```", section, re.DOTALL)
    if not json_match:
        raise APITermsValidationError("Missing JSON example block in API term section.")
    try:
        return json.loads(json_match.group(1))
    except json.JSONDecodeError as exc:
        raise APITermsValidationError(f"Invalid JSON example in API term section: {exc}") from exc


def load_and_parse_api_terms(path: Path) -> dict[str, dict]:
    markdown = path.read_text(encoding="utf-8")
    sections = _split_sections(markdown)

    parsed: dict[str, dict] = {}
    for term in REQUIRED_TERMS:
        if term not in sections:
            raise APITermsValidationError(f"Missing required API term section: {term}")
        section = sections[term]
        parsed[term] = {
            "definition": parse_term_definition(section),
            "example": parse_term_json_example(section),
        }
    return parsed
