#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ri_attr.final_segments import build_segments, load_json, load_labels, load_preds  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="STEP 9: build final TTS segments")
    parser.add_argument(
        "--sentences-dir",
        type=Path,
        default=Path("data/processed/sentences"),
        help="Directory with chapter_XXXX.json",
    )
    parser.add_argument(
        "--blocks-dir",
        type=Path,
        default=Path("data/processed/blocks"),
        help="Directory with chapter_XXXX.blocks.resolved.json",
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
        "--no-labels",
        action="store_true",
        help="Disable labels.jsonl override",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed/final_segments"),
        help="Output directory for segments",
    )
    return parser.parse_args()


def _resolve_chapter_path(directory: Path, chapter_num: int, suffix: str) -> Path:
    candidates = [
        directory / f"chapter_{chapter_num}{suffix}",
        directory / f"chapter_{chapter_num:04d}{suffix}",
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def main() -> int:
    args = parse_args()

    if not args.sentences_dir.exists():
        raise SystemExit(f"Missing sentences dir: {args.sentences_dir}")
    if not args.blocks_dir.exists():
        raise SystemExit(f"Missing blocks dir: {args.blocks_dir}")
    if not args.preds.exists():
        raise SystemExit(f"Missing predictions file: {args.preds}")

    preds = load_preds(args.preds)
    labels = None
    if not args.no_labels and args.labels.exists():
        labels = load_labels(args.labels)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    def _chapter_num(path: Path) -> int:
        try:
            return int(path.name.split("_", 1)[1].split(".")[0])
        except Exception:
            return 0

    block_files = sorted(args.blocks_dir.glob("chapter_*.blocks.resolved.json"), key=_chapter_num)
    if not block_files:
        raise SystemExit("No resolved block files found")

    total_segments = 0
    for block_path in block_files:
        chapter_num = int(block_path.name.split("_")[1].split(".")[0])
        sentences_path = _resolve_chapter_path(args.sentences_dir, chapter_num, ".json")
        if not sentences_path.exists():
            raise SystemExit(f"Missing sentences file: {sentences_path}")

        chapter_payload = load_json(sentences_path)
        blocks_payload = load_json(block_path)

        result = build_segments(
            chapter_payload=chapter_payload,
            blocks_payload=blocks_payload,
            preds=preds,
            labels=labels,
        )

        out_path = args.output_dir / f"chapter_{chapter_num}.segments.json"
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        total_segments += len(result.get("segments", []))

    print(f"[INFO] Wrote {len(block_files)} chapter segment files")
    print(f"[INFO] Total segments: {total_segments}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
