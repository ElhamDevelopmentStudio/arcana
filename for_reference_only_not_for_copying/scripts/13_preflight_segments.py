#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ri_attr.preflight import load_thresholds, run_preflight  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preflight checks for span segments")
    parser.add_argument(
        "--segments-dir",
        type=Path,
        default=Path("data/processed/span_segments"),
        help="Directory containing chapter_*.segments.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed/preflight"),
        help="Output directory for preflight reports",
    )
    parser.add_argument(
        "--thresholds",
        type=Path,
        default=Path("data/processed/preflight/thresholds.json"),
        help="Thresholds JSON file",
    )
    parser.add_argument(
        "--fail-on-violation",
        action="store_true",
        help="Exit with non-zero if any chapter violates thresholds",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.segments_dir.exists():
        raise SystemExit(f"Missing segments dir: {args.segments_dir}")

    def _chapter_num(path: Path) -> int:
        try:
            return int(path.name.split("_", 1)[1].split(".")[0])
        except Exception:
            return 0

    segment_files = sorted(args.segments_dir.glob("chapter_*.segments.json"), key=_chapter_num)
    if not segment_files:
        raise SystemExit("No segment files found")

    thresholds = load_thresholds(args.thresholds)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    any_violations = False
    summary = []
    for seg_path in segment_files:
        result = run_preflight(seg_path, thresholds)
        report = result.report
        chapter = report.get("chapter")
        out_path = args.output_dir / f"chapter_{chapter}.report.json"
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        summary.append(
            {
                "chapter": chapter,
                "segment_count": report.get("segment_count"),
                "short_ratio": report.get("stats", {}).get("short_ratio"),
                "transition_density": report.get("stats", {}).get("transition_density"),
                "violations": report.get("violations"),
            }
        )
        if result.violations:
            any_violations = True

    summary_path = args.output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"[INFO] Preflight reports written: {args.output_dir}")
    if any_violations:
        print("[WARN] Preflight violations detected")
        return 1 if args.fail_on_violation else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
