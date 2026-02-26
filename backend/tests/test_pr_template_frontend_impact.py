import subprocess
import sys
from pathlib import Path

from app.pr_template_frontend_impact_validation import (
    REQUIRED_PATTERN_MAP,
    validate_pr_template_frontend_impact,
)

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = ROOT / ".github" / "pull_request_template.md"
VALIDATION_SCRIPT_PATH = ROOT / "backend" / "scripts_validate_pr_template_frontend_impact.py"

EXPECTED_REQUIRED_KEYS = [
    "backend_api_change_declaration",
    "frontend_impact_review_checkbox",
    "paired_frontend_impact_heading",
    "frontend_impact_summary_field",
    "related_fe_task_ids_field",
    "deferred_fe_task_id_field",
]


def test_unit_required_pattern_snapshot() -> None:
    assert list(REQUIRED_PATTERN_MAP.keys()) == EXPECTED_REQUIRED_KEYS


def test_integration_pr_template_contains_paired_frontend_impact_note() -> None:
    stats = validate_pr_template_frontend_impact(TEMPLATE_PATH)
    assert stats["required_entries"] == len(EXPECTED_REQUIRED_KEYS)


def test_e2e_pr_template_frontend_impact_validation_cli_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATION_SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    assert "PR template frontend-impact validation succeeded" in result.stdout


def test_regression_pr_template_contains_required_heading_snapshot() -> None:
    markdown = TEMPLATE_PATH.read_text(encoding="utf-8")
    assert "## Paired frontend impact (required for backend/API changes)" in markdown
