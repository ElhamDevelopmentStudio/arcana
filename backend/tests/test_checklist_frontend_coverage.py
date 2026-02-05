import subprocess
import sys
from pathlib import Path

from app.checklist_frontend_coverage_validation import (
    REQUIRED_ACCEPTANCE_NOTES_RULE,
    extract_frontend_task_ids,
    validate_checklist_frontend_coverage,
)

ROOT = Path(__file__).resolve().parents[2]
CHECKLIST_PATH = ROOT / "SRS_Expanded_Implementation_Checklist.md"
VALIDATION_SCRIPT_PATH = ROOT / "backend" / "scripts_validate_checklist_frontend_coverage.py"


def test_unit_extract_frontend_task_ids() -> None:
    sample = """
- [ ] [FE-001] First
- [x] [FE-002] Second
- [ ] [PW-001] Visual
- [ ] [PW-002] E2E
"""
    assert extract_frontend_task_ids(sample, "FE") == [1, 2]
    assert extract_frontend_task_ids(sample, "PW") == [1, 2]


def test_integration_checklist_contains_parallel_frontend_and_playwright_coverage() -> None:
    stats = validate_checklist_frontend_coverage(CHECKLIST_PATH)
    assert stats["fe_tasks"] >= 80
    assert stats["pw_tasks"] >= 15


def test_integration_checklist_contains_feature_slice_acceptance_notes_policy() -> None:
    markdown = CHECKLIST_PATH.read_text(encoding="utf-8")
    assert REQUIRED_ACCEPTANCE_NOTES_RULE in markdown


def test_e2e_checklist_frontend_coverage_validation_cli_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATION_SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    assert "Checklist frontend coverage validation succeeded" in result.stdout


def test_regression_frontend_and_playwright_task_count_snapshot() -> None:
    markdown = CHECKLIST_PATH.read_text(encoding="utf-8")
    fe_ids = extract_frontend_task_ids(markdown, "FE")
    pw_ids = extract_frontend_task_ids(markdown, "PW")
    assert len(fe_ids) == 85
    assert len(pw_ids) == 20
