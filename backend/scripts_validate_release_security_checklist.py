from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.release_security_checklist_validation import (  # noqa: E402
    ReleaseSecurityChecklistValidationError,
    validate_release_security_checklist,
)


def main() -> int:
    doc_path = ROOT / "docs" / "release_security_review_checklist.md"

    try:
        stats = validate_release_security_checklist(doc_path)
    except ReleaseSecurityChecklistValidationError as exc:
        print(f"Release security checklist validation failed: {exc}")
        return 1

    print(
        "Release security checklist validation succeeded with "
        f"{stats['controls']} controls and {stats['required_fields']} required fields per control."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
