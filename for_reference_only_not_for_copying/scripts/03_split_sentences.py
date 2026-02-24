#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pysbd


def _load_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print(f"[ERROR] Encoding error in {path.name} (fatal)", file=sys.stderr)
        raise


def _segment_text(text: str, segmenter: pysbd.Segmenter) -> list[dict]:
    sentences = []
    spans = segmenter.segment(text)
    for idx, span in enumerate(spans, start=1):
        if not hasattr(span, "start") or not hasattr(span, "end"):
            raise ValueError("pysbd returned segments without character spans")

        start = span.start
        end = span.end
        if not isinstance(start, int) or not isinstance(end, int):
            raise ValueError("pysbd character spans must be integers")
        if start < 0 or end < start or end > len(text):
            raise ValueError(f"Invalid span offsets: {start}-{end} for text length {len(text)}")

        sentence_text = text[start:end]
        sentences.append(
            {
                "sid": "",  # filled by caller with chapter context
                "text": sentence_text,
                "char_start": start,
                "char_end": end,
            }
        )
    return sentences


CHAPTER_FILE_RE = re.compile(r"^chapter_(\d+)\.txt$")


def _chapter_number(path: Path) -> int | None:
    match = CHAPTER_FILE_RE.match(path.name)
    if not match:
        return None
    return int(match.group(1))


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    input_dir = repo_root / "data" / "processed" / "raw_clean"
    output_dir = repo_root / "data" / "processed" / "sentences"

    all_txt = sorted(input_dir.glob("*.txt"))
    chapter_files = [path for path in all_txt if _chapter_number(path) is not None]
    input_files = (
        sorted(chapter_files, key=lambda p: _chapter_number(p) or 0)
        if chapter_files
        else all_txt
    )
    if not input_files:
        print("[ERROR] No .txt files found in data/processed/raw_clean/ (fatal)", file=sys.stderr)
        return 1

    print(f"[INFO] Processing {len(input_files)} cleaned files")
    if output_dir.exists() and any(output_dir.iterdir()):
        print("[INFO] Overwriting existing files in data/processed/sentences/")

    output_dir.mkdir(parents=True, exist_ok=True)

    segmenter = pysbd.Segmenter(language="en", clean=False, char_span=True)

    for chapter_index, source_path in enumerate(input_files, start=1):
        try:
            text = _load_text(source_path)
        except UnicodeDecodeError:
            return 1

        sentences = _segment_text(text, segmenter)
        chapter_num = _chapter_number(source_path) or chapter_index
        for sentence_index, sentence in enumerate(sentences, start=1):
            sentence["sid"] = f"{chapter_num}-{sentence_index:06d}"

        payload = {
            "chapter": chapter_num,
            "source_file": source_path.name,
            "sentences": sentences,
        }

        output_path = (
            output_dir / f"chapter_{chapter_num}.json"
            if _chapter_number(source_path) is not None
            else output_dir / f"chapter_{chapter_index:04d}.json"
        )
        output_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
