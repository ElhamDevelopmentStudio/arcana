import subprocess
import sys
from pathlib import Path

from app.mvp_release_gate_validation import evaluate_mvp_release_gate, validate_mvp_release_gate, MVPReleaseGateValidationError


ROOT = Path(__file__).resolve().parents[2]
CHECKLIST_PATH = ROOT / "SRS_Expanded_Implementation_Checklist.md"
VALIDATION_SCRIPT_PATH = ROOT / "backend" / "scripts_validate_mvp_release_gate.py"


def test_unit_release_gate_ignores_excluded_mvp_backlog_items() -> None:
    sample = """
- [x] [MVP-001] Verify ingest supports TXT + chapter directory paths.
- [x] [MVP-011] Verify incremental append update flow.
- [ ] [MVP-012] Add explicit backlog labels for excluded “nice-to-have” features.
- `[BACKLOG][MVP-EXCLUDED][NICE-TO-HAVE]` full motif recurrence modeling.
"""
    result = evaluate_mvp_release_gate(sample)
    assert result["is_ready"] is True
    assert result["blocking_tasks"] == []
    assert result["excluded_backlog_count"] == 1


def test_unit_release_gate_blocks_on_incomplete_mvp_include_task() -> None:
    sample = """
- [ ] [MVP-005] Verify pronunciation overrides and preview.
- `[BACKLOG][MVP-EXCLUDED][NICE-TO-HAVE]` community sentiment overlay.
"""
    result = evaluate_mvp_release_gate(sample)
    assert result["is_ready"] is False
    assert result["blocking_tasks"] == ["MVP-005"]


def test_unit_release_gate_requires_excluded_backlog_labels() -> None:
    sample = """
- [x] [MVP-001] Verify ingest supports TXT + chapter directory paths.
- [x] [MVP-011] Verify incremental append update flow.
"""
    try:
        evaluate_mvp_release_gate(sample)
    except MVPReleaseGateValidationError as exc:
        assert "missing `[BACKLOG][MVP-EXCLUDED][NICE-TO-HAVE]` labels" in str(exc)
        return
    raise AssertionError("Expected MVPReleaseGateValidationError when exclude labels are missing.")


def test_integration_release_gate_succeeds_for_repository_checklist() -> None:
    stats = validate_mvp_release_gate(CHECKLIST_PATH)
    assert stats["is_ready"] is True
    assert stats["included_task_count"] >= 11
    assert stats["excluded_backlog_count"] >= 4


def test_e2e_release_gate_validation_cli_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATION_SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    assert "MVP release gate validation succeeded" in result.stdout

