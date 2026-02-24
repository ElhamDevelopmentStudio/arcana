#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare VCTK metadata for Coqui TTS")
    parser.add_argument(
        "--vctk-dir",
        type=Path,
        required=True,
        help="Path to VCTK root (contains wav48/ and txt/)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/datasets/vctk_metadata.csv"),
        help="Output metadata CSV",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.vctk_dir.exists():
        raise SystemExit(f"Missing VCTK dir: {args.vctk_dir}")

    wav_dir = args.vctk_dir / "wav48"
    txt_dir = args.vctk_dir / "txt"
    if not wav_dir.exists() or not txt_dir.exists():
        raise SystemExit("Expected wav48/ and txt/ directories in VCTK root")

    entries = []
    for wav_path in wav_dir.rglob("*.wav"):
        rel = wav_path.relative_to(wav_dir)
        txt_path = (txt_dir / rel).with_suffix(".txt")
        if not txt_path.exists():
            continue
        try:
            text = txt_path.read_text(encoding="utf-8").strip()
        except Exception:
            continue
        if not text:
            continue
        speaker = rel.parts[0] if rel.parts else "unknown"
        entries.append(f"{wav_path.as_posix()}|{text}|{speaker}")

    if not entries:
        raise SystemExit("No VCTK entries found")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(entries) + "\n", encoding="utf-8")
    print(f"[INFO] Wrote {len(entries)} entries to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
