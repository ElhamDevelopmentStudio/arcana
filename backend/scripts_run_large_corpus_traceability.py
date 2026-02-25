from __future__ import annotations

import argparse
from pathlib import Path
import sys

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.large_corpus_traceability_regression import (  # noqa: E402
    LargeCorpusTraceabilityError,
    run_large_corpus_traceability,
    write_large_corpus_report,
)
from app.main import app  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run USE-009 optional slow large-corpus regression suite "
            "(UC1/UC2/UC3 with deterministic rerun checks)."
        )
    )
    parser.add_argument(
        "--novel-path",
        type=Path,
        default=ROOT / "novels_extra_chapter_0_to_22.txt",
        help="Path to a TXT novel fixture used for large-corpus traceability.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "backend" / "reports" / "large_corpus_traceability_report.json",
        help="Path to write the USE-009 JSON report.",
    )
    parser.add_argument(
        "--allow-slow",
        action="store_true",
        help="Required opt-in flag for running the slow regression suite.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.allow_slow:
        print("Refusing to run slow suite without --allow-slow.")
        return 2

    try:
        with TestClient(app) as client:
            report = run_large_corpus_traceability(client, args.novel_path)
    except LargeCorpusTraceabilityError as exc:
        print(f"USE-009 large-corpus traceability failed: {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"USE-009 large-corpus traceability failed with unexpected error: {exc}")
        return 1

    write_large_corpus_report(args.output, report)
    print(
        "USE-009 large-corpus traceability succeeded "
        f"(project_id={report['project_id']}, chapter_count={report['chapter_count']})."
    )
    for mode_report in report["modes"]:
        print(
            f"  mode={mode_report['mode']} run_id={mode_report['run_id']} "
            f"rerun_id={mode_report['rerun_id']} segments={mode_report['segment_count']} "
            f"deterministic={mode_report['deterministic']}"
        )
    print(f"Report written to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
