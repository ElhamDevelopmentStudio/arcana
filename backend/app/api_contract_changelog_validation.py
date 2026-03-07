from __future__ import annotations

from pathlib import Path
import re


REQUIRED_SECTION_HEADING_PATTERN = re.compile(
    r"(?m)^##\s+API Contract Changelog \(Frontend Maintainers\)\s*$"
)
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CHANGE_ID_PATTERN = re.compile(r"^API-(\d{3})$")

EXPECTED_HEADER = [
    "Change ID",
    "Date",
    "Backend/API change",
    "Frontend impact",
    "Source artifact",
    "Status",
]
MIN_ENTRIES = 5
ALLOWED_STATUSES = {"implemented", "deferred", "planned"}


class APIContractChangelogValidationError(ValueError):
    pass


def _split_table_row(row: str) -> list[str]:
    stripped = row.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        raise APIContractChangelogValidationError(f"Invalid table row format: {row}")
    return [cell.strip() for cell in stripped[1:-1].split("|")]


def extract_api_contract_changelog_section(markdown: str) -> str:
    match = REQUIRED_SECTION_HEADING_PATTERN.search(markdown)
    if match is None:
        raise APIContractChangelogValidationError(
            "Could not find 'API Contract Changelog (Frontend Maintainers)' section."
        )
    return markdown[match.end() :]


def parse_api_contract_changelog_entries(section: str) -> list[dict[str, str]]:
    table_lines = [line.strip() for line in section.splitlines() if line.strip().startswith("|")]
    if len(table_lines) < 3:
        raise APIContractChangelogValidationError("API contract changelog must include a markdown table with entries.")

    header = _split_table_row(table_lines[0])
    if header != EXPECTED_HEADER:
        raise APIContractChangelogValidationError(
            f"API contract changelog header mismatch. expected={EXPECTED_HEADER} actual={header}"
        )

    entries: list[dict[str, str]] = []
    for raw_line in table_lines[2:]:
        cells = _split_table_row(raw_line)
        if len(cells) != len(EXPECTED_HEADER):
            raise APIContractChangelogValidationError(
                f"API contract changelog row has {len(cells)} columns; expected {len(EXPECTED_HEADER)}."
            )
        entries.append(dict(zip(EXPECTED_HEADER, cells, strict=True)))

    return entries


def validate_api_contract_changelog(path: Path) -> dict[str, int]:
    markdown = path.read_text(encoding="utf-8")
    section = extract_api_contract_changelog_section(markdown)
    entries = parse_api_contract_changelog_entries(section)

    if len(entries) < MIN_ENTRIES:
        raise APIContractChangelogValidationError(
            f"API contract changelog must include at least {MIN_ENTRIES} entries, found {len(entries)}."
        )

    change_ids: list[int] = []
    deferred_count = 0
    for entry in entries:
        raw_change_id = entry["Change ID"]
        id_match = CHANGE_ID_PATTERN.match(raw_change_id)
        if id_match is None:
            raise APIContractChangelogValidationError(f"Invalid Change ID format: {raw_change_id}")
        change_ids.append(int(id_match.group(1)))

        if DATE_PATTERN.match(entry["Date"]) is None:
            raise APIContractChangelogValidationError(f"Invalid date format: {entry['Date']}")

        frontend_impact = entry["Frontend impact"].strip()
        if not frontend_impact or frontend_impact == "-":
            raise APIContractChangelogValidationError(f"Frontend impact must be populated for {raw_change_id}.")

        source_artifact = entry["Source artifact"].strip()
        if not source_artifact or source_artifact == "-":
            raise APIContractChangelogValidationError(f"Source artifact must be populated for {raw_change_id}.")

        status = entry["Status"].strip().lower()
        if status not in ALLOWED_STATUSES:
            raise APIContractChangelogValidationError(
                f"Invalid status '{entry['Status']}' for {raw_change_id}; allowed={sorted(ALLOWED_STATUSES)}."
            )
        if status == "deferred":
            deferred_count += 1

    expected_ids = list(range(1, len(entries) + 1))
    if change_ids != expected_ids:
        raise APIContractChangelogValidationError(
            f"Change IDs must be contiguous from API-001. expected={expected_ids} actual={change_ids}"
        )

    return {
        "entries": len(entries),
        "deferred_entries": deferred_count,
    }
