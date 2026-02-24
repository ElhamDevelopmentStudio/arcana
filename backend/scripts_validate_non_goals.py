from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.non_goals_validation import load_non_goals  # noqa: E402
from app.scope_validation import load_and_parse_scope  # noqa: E402


def main() -> int:
    srs_path = ROOT / "SRS.md"
    docs_non_goals_path = ROOT / "docs" / "non_goals.md"

    srs_scope = load_and_parse_scope(srs_path, already_scope_section=False)
    srs_non_goals = srs_scope["shall_not"]
    docs_non_goals = load_non_goals(docs_non_goals_path)

    if docs_non_goals != srs_non_goals:
        print("Non-goals validation failed: docs/non_goals.md does not exactly match SRS.md §1.2 NIPE SHALL NOT list.")
        print(f"SRS non-goals count: {len(srs_non_goals)}")
        print(f"Docs non-goals count: {len(docs_non_goals)}")
        return 1

    print(f"Non-goals validation succeeded with {len(docs_non_goals)} non-goal items.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
