from __future__ import annotations

import argparse
from pathlib import Path
import sys

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.main import app  # noqa: E402
from app.uc3_traceability import UC3TraceabilityError, run_uc3_traceability, write_uc3_report  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run UC-3 traceability flow (Draft novel -> Author diagnostics)."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "backend" / "reports" / "uc3_traceability_report.json",
        help="Path to write the UC-3 traceability JSON report.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        with TestClient(app) as client:
            report = run_uc3_traceability(client)
    except UC3TraceabilityError as exc:
        print(f"UC-3 traceability failed: {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"UC-3 traceability failed with unexpected error: {exc}")
        return 1

    write_uc3_report(args.output, report)
    print(
        "UC-3 traceability succeeded "
        f"(project_id={report['project_id']}, run_id={report['run_id']}, rerun_id={report['rerun_id']}, segments={report['segment_count']})."
    )
    print(f"Report written to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
