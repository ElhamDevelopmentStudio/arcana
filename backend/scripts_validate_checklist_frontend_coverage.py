from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.checklist_frontend_coverage_validation import (  # noqa: E402
    ChecklistFrontendCoverageValidationError,
    validate_checklist_frontend_coverage,
)


def main() -> int:
    checklist_path = ROOT / "SRS_Expanded_Implementation_Checklist.md"
    try:
        stats = validate_checklist_frontend_coverage(checklist_path)
    except ChecklistFrontendCoverageValidationError as exc:
        print(f"Checklist frontend coverage validation failed: {exc}")
        return 1

    print(
        "Checklist frontend coverage validation succeeded with "
        f"{stats['fe_tasks']} FE tasks and {stats['pw_tasks']} PW tasks."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
