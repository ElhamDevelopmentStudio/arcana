#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ri_attr.gender_resolve import load_json, load_labels, resolve_chapter_blocks  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="STEP 8: resolve gender per dialogue block")
    parser.add_argument(
        "--blocks-dir",
        type=Path,
        default=Path("data/processed/blocks"),
        help="Directory with chapter_XXXX.blocks.json",
    )
    parser.add_argument(
        "--sentences-dir",
        type=Path,
        default=Path("data/processed/sentences"),
        help="Directory with chapter_XXXX.json",
    )
    parser.add_argument(
        "--alias-to-gender",
        type=Path,
        default=Path("data/name_map/derived/alias_to_gender.json"),
        help="Alias to gender map",
    )
    parser.add_argument(
        "--alias-to-canonical",
        type=Path,
        default=Path("data/name_map/derived/alias_to_canonical.json"),
        help="Alias to canonical map",
    )
    parser.add_argument(
        "--alias-to-speaker",
        type=Path,
        default=Path("data/name_map/derived/alias_to_speaker.json"),
        help="Alias to speaker map",
    )
    parser.add_argument(
        "--labels",
        type=Path,
        default=Path("data/processed/labels/labels.jsonl"),
        help="Labels JSONL for pronoun skipping",
    )
    parser.add_argument(
        "--no-labels",
        action="store_true",
        help="Disable labels.jsonl override",
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

    if not args.blocks_dir.exists():
        raise SystemExit(f"Missing blocks dir: {args.blocks_dir}")
    if not args.sentences_dir.exists():
        raise SystemExit(f"Missing sentences dir: {args.sentences_dir}")

    alias_to_gender = load_json(args.alias_to_gender)
    alias_to_canonical = load_json(args.alias_to_canonical)
    alias_to_speaker = load_json(args.alias_to_speaker)

    labels = None
    if not args.no_labels and args.labels.exists():
        labels = load_labels(args.labels)

    def _chapter_num(path: Path) -> int:
        try:
            return int(path.name.split("_", 1)[1].split(".")[0])
        except Exception:
            return 0

    block_files = sorted(args.blocks_dir.glob("chapter_*.blocks.json"), key=_chapter_num)
    if not block_files:
        raise SystemExit("No block files found")

    total_blocks = 0
    for block_path in block_files:
        chapter_num = int(block_path.stem.split("_")[-1].split(".")[0])
        sentences_path = _resolve_chapter_path(args.sentences_dir, chapter_num, ".json")
        if not sentences_path.exists():
            raise SystemExit(f"Missing sentences file: {sentences_path}")

        blocks_payload = load_json(block_path)
        chapter_payload = load_json(sentences_path)

        resolved = resolve_chapter_blocks(
            chapter_payload=chapter_payload,
            blocks_payload=blocks_payload,
            alias_to_gender=alias_to_gender,
            alias_to_canonical=alias_to_canonical,
            alias_to_speaker=alias_to_speaker,
            labels=labels,
        )

        out_path = block_path.with_suffix(".resolved.json")
        out_path.write_text(json.dumps(resolved, indent=2), encoding="utf-8")
        total_blocks += len(resolved.get("blocks", []))

    print(f"[INFO] Wrote {len(block_files)} resolved files")
    print(f"[INFO] Total blocks resolved: {total_blocks}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
