from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.academic_output_map_validation import AcademicOutputMapValidationError, validate_use_003_mapping  # noqa: E402


def main() -> int:
    mapping_path = ROOT / "docs" / "academic_outputs_export_mapping.md"

    try:
        stats = validate_use_003_mapping(mapping_path)
    except AcademicOutputMapValidationError as exc:
        print(f"Academic outputs mapping validation failed: {exc}")
        return 1

    print(
        "Academic outputs mapping validation succeeded with "
        f"{stats['outputs']} output mappings and {stats['format_coverage']} covered export formats."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
