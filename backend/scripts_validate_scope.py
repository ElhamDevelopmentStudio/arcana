from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.scope_validation import load_and_parse_scope  # noqa: E402


def main() -> int:
    srs_path = ROOT / "SRS.md"
    docs_scope_path = ROOT / "docs" / "scope.md"

    srs_scope = load_and_parse_scope(srs_path, already_scope_section=False)
    docs_scope = load_and_parse_scope(docs_scope_path, already_scope_section=True)

    if srs_scope != docs_scope:
        print("Scope validation failed: docs/scope.md does not exactly match SRS.md §1.2 SHALL/SHALL NOT lists.")
        print(f"SRS SHALL count: {len(srs_scope['shall'])}, docs SHALL count: {len(docs_scope['shall'])}")
        print(
            f"SRS SHALL NOT count: {len(srs_scope['shall_not'])}, docs SHALL NOT count: {len(docs_scope['shall_not'])}"
        )
        return 1

    print(
        "Scope validation succeeded with "
        f"{len(docs_scope['shall'])} SHALL items and {len(docs_scope['shall_not'])} SHALL NOT items."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
