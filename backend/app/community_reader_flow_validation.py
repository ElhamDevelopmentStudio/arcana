from __future__ import annotations

from pathlib import Path
import re


DOC_SECTION_HEADING_PATTERN = re.compile(r"(?m)^##\s+USE-005 Community Reader Read-Only Dashboard Flow\s*$")
STEP_HEADING_PATTERN = re.compile(r"(?m)^###\s+Step\s+(\d+):\s+(.+?)\s*$")
FIELD_PATTERN = re.compile(r"(?m)^\s*-\s+([a-z_]+):\s+(.+?)\s*$")

REQUIRED_FIELD_KEYS = {"flow_id", "ui_view", "user_action", "dashboard_focus", "read_only_guardrail", "expected_outcome"}
EXPECTED_FLOW_ID = "FLOW-COMMUNITY-001"
EXPECTED_READ_ONLY_GUARDRAIL = "no create/update/delete operations allowed"
MIN_STEPS = 6

REQUIRED_DASHBOARD_FOCUS = {
    "project_summary",
    "chapter_trends",
    "character_trends",
    "emotion_tension_dominance_curves",
    "arc_filters",
    "insight_export",
}


class CommunityReaderFlowValidationError(ValueError):
    pass


def _normalize_text(text: str) -> str:
    return " ".join(text.split())


def extract_use_005_section(markdown: str) -> str:
    section_match = DOC_SECTION_HEADING_PATTERN.search(markdown)
    if section_match is None:
        raise CommunityReaderFlowValidationError(
            "Could not find 'USE-005 Community Reader Read-Only Dashboard Flow' section."
        )
    return markdown[section_match.end() :]


def parse_steps(section_text: str) -> list[dict[str, object]]:
    headings = list(STEP_HEADING_PATTERN.finditer(section_text))
    if not headings:
        raise CommunityReaderFlowValidationError("No step headings found in USE-005 flow section.")

    steps: list[dict[str, object]] = []
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

        steps.append(
            {
                "number": step_number,
                "title": step_title,
                "fields": fields,
            }
        )

    return steps


def validate_use_005_flow(path: Path) -> dict[str, int]:
    markdown = path.read_text(encoding="utf-8")
    section = extract_use_005_section(markdown)
    steps = parse_steps(section)

    numbers = [int(step["number"]) for step in steps]
    expected_numbers = list(range(1, len(steps) + 1))
    if numbers != expected_numbers:
        raise CommunityReaderFlowValidationError(
            f"Step numbers must be contiguous starting at 1. expected={expected_numbers} actual={numbers}"
        )

    if len(steps) < MIN_STEPS:
        raise CommunityReaderFlowValidationError(
            f"USE-005 flow must include at least {MIN_STEPS} steps, found {len(steps)}."
        )

    seen_views: set[str] = set()
    focus_coverage: set[str] = set()

    for step in steps:
        fields = step["fields"]
        missing = REQUIRED_FIELD_KEYS - set(fields.keys())
        if missing:
            raise CommunityReaderFlowValidationError(
                f"Step {step['number']} is missing required fields: {sorted(missing)}"
            )

        if fields["flow_id"] != EXPECTED_FLOW_ID:
            raise CommunityReaderFlowValidationError(
                f"Step {step['number']} has invalid flow_id. expected={EXPECTED_FLOW_ID} actual={fields['flow_id']}"
            )

        if fields["read_only_guardrail"] != EXPECTED_READ_ONLY_GUARDRAIL:
            raise CommunityReaderFlowValidationError(
                f"Step {step['number']} has invalid read_only_guardrail. "
                f"expected='{EXPECTED_READ_ONLY_GUARDRAIL}' actual='{fields['read_only_guardrail']}'"
            )

        ui_view = fields["ui_view"]
        if ui_view in seen_views:
            raise CommunityReaderFlowValidationError(f"Duplicate ui_view detected: {ui_view}")
        seen_views.add(ui_view)

        focus_coverage.add(fields["dashboard_focus"])

    missing_focus = REQUIRED_DASHBOARD_FOCUS - focus_coverage
    if missing_focus:
        raise CommunityReaderFlowValidationError(
            "USE-005 flow is missing required dashboard_focus coverage: " + ", ".join(sorted(missing_focus))
        )

    return {
        "steps": len(steps),
        "focus_coverage": len(focus_coverage),
    }
