from __future__ import annotations

from pathlib import Path
import re


H2_HEADING_PATTERN = re.compile(r"(?m)^##\s+.+$")
ADR_TITLE_PATTERN = re.compile(r"(?m)^#\s+(ADR-\d{3}):\s+(.+?)\s*$")

REQUIRED_SECTIONS = [
    "Status",
    "Context",
    "Decision",
    "Consequences",
    "Backend Impact",
    "Frontend Impact",
]

EXPECTED_ADR_SPECS = [
    {"filename": "ADR-101-mode-system.md", "adr_id": "ADR-101", "topic": "mode"},
    {"filename": "ADR-102-tagging-pipeline.md", "adr_id": "ADR-102", "topic": "tagging"},
    {"filename": "ADR-103-llm-router-failover.md", "adr_id": "ADR-103", "topic": "llm router"},
]


class AdrDocsValidationError(ValueError):
    pass


def _extract_h2_section(markdown: str, heading: str) -> str:
    heading_pattern = re.compile(rf"(?m)^##\s+{re.escape(heading)}\s*$")
    heading_match = heading_pattern.search(markdown)
    if heading_match is None:
        raise AdrDocsValidationError(f"Missing required section heading: '## {heading}'.")

    search_tail = markdown[heading_match.end() :]
    next_h2 = H2_HEADING_PATTERN.search(search_tail)
    if next_h2 is None:
        section_end = len(markdown)
    else:
        section_end = heading_match.end() + next_h2.start()

    return markdown[heading_match.end() : section_end]


def extract_adr_heading(markdown: str) -> tuple[str, str]:
    title_match = ADR_TITLE_PATTERN.search(markdown)
    if title_match is None:
        raise AdrDocsValidationError("ADR file must start with title format '# ADR-XXX: <title>'.")
    return title_match.group(1), title_match.group(2)


def collect_missing_required_sections(markdown: str) -> list[str]:
    missing: list[str] = []
    for section in REQUIRED_SECTIONS:
        if re.search(rf"(?m)^##\s+{re.escape(section)}\s*$", markdown) is None:
            missing.append(section)
    return missing


def validate_adr_docs(adr_dir: Path) -> dict[str, int]:
    if not adr_dir.exists() or not adr_dir.is_dir():
        raise AdrDocsValidationError(f"ADR directory not found: {adr_dir}")

    accepted_count = 0
    for spec in EXPECTED_ADR_SPECS:
        path = adr_dir / spec["filename"]
        if not path.exists():
            raise AdrDocsValidationError(f"Missing ADR file: {path.name}")

        markdown = path.read_text(encoding="utf-8")
        adr_id, adr_title = extract_adr_heading(markdown)
        if adr_id != spec["adr_id"]:
            raise AdrDocsValidationError(
                f"ADR ID mismatch for {path.name}. expected={spec['adr_id']} actual={adr_id}"
            )

        if spec["topic"] not in adr_title.lower():
            raise AdrDocsValidationError(
                f"ADR title for {path.name} must include topic keyword '{spec['topic']}'."
            )

        missing_sections = collect_missing_required_sections(markdown)
        if missing_sections:
            raise AdrDocsValidationError(
                f"ADR {adr_id} is missing required sections: {missing_sections}"
            )

        status_section = _extract_h2_section(markdown, "Status").strip().lower()
        if "accepted" not in status_section:
            raise AdrDocsValidationError(f"ADR {adr_id} must have status 'accepted'.")
        accepted_count += 1

    return {
        "adr_count": len(EXPECTED_ADR_SPECS),
        "accepted_count": accepted_count,
    }

