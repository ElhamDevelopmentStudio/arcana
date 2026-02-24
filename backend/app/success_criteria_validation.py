from __future__ import annotations

from pathlib import Path
import re


SRS_SUCCESS_HEADING_PATTERN = re.compile(r"(?m)^###\s+1\.3 Success Criteria \(Product-Level\)\s*$")
LEVEL2_HEADING_PATTERN = re.compile(r"(?m)^##\s+.+$")
DOC_CRITERION_PATTERN = re.compile(r"^\s*-\s*(SC-\d{3}):\s+(.+?)\s*$")
DOC_CHECKBOX_PATTERN = re.compile(r"^\s*-\s*\[[ xX]\]\s*(SC-\d{3})\s+verified for current run\.\s*$")
BULLET_PATTERN = re.compile(r"^\s*-\s+(.+?)\s*$")


class SuccessCriteriaValidationError(ValueError):
    pass


def _normalize_text(text: str) -> str:
    return " ".join(text.replace("→", "->").split())


def extract_srs_success_criteria_section(markdown: str) -> str:
    heading_match = SRS_SUCCESS_HEADING_PATTERN.search(markdown)
    if heading_match is None:
        raise SuccessCriteriaValidationError("Could not find SRS success criteria heading.")

    search_tail = markdown[heading_match.end() :]
    next_level2 = LEVEL2_HEADING_PATTERN.search(search_tail)
    if next_level2 is None:
        section_end = len(markdown)
    else:
        section_end = heading_match.end() + next_level2.start()

    return markdown[heading_match.end() : section_end]


def parse_srs_success_criteria_items(section_text: str) -> list[str]:
    items: list[str] = []
    in_shadow_slave_block = False

    for raw_line in section_text.splitlines():
        stripped = raw_line.strip()
        bullet_match = BULLET_PATTERN.match(stripped)
        if bullet_match is None:
            continue

        item = _normalize_text(bullet_match.group(1))
        if item == "A user can take Shadow Slave input and obtain:":
            in_shadow_slave_block = True
            continue

        if in_shadow_slave_block and not item.startswith("The system is"):
            items.append(item)
            continue

        if item.startswith("The system is deterministic enough to reproduce results with pinned configuration."):
            items.append(item)
            in_shadow_slave_block = False

    if len(items) != 5:
        raise SuccessCriteriaValidationError(
            f"Expected 5 SRS success criteria items for Shadow Slave, found {len(items)}."
        )

    return items


def parse_doc_success_criteria_map(markdown: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for line in markdown.splitlines():
        match = DOC_CRITERION_PATTERN.match(line)
        if match is None:
            continue
        criterion_id = match.group(1).strip()
        criterion_text = _normalize_text(match.group(2).strip())
        pairs.append((criterion_id, criterion_text))

    if not pairs:
        raise SuccessCriteriaValidationError("No SC-xxx criterion mappings found in checklist doc.")

    return pairs


def parse_doc_checklist_ids(markdown: str) -> list[str]:
    ids: list[str] = []
    for line in markdown.splitlines():
        match = DOC_CHECKBOX_PATTERN.match(line)
        if match is None:
            continue
        ids.append(match.group(1).strip())

    if not ids:
        raise SuccessCriteriaValidationError("No checklist verification lines found in checklist doc.")

    return ids


def load_srs_success_criteria(path: Path) -> list[str]:
    markdown = path.read_text(encoding="utf-8")
    section = extract_srs_success_criteria_section(markdown)
    return parse_srs_success_criteria_items(section)


def load_doc_success_criteria(path: Path) -> tuple[list[tuple[str, str]], list[str]]:
    markdown = path.read_text(encoding="utf-8")
    pairs = parse_doc_success_criteria_map(markdown)
    checklist_ids = parse_doc_checklist_ids(markdown)
    return pairs, checklist_ids
