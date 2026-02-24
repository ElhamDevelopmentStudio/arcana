#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path


PHRASE_SUFFIXES = {
    "path",
    "rank",
    "move",
    "elder",
    "venerable",
    "aperture",
    "force",
}

HEAD_STOPWORDS = {
    "a",
    "an",
    "the",
    "this",
    "that",
    "to",
    "not",
    "of",
    "in",
    "on",
    "for",
    "with",
    "and",
    "or",
    "is",
    "was",
    "were",
    "be",
    "been",
    "as",
}

ALLOWED_MOVE_HEADS = {"killer"}
ALLOWED_VENERABLE_HEADS = {
    "immortal",
    "demon",
    "giant",
    "star",
    "red",
    "spectral",
    "heavenly",
    "limitless",
    "reckless",
    "thieving",
    "primordial",
    "genesis",
    "paradise",
}


def _load_text_files(raw_dir: Path) -> list[str]:
    files = sorted(raw_dir.glob("*.txt"))
    if not files:
        return []
    contents = []
    for path in files:
        contents.append(path.read_text(encoding="utf-8", errors="ignore"))
    return contents


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z]+", text.lower())


def _build_bigrams(tokens: list[str]) -> Counter:
    counts: Counter = Counter()
    for i in range(len(tokens) - 1):
        counts[f"{tokens[i]} {tokens[i + 1]}"] += 1
    return counts


def _build_trigrams(tokens: list[str]) -> Counter:
    counts: Counter = Counter()
    for i in range(len(tokens) - 2):
        counts[f"{tokens[i]} {tokens[i + 1]} {tokens[i + 2]}"] += 1
    return counts


def _suggest_rewrite(phrase: str) -> str | None:
    parts = phrase.split()
    if len(parts) == 2:
        head, tail = parts
        if tail == "path":
            if head in HEAD_STOPWORDS:
                return None
            return f"{head}-path"
        if head == "rank":
            return f"rank-{tail}"
        if tail in {"move", "elder", "venerable", "aperture"}:
            if head in HEAD_STOPWORDS:
                return None
            if tail == "move" and head not in ALLOWED_MOVE_HEADS:
                return None
            if tail == "venerable" and head not in ALLOWED_VENERABLE_HEADS:
                return None
            return f"{head}-{tail}"
        if phrase == "super force":
            return "superforce"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Suggest prosody rewrite candidates")
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/processed/raw_clean"),
        help="Directory with chapter_*.txt",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/pronunciation/prosody_candidates.json"),
        help="Output JSON file with candidates",
    )
    parser.add_argument(
        "--min-count",
        type=int,
        default=50,
        help="Minimum count for candidate phrases",
    )
    parser.add_argument(
        "--rewrite-file",
        type=Path,
        default=Path("data/pronunciation/prosody_rewrites.json"),
        help="Existing prosody rewrites file to exclude",
    )
    args = parser.parse_args()

    texts = _load_text_files(args.raw_dir)
    if not texts:
        print(f"[WARN] No text files found in {args.raw_dir}")
        return 1

    existing = set()
    if args.rewrite_file.exists():
        try:
            data = json.loads(args.rewrite_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                existing = {str(k).lower() for k in data.keys()}
        except Exception:
            existing = set()

    bigrams: Counter = Counter()
    trigrams: Counter = Counter()
    for text in texts:
        tokens = _tokenize(text)
        bigrams.update(_build_bigrams(tokens))
        trigrams.update(_build_trigrams(tokens))

    candidates = []
    for phrase, count in bigrams.most_common():
        if count < args.min_count:
            break
        if phrase in existing:
            continue
        tail = phrase.split()[-1]
        if tail not in PHRASE_SUFFIXES and phrase not in {"super force"}:
            continue
        suggestion = _suggest_rewrite(phrase)
        if suggestion:
            candidates.append({"phrase": phrase, "count": count, "suggested": suggestion})

    for phrase, count in trigrams.most_common():
        if count < args.min_count:
            break
        if phrase in existing:
            continue
        if phrase == "righteous path super force":
            candidates.append({"phrase": phrase, "count": count, "suggested": "righteouspath superforce"})

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(candidates, indent=2), encoding="utf-8")
    print(f"[INFO] Wrote {len(candidates)} candidates to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
