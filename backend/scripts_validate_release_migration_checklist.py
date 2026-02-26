from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.release_migration_checklist_validation import (  # noqa: E402
    ReleaseMigrationChecklistValidationError,
    validate_release_migration_checklist,
)


def main() -> int:
    doc_path = ROOT / "docs" / "release_migration_backward_compatibility_checklist.md"

    try:
        stats = validate_release_migration_checklist(doc_path)
    except ReleaseMigrationChecklistValidationError as exc:
        print(f"Release migration checklist validation failed: {exc}")
        return 1

    print(
        "Release migration checklist validation succeeded with "
        f"{stats['items']} items and {stats['required_fields']} required fields per item."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
