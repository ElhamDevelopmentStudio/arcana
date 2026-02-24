#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ri_attr.chaptering import normalize_text, split_chapters, write_chapters  # noqa: E402


def _decode_bytes(data: bytes, source_name: str) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return data.decode("utf-8-sig")
        except UnicodeDecodeError:
            print(f"[ERROR] Encoding error in {source_name} (fatal)", file=sys.stderr)
            raise


def main() -> int:
    raw_dir = REPO_ROOT / "data" / "raw"
    out_dir = REPO_ROOT / "data" / "processed" / "raw_clean"

    raw_files = sorted(raw_dir.glob("*.txt"))
    if not raw_files:
        print("[ERROR] No .txt files found in data/raw/ (fatal)", file=sys.stderr)
        return 1

    print(f"[INFO] Processing {len(raw_files)} raw files")

    if out_dir.exists() and any(out_dir.iterdir()):
        print("[INFO] Overwriting existing files in data/processed/raw_clean/")

    out_dir.mkdir(parents=True, exist_ok=True)

    for raw_path in raw_files:
        try:
            data = raw_path.read_bytes()
            text = _decode_bytes(data, raw_path.name)
        except UnicodeDecodeError:
            return 1

        normalized = normalize_text(text)
        chapters = split_chapters(normalized)
        if chapters:
            written = write_chapters(chapters, out_dir)
            print(f"[INFO] Wrote {len(written)} chapters from {raw_path.name}")
        else:
            out_path = out_dir / raw_path.name
            out_path.write_text(normalized, encoding="utf-8")
            if not any(line for line in normalized.split("\n")):
                print(f"[WARN] File {raw_path.name} is empty after normalization", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
