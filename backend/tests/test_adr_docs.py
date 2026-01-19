import subprocess
import sys
from pathlib import Path

from app.adr_docs_validation import (
    EXPECTED_ADR_SPECS,
    collect_missing_required_sections,
    extract_adr_heading,
    validate_adr_docs,
)

ROOT = Path(__file__).resolve().parents[2]
ADR_DIR = ROOT / "docs" / "adrs"
VALIDATION_SCRIPT_PATH = ROOT / "backend" / "scripts_validate_adrs.py"

EXPECTED_ADR_FILENAMES = [spec["filename"] for spec in EXPECTED_ADR_SPECS]


def test_unit_extract_heading_and_required_sections() -> None:
    sample = """
# ADR-101: mode system profile snapshots
## Status
accepted
## Context
ctx
## Decision
decision
## Consequences
consequences
## Backend Impact
backend
## Frontend Impact
frontend
"""
    adr_id, title = extract_adr_heading(sample)
    assert adr_id == "ADR-101"
    assert "mode system" in title
    assert collect_missing_required_sections(sample) == []


def test_integration_adr_docs_cover_mode_tagging_and_llm_router() -> None:
    stats = validate_adr_docs(ADR_DIR)
    assert stats["adr_count"] == 3
    assert stats["accepted_count"] == 3


def test_e2e_adr_validation_cli_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATION_SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    assert "ADR validation succeeded" in result.stdout


def test_regression_adr_filename_snapshot() -> None:
    filenames = sorted(path.name for path in ADR_DIR.glob("ADR-*.md"))
    assert filenames == EXPECTED_ADR_FILENAMES

