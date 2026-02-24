#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ri_attr.blocking import (  # noqa: E402
    Thresholds,
    build_blocks_for_chapter,
    iter_chapter_files,
    load_labels,
    load_preds,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="STEP 7: build dialogue blocks")
    parser.add_argument(
        "--sentences-dir",
        type=Path,
        default=Path("data/processed/sentences"),
        help="Directory with chapter_XXXX.json files",
    )
    parser.add_argument(
        "--preds",
        type=Path,
        default=Path("data/processed/predictions/mode_preds.jsonl"),
        help="Mode prediction JSONL",
    )
    parser.add_argument(
        "--labels",
        type=Path,
        default=Path("data/processed/labels/labels.jsonl"),
        help="Labels JSONL (optional override)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed/blocks"),
        help="Output directory for blocks",
    )
    parser.add_argument(
        "--no-labels",
        action="store_true",
        help="Disable labeled override",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.sentences_dir.exists():
        raise SystemExit(f"Missing sentences dir: {args.sentences_dir}")
    if not args.preds.exists():
        raise SystemExit(f"Missing predictions file: {args.preds}")

    preds = load_preds(args.preds)
    labels = None
    if not args.no_labels and args.labels.exists():
        labels = load_labels(args.labels)

    thresholds = Thresholds()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    chapters = list(iter_chapter_files(args.sentences_dir))
    if not chapters:
        raise SystemExit("No chapter_*.json files found")

    total_blocks = 0
    for chapter_path in chapters:
        result = build_blocks_for_chapter(
            chapter_path=chapter_path,
            preds=preds,
            labels=labels,
            thresholds=thresholds,
            use_labels=not args.no_labels,
        )
        chapter_num = result.get("chapter")
        out_path = args.output_dir / f"chapter_{int(chapter_num)}.blocks.json"
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        total_blocks += len(result.get("blocks", []))

    print(f"[INFO] Wrote {len(chapters)} chapter block files")
    print(f"[INFO] Total blocks: {total_blocks}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
