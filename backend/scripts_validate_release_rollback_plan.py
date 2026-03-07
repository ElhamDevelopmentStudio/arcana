from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.release_rollback_plan_validation import (  # noqa: E402
    ReleaseRollbackPlanValidationError,
    validate_release_rollback_plan,
)


def main() -> int:
    doc_path = ROOT / "docs" / "release_rollback_plan_template.md"

    try:
        stats = validate_release_rollback_plan(doc_path)
    except ReleaseRollbackPlanValidationError as exc:
        print(f"Release rollback plan validation failed: {exc}")
        return 1

    print(
        "Release rollback plan validation succeeded with "
        f"{stats['sections']} sections and {stats['required_fields']} required fields per section."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
