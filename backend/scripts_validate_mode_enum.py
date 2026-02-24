from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.mode_enum_validation import ModeEnumValidationError, validate_mode_001_contract  # noqa: E402


def main() -> int:
    doc_path = ROOT / "docs" / "system_modes.md"

    try:
        stats = validate_mode_001_contract(doc_path)
    except ModeEnumValidationError as exc:
        print(f"Mode enum validation failed: {exc}")
        return 1

    print(
        "Mode enum validation succeeded with "
        f"{stats['mode_count']} modes and {stats['persistence_paths']} persistence path(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
