from __future__ import annotations

from pathlib import Path
import re

from app.success_criteria_validation import load_srs_success_criteria


ARCH_OBJECTIVES_HEADING_PATTERN = re.compile(r"(?m)^##\s+Architecture Objectives\s*$")
DETERMINISM_GUARDRAILS_HEADING_PATTERN = re.compile(r"(?m)^##\s+Determinism Baseline Guardrails\s*$")
H2_HEADING_PATTERN = re.compile(r"(?m)^##\s+.+$")
BULLET_PATTERN = re.compile(r"^\s*-\s+(.+?)\s*$")
MIN_GUARDRAILS = 3


class ArchitectureValidationError(ValueError):
    pass


def extract_h2_section(markdown: str, heading_pattern: re.Pattern[str]) -> str:
    heading_match = heading_pattern.search(markdown)
    if heading_match is None:
        raise ArchitectureValidationError("Could not find expected architecture section heading.")

    search_tail = markdown[heading_match.end() :]
    next_h2_match = H2_HEADING_PATTERN.search(search_tail)

    if next_h2_match is None:
        section_end = len(markdown)
    else:
        section_end = heading_match.end() + next_h2_match.start()

    return markdown[heading_match.end() : section_end]


def parse_bullets(section_text: str) -> list[str]:
    bullets: list[str] = []
    for line in section_text.splitlines():
        match = BULLET_PATTERN.match(line)
        if match is None:
            continue
        bullets.append(" ".join(match.group(1).split()))

    if not bullets:
        raise ArchitectureValidationError("No bullet lines found in architecture section.")

    return bullets


def load_architecture_sections(path: Path) -> tuple[list[str], list[str]]:
    markdown = path.read_text(encoding="utf-8")
    objectives = parse_bullets(extract_h2_section(markdown, ARCH_OBJECTIVES_HEADING_PATTERN))
    guardrails = parse_bullets(extract_h2_section(markdown, DETERMINISM_GUARDRAILS_HEADING_PATTERN))
    return objectives, guardrails


def validate_architecture_determinism(srs_path: Path, architecture_path: Path) -> dict[str, int]:
    srs_criteria = load_srs_success_criteria(srs_path)
    expected_objective = srs_criteria[-1]

    objectives, guardrails = load_architecture_sections(architecture_path)

    if expected_objective not in objectives:
        raise ArchitectureValidationError("Architecture objectives section is missing the SRS deterministic objective.")

    if len(guardrails) < MIN_GUARDRAILS:
        raise ArchitectureValidationError(
            f"Determinism guardrails section must contain at least {MIN_GUARDRAILS} bullet items."
        )

    return {
        "objectives": len(objectives),
        "guardrails": len(guardrails),
    }
