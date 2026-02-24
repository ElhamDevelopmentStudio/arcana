from __future__ import annotations

from pathlib import Path
import re

GLOSSARY_HEADING = "## 0. Glossary"
TERM_PATTERN = re.compile(r"^\s*-\s+\*\*(.+?)\*\*:\s*(.+)\s*$")


class GlossaryValidationError(ValueError):
    pass


def extract_glossary_section(markdown: str) -> str:
    heading_match = re.search(r"(?m)^## 0\. Glossary\s*$", markdown)
    if heading_match is None:
        raise GlossaryValidationError("Could not find glossary heading in markdown content.")

    section_start = heading_match.start()
    search_tail = markdown[heading_match.end() :]
    next_h2_match = re.search(r"(?m)^##\s+.+$", search_tail)

    if next_h2_match is None:
        section_end = len(markdown)
    else:
        section_end = heading_match.end() + next_h2_match.start()

    return markdown[section_start:section_end]


def parse_glossary_terms(glossary_section: str) -> list[tuple[str, str]]:
    terms: list[tuple[str, str]] = []

    for line in glossary_section.splitlines():
        match = TERM_PATTERN.match(line)
        if not match:
            continue
        term = match.group(1).strip()
        definition = match.group(2).strip()
        terms.append((term, definition))

    if not terms:
        raise GlossaryValidationError("No glossary terms were found in glossary section.")

    return terms


def load_and_parse_glossary(path: Path) -> list[tuple[str, str]]:
    markdown = path.read_text(encoding="utf-8")
    section = extract_glossary_section(markdown)
    return parse_glossary_terms(section)
