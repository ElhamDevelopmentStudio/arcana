from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.adr_docs_validation import AdrDocsValidationError, validate_adr_docs  # noqa: E402


def main() -> int:
    adr_dir = ROOT / "docs" / "adrs"

    try:
        stats = validate_adr_docs(adr_dir)
    except AdrDocsValidationError as exc:
        print(f"ADR validation failed: {exc}")
        return 1

    print(
        "ADR validation succeeded with "
        f"{stats['adr_count']} ADR(s) and {stats['accepted_count']} accepted ADR(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

