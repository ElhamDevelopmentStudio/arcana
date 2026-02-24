from __future__ import annotations

from pathlib import Path
import re


DOC_SECTION_HEADING_PATTERN = re.compile(r"(?m)^##\s+USE-002 Audiobook Flow Mapping\s*$")
STEP_HEADING_PATTERN = re.compile(r"(?m)^###\s+Step\s+(\d+):\s+(.+?)\s*$")
FIELD_PATTERN = re.compile(r"(?m)^\s*-\s+([a-z_]+):\s+(.+?)\s*$")
ENDPOINT_PATTERN = re.compile(r"^(GET|POST|PUT|DELETE|PATCH)\s+/api/.+$")

REQUIRED_FIELD_KEYS = {"ui_screen", "user_action", "api_endpoint", "expected_outcome"}

REQUIRED_ENDPOINTS = [
    "POST /api/projects",
    "POST /api/projects/{project_id}/ingest/txt",
    "POST /api/projects/{project_id}/characters/import",
    "PUT /api/projects/{project_id}/voices",
    "POST /api/projects/{project_id}/runs",
    "GET /api/projects/{project_id}/runs/{run_id}",
    "GET /api/projects/{project_id}/exports/{run_id}.json",
]


class AudiobookFlowValidationError(ValueError):
    pass


def _normalize_text(text: str) -> str:
    return " ".join(text.split())


def extract_use_002_section(markdown: str) -> str:
    section_match = DOC_SECTION_HEADING_PATTERN.search(markdown)
    if section_match is None:
        raise AudiobookFlowValidationError("Could not find 'USE-002 Audiobook Flow Mapping' section.")

    return markdown[section_match.end() :]


def parse_steps(section_text: str) -> list[dict[str, object]]:
    matches = list(STEP_HEADING_PATTERN.finditer(section_text))
    if not matches:
        raise AudiobookFlowValidationError("No step headings found in USE-002 mapping section.")

    steps: list[dict[str, object]] = []
    for idx, match in enumerate(matches):
        step_number = int(match.group(1))
        step_title = _normalize_text(match.group(2))

        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(section_text)
        block = section_text[start:end]

        fields: dict[str, str] = {}
        for field_match in FIELD_PATTERN.finditer(block):
            key = _normalize_text(field_match.group(1))
            value = _normalize_text(field_match.group(2))
            fields[key] = value

        steps.append(
            {
                "number": step_number,
                "title": step_title,
                "fields": fields,
            }
        )

    return steps


def validate_use_002_mapping(path: Path) -> dict[str, int]:
    markdown = path.read_text(encoding="utf-8")
    section = extract_use_002_section(markdown)
    steps = parse_steps(section)

    step_numbers = [int(step["number"]) for step in steps]
    expected_numbers = list(range(1, len(steps) + 1))
    if step_numbers != expected_numbers:
        raise AudiobookFlowValidationError(
            f"Step numbers must be contiguous starting at 1. expected={expected_numbers} actual={step_numbers}"
        )

    if len(steps) < len(REQUIRED_ENDPOINTS):
        raise AudiobookFlowValidationError(
            f"USE-002 mapping must include at least {len(REQUIRED_ENDPOINTS)} steps, found {len(steps)}."
        )

    endpoints: list[str] = []
    for step in steps:
        fields = step["fields"]
        missing = REQUIRED_FIELD_KEYS - set(fields.keys())
        if missing:
            raise AudiobookFlowValidationError(
                f"Step {step['number']} is missing required fields: {sorted(missing)}"
            )

        endpoint = fields["api_endpoint"]
        if not ENDPOINT_PATTERN.match(endpoint):
            raise AudiobookFlowValidationError(
                f"Step {step['number']} has invalid api_endpoint format: {endpoint}"
            )
        endpoints.append(endpoint)

    if endpoints != REQUIRED_ENDPOINTS:
        raise AudiobookFlowValidationError(
            f"USE-002 endpoint sequence mismatch. expected={REQUIRED_ENDPOINTS} actual={endpoints}"
        )

    return {
        "steps": len(steps),
        "endpoints": len(endpoints),
    }
