#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare LibriTTS metadata for Coqui TTS")
    parser.add_argument(
        "--librtts-dir",
        type=Path,
        required=True,
        help="Path to LibriTTS root (contains train-clean-100, etc.)",
    )
    parser.add_argument(
        "--splits",
        type=str,
        default="train-clean-100",
        help="Comma-separated splits to include",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/datasets/librtts_metadata.csv"),
        help="Output metadata CSV",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.librtts_dir.exists():
        raise SystemExit(f"Missing LibriTTS dir: {args.librtts_dir}")

    splits = [s.strip() for s in args.splits.split(",") if s.strip()]
    entries = []
    for split in splits:
        split_dir = args.librtts_dir / split
        if not split_dir.exists():
            print(f"[WARN] Missing split: {split_dir}")
            continue
        for txt_path in split_dir.rglob("*.normalized.txt"):
            wav_path = txt_path.with_suffix("").with_suffix(".wav")
            if not wav_path.exists():
                continue
            try:
                text = txt_path.read_text(encoding="utf-8").strip()
            except Exception:
                continue
            if not text:
                continue
            # speaker id is parent of chapter dir
            parts = txt_path.parts
            speaker = parts[-3] if len(parts) >= 3 else "unknown"
            entries.append(f"{wav_path.as_posix()}|{text}|{speaker}")

    if not entries:
        raise SystemExit("No LibriTTS entries found")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(entries) + "\n", encoding="utf-8")
    print(f"[INFO] Wrote {len(entries)} entries to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
