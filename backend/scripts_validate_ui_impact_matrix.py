from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.ui_impact_matrix_validation import UIImpactMatrixValidationError, validate_ui_impact_matrix  # noqa: E402


def main() -> int:
    doc_path = ROOT / "docs" / "frontend_ui_impact_matrix.md"
    try:
        stats = validate_ui_impact_matrix(doc_path)
    except UIImpactMatrixValidationError as exc:
        print(f"UI impact matrix validation failed: {exc}")
        return 1

    print(
        "UI impact matrix validation succeeded with "
        f"{stats['entries']} entries and {stats['required_srs_sections']} required SRS section buckets."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
