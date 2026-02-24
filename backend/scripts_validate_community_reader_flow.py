from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.community_reader_flow_validation import CommunityReaderFlowValidationError, validate_use_005_flow  # noqa: E402


def main() -> int:
    flow_path = ROOT / "docs" / "community_reader_readonly_dashboard_flow.md"

    try:
        stats = validate_use_005_flow(flow_path)
    except CommunityReaderFlowValidationError as exc:
        print(f"Community reader flow validation failed: {exc}")
        return 1

    print(
        "Community reader flow validation succeeded with "
        f"{stats['steps']} read-only steps and {stats['focus_coverage']} dashboard focus categories."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
