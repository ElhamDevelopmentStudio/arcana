from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.export_schema_contributor_doc_validation import (  # noqa: E402
    ExportSchemaContributorDocValidationError,
    validate_export_schema_contributor_guide,
)


def main() -> int:
    doc_path = ROOT / "docs" / "contributor_evolve_export_schema_safely.md"

    try:
        stats = validate_export_schema_contributor_guide(doc_path)
    except ExportSchemaContributorDocValidationError as exc:
        print(f"Contributor export-schema guide validation failed: {exc}")
        return 1

    print(
        "Contributor export-schema guide validation succeeded with "
        f"{stats['steps']} steps and {stats['required_fields']} required fields per step."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
