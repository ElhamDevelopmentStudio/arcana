import subprocess
import sys
from pathlib import Path

from app.api_contract_changelog_validation import (
    extract_api_contract_changelog_section,
    parse_api_contract_changelog_entries,
    validate_api_contract_changelog,
)

ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = ROOT / "docs" / "api_contract_changelog.md"
VALIDATION_SCRIPT_PATH = ROOT / "backend" / "scripts_validate_api_contract_changelog.py"

EXPECTED_CHANGE_IDS = ["API-001", "API-002", "API-003", "API-004", "API-005", "API-006"]


def test_unit_extract_and_parse_api_contract_changelog_entries() -> None:
    sample = """
## API Contract Changelog (Frontend Maintainers)
| Change ID | Date | Backend/API change | Frontend impact | Source artifact | Status |
| --- | --- | --- | --- | --- | --- |
| API-001 | 2026-02-20 | Added field | Update schema | backend/tests/test_a.py | implemented |
| API-002 | 2026-02-21 | Added endpoint | Add UI hook | frontend/tests/e2e/test_b.ts | deferred |
"""
    section = extract_api_contract_changelog_section(sample)
    entries = parse_api_contract_changelog_entries(section)
    assert len(entries) == 2
    assert entries[0]["Change ID"] == "API-001"
    assert entries[1]["Status"] == "deferred"


def test_integration_api_contract_changelog_doc_is_valid() -> None:
    stats = validate_api_contract_changelog(DOC_PATH)
    assert stats["entries"] >= 6
    assert stats["deferred_entries"] == 0


def test_e2e_api_contract_changelog_validation_cli_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATION_SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    assert "API contract changelog validation succeeded" in result.stdout


def test_regression_api_contract_changelog_ids_snapshot() -> None:
    markdown = DOC_PATH.read_text(encoding="utf-8")
    entries = parse_api_contract_changelog_entries(extract_api_contract_changelog_section(markdown))
    ids = [entry["Change ID"] for entry in entries]
    assert ids == EXPECTED_CHANGE_IDS
