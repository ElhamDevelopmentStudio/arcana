from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.performance_regression_gate import (  # noqa: E402
    collect_core_pipeline_performance_metrics,
    evaluate_performance_regression_gate,
    load_performance_regression_thresholds,
)

DEFAULT_THRESHOLDS_PATH = ROOT / "backend" / "performance_regression_thresholds.json"
DEFAULT_OUTPUT_PATH = ROOT / "backend" / "reports" / "performance_regression_gate_report.json"
DEFAULT_DATABASE_URL = "sqlite:///./test_nipe_performance_regression_gate.db"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run core pipeline performance regression gate and fail on threshold regressions.",
    )
    parser.add_argument(
        "--thresholds",
        type=Path,
        default=DEFAULT_THRESHOLDS_PATH,
        help="Path to per-mode performance thresholds JSON.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Path to write performance regression gate report JSON.",
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=DEFAULT_DATABASE_URL,
        help="Database URL used for the local gate run.",
    )
    return parser.parse_args()


def _write_report(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    args = _parse_args()

    os.environ["DATABASE_URL"] = args.database_url

    from app.config import clear_settings_cache  # noqa: WPS433
    from app.database import init_db, reset_engine  # noqa: WPS433
    from app.main import app  # noqa: WPS433
    from fastapi.testclient import TestClient  # noqa: WPS433

    clear_settings_cache()
    reset_engine()
    init_db()

    try:
        thresholds = load_performance_regression_thresholds(args.thresholds)
        with TestClient(app) as client:
            metrics = collect_core_pipeline_performance_metrics(client)
        gate_result = evaluate_performance_regression_gate(metrics=metrics, thresholds=thresholds)
    except Exception as exc:  # noqa: BLE001
        print(f"Performance regression gate failed with unexpected error: {exc}")
        return 1
    finally:
        reset_engine()
        clear_settings_cache()

    payload: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "thresholds_path": str(args.thresholds),
        "thresholds": thresholds,
        "metrics": metrics,
        "gate_result": gate_result,
    }
    _write_report(args.output, payload)

    if not bool(gate_result["gate_passed"]):
        print("Performance regression gate failed.")
        for violation in gate_result["violations"]:
            print(f"- violation: {violation}")
        print(f"Report written to: {args.output}")
        return 1

    print("Performance regression gate passed.")
    for mode, mode_payload in gate_result["by_mode"].items():
        print(
            f"- mode={mode} total_duration_ms={mode_payload['total_duration_ms']} "
            f"threshold_ms={mode_payload['threshold_ms']}"
        )
    print(f"Report written to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
