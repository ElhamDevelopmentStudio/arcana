from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.author_diagnostic_map_validation import AuthorDiagnosticMapValidationError, validate_use_004_mapping  # noqa: E402


def main() -> int:
    mapping_path = ROOT / "docs" / "author_diagnostic_requirements_mapping.md"

    try:
        stats = validate_use_004_mapping(mapping_path)
    except AuthorDiagnosticMapValidationError as exc:
        print(f"Author diagnostics mapping validation failed: {exc}")
        return 1

    print(
        "Author diagnostics mapping validation succeeded with "
        f"{stats['requirements']} requirements and {stats['coverage_categories']} coverage categories."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
