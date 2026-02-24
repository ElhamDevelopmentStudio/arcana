#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


CHAPTER_RE = re.compile(r"^chapter_(\d+)\.json$")


def _load_chapter(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path.name}: {exc}") from exc


def _extract_chapter_number(filename: str) -> int | None:
    match = CHAPTER_RE.match(filename)
    if not match:
        return None
    return int(match.group(1))


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    sentences_dir = repo_root / "data" / "processed" / "sentences"
    output_dir = repo_root / "data" / "processed" / "windows"
    output_path = output_dir / "windows.jsonl"

    if not sentences_dir.exists():
        print(
            "[ERROR] Missing directory data/processed/sentences/ (fatal)",
            file=sys.stderr,
        )
        return 1

    all_json_files = sorted(sentences_dir.glob("*.json"))
    chapter_files = []
    ignored = False
    for path in all_json_files:
        if CHAPTER_RE.match(path.name):
            chapter_files.append(path)
        else:
            ignored = True

    if ignored:
        print("[WARN] Ignoring non-chapter files in sentences directory", file=sys.stderr)

    if not chapter_files:
        print(
            "[ERROR] No chapter_XXXX.json files found in data/processed/sentences/ (fatal)",
            file=sys.stderr,
        )
        return 1

    print(f"[INFO] Loaded {len(chapter_files)} chapters")

    output_dir.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        print("[INFO] Overwriting existing windows.jsonl")

    total_windows = 0
    with output_path.open("w", encoding="utf-8", newline="\n") as out_handle:
        for chapter_path in chapter_files:
            expected_chapter = _extract_chapter_number(chapter_path.name)
            if expected_chapter is None:
                continue

            try:
                payload = _load_chapter(chapter_path)
            except ValueError as exc:
                print(f"[ERROR] {exc}", file=sys.stderr)
                return 1

            actual_chapter = payload.get("chapter")
            if actual_chapter != expected_chapter:
                print(
                    f"[ERROR] Chapter mismatch in {chapter_path.name}: "
                    f"filename={expected_chapter} payload={actual_chapter} (fatal)",
                    file=sys.stderr,
                )
                return 1

            sentences = payload.get("sentences")
            if not isinstance(sentences, list):
                print(
                    f"[ERROR] Invalid sentences list in {chapter_path.name} (fatal)",
                    file=sys.stderr,
                )
                return 1

            if len(sentences) == 0:
                print(
                    f"[WARN] Chapter {expected_chapter} has zero sentences",
                    file=sys.stderr,
                )

            for idx, sentence in enumerate(sentences):
                if not isinstance(sentence, dict) or "text" not in sentence or "sid" not in sentence:
                    print(
                        f"[ERROR] Invalid sentence entry in {chapter_path.name} (fatal)",
                        file=sys.stderr,
                    )
                    return 1

                prev_slice = sentences[max(0, idx - 2) : idx]
                next_slice = sentences[idx + 1 : idx + 3]

                window = {
                    "sid": sentence["sid"],
                    "chapter": expected_chapter,
                    "prev": [item["text"] for item in prev_slice],
                    "cur": sentence["text"],
                    "next": [item["text"] for item in next_slice],
                }

                out_handle.write(json.dumps(window, ensure_ascii=False) + "\n")
                total_windows += 1

    print(f"[INFO] Built {total_windows} windows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
