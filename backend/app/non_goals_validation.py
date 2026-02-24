from __future__ import annotations

from pathlib import Path
import re


NON_GOALS_HEADING_PATTERN = re.compile(r"(?m)^##\s+Explicit Non-Goals\s*$")
H2_HEADING_PATTERN = re.compile(r"(?m)^##\s+.+$")
BULLET_PATTERN = re.compile(r"^\s*-\s+(.+?)\s*$")


class NonGoalsValidationError(ValueError):
    pass


def extract_non_goals_section(markdown: str) -> str:
    heading_match = NON_GOALS_HEADING_PATTERN.search(markdown)
    if heading_match is None:
        raise NonGoalsValidationError("Could not find '## Explicit Non-Goals' heading in markdown content.")

    search_tail = markdown[heading_match.end() :]
    next_h2_match = H2_HEADING_PATTERN.search(search_tail)

    if next_h2_match is None:
        section_end = len(markdown)
    else:
        section_end = heading_match.end() + next_h2_match.start()

    return markdown[heading_match.end() : section_end]


def parse_non_goal_items(non_goals_text: str) -> list[str]:
    items: list[str] = []
    for line in non_goals_text.splitlines():
        bullet_match = BULLET_PATTERN.match(line)
        if bullet_match is None:
            continue

        item = bullet_match.group(1).strip()
        if item:
            items.append(item)

    if not items:
        raise NonGoalsValidationError("No non-goal bullet items found in non-goals section.")

    return items


def load_non_goals(path: Path) -> list[str]:
    markdown = path.read_text(encoding="utf-8")
    section = extract_non_goals_section(markdown)
    return parse_non_goal_items(section)
