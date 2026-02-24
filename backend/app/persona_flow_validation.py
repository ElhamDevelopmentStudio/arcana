from __future__ import annotations

from pathlib import Path
import re


SRS_PERSONA_HEADING_PATTERN = re.compile(r"(?m)^###\s+2\.1 Personas\s*$")
SRS_PERSONA_END_PATTERN = re.compile(r"(?m)^###\s+2\.2 Primary Use Cases\s*$")
SRS_PERSONA_NAME_PATTERN = re.compile(r"(?m)^\d+\.\s+\*\*(.+?)\*\*\s*$")

DOC_PERSONA_HEADING_PATTERN = re.compile(r"(?m)^##\s+(.+?)\s+End-to-End Flow\s*$")
DOC_H2_PATTERN = re.compile(r"(?m)^##\s+.+$")
DOC_FIELD_PATTERN = re.compile(r"(?m)^\s*-\s+([a-z_]+):\s+(.+?)\s*$")
DOC_STEP_PATTERN = re.compile(r"(?m)^\s*\d+\.\s+(.+?)\s*$")

REQUIRED_DOC_FIELDS = {"flow_id", "objective", "expected_outcome"}
MIN_STEPS_PER_FLOW = 5


class PersonaFlowValidationError(ValueError):
    pass


def _normalize_text(text: str) -> str:
    return " ".join(text.split())


def extract_srs_persona_section(markdown: str) -> str:
    start_match = SRS_PERSONA_HEADING_PATTERN.search(markdown)
    if start_match is None:
        raise PersonaFlowValidationError("Could not find SRS persona section heading.")

    tail = markdown[start_match.end() :]
    end_match = SRS_PERSONA_END_PATTERN.search(tail)
    if end_match is None:
        raise PersonaFlowValidationError("Could not find SRS end boundary for persona section.")

    section_end = start_match.end() + end_match.start()
    return markdown[start_match.end() : section_end]


def parse_srs_persona_names(section_text: str) -> list[str]:
    names = [_normalize_text(match.group(1)) for match in SRS_PERSONA_NAME_PATTERN.finditer(section_text)]
    if not names:
        raise PersonaFlowValidationError("No persona names found in SRS persona section.")
    return names


def parse_doc_persona_sections(markdown: str) -> dict[str, str]:
    matches = list(DOC_PERSONA_HEADING_PATTERN.finditer(markdown))
    if not matches:
        raise PersonaFlowValidationError("No persona end-to-end flow sections found in doc.")

    sections: dict[str, str] = {}
    for idx, match in enumerate(matches):
        persona_name = _normalize_text(match.group(1))
        section_start = match.end()
        section_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(markdown)
        sections[persona_name] = markdown[section_start:section_end]

    return sections


def parse_doc_fields(section_text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for match in DOC_FIELD_PATTERN.finditer(section_text):
        key = _normalize_text(match.group(1))
        value = _normalize_text(match.group(2))
        fields[key] = value
    return fields


def parse_doc_steps(section_text: str) -> list[str]:
    return [_normalize_text(match.group(1)) for match in DOC_STEP_PATTERN.finditer(section_text)]


def validate_persona_flows(srs_path: Path, doc_path: Path) -> dict[str, int]:
    srs_markdown = srs_path.read_text(encoding="utf-8")
    doc_markdown = doc_path.read_text(encoding="utf-8")

    srs_personas = parse_srs_persona_names(extract_srs_persona_section(srs_markdown))
    doc_sections = parse_doc_persona_sections(doc_markdown)
    doc_personas = list(doc_sections.keys())

    if doc_personas != srs_personas:
        raise PersonaFlowValidationError(
            "Persona flow doc headings do not match SRS persona names/order. "
            f"expected={srs_personas} actual={doc_personas}"
        )

    seen_flow_ids: set[str] = set()
    total_steps = 0
    for persona_name in srs_personas:
        section_text = doc_sections[persona_name]
        fields = parse_doc_fields(section_text)
        steps = parse_doc_steps(section_text)

        missing_fields = REQUIRED_DOC_FIELDS - set(fields.keys())
        if missing_fields:
            raise PersonaFlowValidationError(
                f"Persona '{persona_name}' flow is missing required fields: {sorted(missing_fields)}"
            )

        flow_id = fields["flow_id"]
        if flow_id in seen_flow_ids:
            raise PersonaFlowValidationError(f"Duplicate flow_id detected: {flow_id}")
        seen_flow_ids.add(flow_id)

        if len(steps) < MIN_STEPS_PER_FLOW:
            raise PersonaFlowValidationError(
                f"Persona '{persona_name}' flow must have at least {MIN_STEPS_PER_FLOW} steps, found {len(steps)}."
            )

        total_steps += len(steps)

    return {
        "personas": len(srs_personas),
        "flows": len(doc_sections),
        "total_steps": total_steps,
    }
