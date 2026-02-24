import subprocess
import sys
from pathlib import Path

from app.success_criteria_validation import (
    extract_srs_success_criteria_section,
    load_doc_success_criteria,
    load_srs_success_criteria,
    parse_doc_checklist_ids,
    parse_doc_success_criteria_map,
    parse_srs_success_criteria_items,
)

ROOT = Path(__file__).resolve().parents[2]
SRS_PATH = ROOT / "SRS.md"
CHECKLIST_PATH = ROOT / "docs" / "shadow_slave_success_checklist.md"
VALIDATION_SCRIPT_PATH = ROOT / "backend" / "scripts_validate_shadow_slave_success.py"

EXPECTED_SRS_CRITERIA = [
    "a clean chapterized corpus",
    "a validated character map (name -> verbalized -> gender)",
    "a segmented, phonetic-normalized, tagged export suitable to feed into a TTS pipeline",
    "basic tension/emotion/dominance time-series and charts",
    "The system is deterministic enough to reproduce results with pinned configuration.",
]

EXPECTED_IDS = ["SC-001", "SC-002", "SC-003", "SC-004", "SC-005"]


def test_unit_parse_srs_success_criteria_items_extracts_expected_criteria() -> None:
    sample = """
### 1.3 Success Criteria (Product-Level)

- A user can take Shadow Slave input and obtain:
  - a clean chapterized corpus
  - a validated character map (name -> verbalized -> gender)
  - a segmented, phonetic-normalized, tagged export suitable to feed into a TTS pipeline
  - basic tension/emotion/dominance time-series and charts
- The system is deterministic enough to reproduce results with pinned configuration.

## 2. User Personas & Use Cases
"""
    section = extract_srs_success_criteria_section(sample)
    criteria = parse_srs_success_criteria_items(section)
    assert criteria == EXPECTED_SRS_CRITERIA


def test_unit_parse_doc_map_and_checklist_ids() -> None:
    sample = """
## Success Criteria Map (SRS 1.3)
- SC-001: a clean chapterized corpus
- SC-002: a validated character map (name -> verbalized -> gender)

## Per-Run Checklist Template (Shadow Slave)
- [ ] SC-001 verified for current run.
- [ ] SC-002 verified for current run.
"""
    pairs = parse_doc_success_criteria_map(sample)
    checklist_ids = parse_doc_checklist_ids(sample)

    assert pairs == [
        ("SC-001", "a clean chapterized corpus"),
        ("SC-002", "a validated character map (name -> verbalized -> gender)"),
    ]
    assert checklist_ids == ["SC-001", "SC-002"]


def test_integration_success_checklist_matches_srs_criteria() -> None:
    srs_items = load_srs_success_criteria(SRS_PATH)
    doc_pairs, doc_checklist_ids = load_doc_success_criteria(CHECKLIST_PATH)
    doc_ids = [pair[0] for pair in doc_pairs]
    doc_items = [pair[1] for pair in doc_pairs]

    assert srs_items == EXPECTED_SRS_CRITERIA
    assert doc_items == srs_items
    assert doc_ids == EXPECTED_IDS
    assert doc_checklist_ids == EXPECTED_IDS


def test_e2e_success_checklist_validation_cli_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATION_SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    assert "Success checklist validation succeeded" in result.stdout


def test_regression_success_criteria_snapshot() -> None:
    srs_items = load_srs_success_criteria(SRS_PATH)
    assert srs_items == EXPECTED_SRS_CRITERIA
