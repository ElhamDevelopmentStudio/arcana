from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.api_contract_changelog_validation import (  # noqa: E402
    APIContractChangelogValidationError,
    validate_api_contract_changelog,
)


def main() -> int:
    doc_path = ROOT / "docs" / "api_contract_changelog.md"
    try:
        stats = validate_api_contract_changelog(doc_path)
    except APIContractChangelogValidationError as exc:
        print(f"API contract changelog validation failed: {exc}")
        return 1

    print(
        "API contract changelog validation succeeded with "
        f"{stats['entries']} entries and {stats['deferred_entries']} deferred entries."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
