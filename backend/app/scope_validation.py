from __future__ import annotations

from pathlib import Path
import re


SCOPE_HEADING = "### 1.2 Scope"
SHALL_MARKER = "NIPE SHALL:"
SHALL_NOT_MARKER = "NIPE SHALL NOT:"
BULLET_PATTERN = re.compile(r"^\s*-\s+(.+?)\s*$")
SHALL_PATTERNS = (
    re.compile(r"^NIPE SHALL:\s*$"),
    re.compile(r"^NIPE SHALL\s*$"),
    re.compile(r"^##+\s*NIPE SHALL\s*$"),
)
SHALL_NOT_PATTERNS = (
    re.compile(r"^NIPE SHALL NOT:\s*$"),
    re.compile(r"^NIPE SHALL NOT\s*$"),
    re.compile(r"^##+\s*NIPE SHALL NOT\s*$"),
)


class ScopeValidationError(ValueError):
    pass


def extract_scope_section(markdown: str) -> str:
    heading_match = re.search(r"(?m)^### 1\.2 Scope\s*$", markdown)
    if heading_match is None:
        raise ScopeValidationError("Could not find scope heading in markdown content.")

    section_start = heading_match.start()
    search_tail = markdown[heading_match.end() :]
    next_h3_match = re.search(r"(?m)^###\s+.+$", search_tail)

    if next_h3_match is None:
        section_end = len(markdown)
    else:
        section_end = heading_match.end() + next_h3_match.start()

    return markdown[section_start:section_end]


def parse_scope_lists(scope_text: str) -> dict[str, list[str]]:
    shall_items: list[str] = []
    shall_not_items: list[str] = []
    mode: str | None = None

    for line in scope_text.splitlines():
        stripped = line.strip()
        if any(pattern.match(stripped) for pattern in SHALL_NOT_PATTERNS):
            mode = "shall_not"
            continue
        if any(pattern.match(stripped) for pattern in SHALL_PATTERNS):
            mode = "shall"
            continue

        bullet_match = BULLET_PATTERN.match(line)
        if bullet_match is None or mode is None:
            continue

        item = bullet_match.group(1).strip()
        if not item:
            continue
        if mode == "shall":
            shall_items.append(item)
        elif mode == "shall_not":
            shall_not_items.append(item)

    if not shall_items:
        raise ScopeValidationError("No NIPE SHALL items found in scope text.")
    if not shall_not_items:
        raise ScopeValidationError("No NIPE SHALL NOT items found in scope text.")

    return {"shall": shall_items, "shall_not": shall_not_items}


def load_and_parse_scope(path: Path, *, already_scope_section: bool = False) -> dict[str, list[str]]:
    markdown = path.read_text(encoding="utf-8")
    content = markdown if already_scope_section else extract_scope_section(markdown)
    return parse_scope_lists(content)
