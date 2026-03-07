from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.mvp_release_gate_validation import MVPReleaseGateValidationError, validate_mvp_release_gate  # noqa: E402


def main() -> int:
    checklist_path = ROOT / "SRS_Expanded_Implementation_Checklist.md"
    try:
        stats = validate_mvp_release_gate(checklist_path)
    except MVPReleaseGateValidationError as exc:
        print(f"MVP release gate validation failed: {exc}")
        return 1

    print(
        "MVP release gate validation succeeded with "
        f"{stats['included_task_count']} MVP include tasks complete and "
        f"{stats['excluded_backlog_count']} excluded backlog labels ignored as non-blocking."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

