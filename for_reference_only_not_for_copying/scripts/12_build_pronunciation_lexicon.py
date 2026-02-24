#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path


BASE_LEXICON = {
    "gu": "goo",
    "dao": "dow",
    "qi": "chee",
    "xian": "shee-en",
    "xianxia": "shee-en-shyah",
}

STOPWORDS = {
    "the",
    "and",
    "a",
    "an",
    "to",
    "of",
    "in",
    "is",
    "it",
    "that",
    "as",
    "for",
    "with",
    "was",
    "were",
    "on",
    "by",
    "at",
    "from",
    "this",
    "be",
    "or",
    "not",
    "are",
    "their",
    "they",
    "you",
    "we",
    "he",
    "she",
    "his",
    "her",
    "them",
    "but",
    "had",
    "have",
    "has",
    "will",
    "would",
    "can",
    "could",
    "should",
    "may",
    "might",
}


def _normalize_key(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _load_text_files(raw_dir: Path) -> list[str]:
    files = sorted(raw_dir.glob("*.txt"))
    if not files:
        return []
    contents = []
    for path in files:
        contents.append(path.read_text(encoding="utf-8", errors="ignore"))
    return contents


def _extract_candidate_terms(text: str) -> Counter:
    tokens = re.findall(r"[A-Za-z][A-Za-z']+", text)
    counts: Counter = Counter()
    for token in tokens:
        norm = token.lower()
        if norm in STOPWORDS:
            continue
        counts[norm] += 1
    return counts


def _load_aliases(repo_root: Path) -> set[str]:
    alias_path = repo_root / "data" / "name_map" / "derived" / "alias_to_canonical.json"
    if not alias_path.exists():
        return set()
    try:
        data = json.loads(alias_path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    if not isinstance(data, dict):
        return set()
    return {key.lower() for key in data.keys()}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build pronunciation lexicon")
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/processed/raw_clean"),
        help="Directory with chapter_*.txt",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/pronunciation"),
        help="Output directory for lexicon JSON files",
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=200,
        help="Max candidate terms to output for review",
    )
    parser.add_argument(
        "--min-count",
        type=int,
        default=25,
        help="Minimum count for candidate terms",
    )
    return_args = parser.parse_args()

    texts = _load_text_files(return_args.raw_dir)
    if not texts:
        print(f"[WARN] No text files found in {return_args.raw_dir}")
        return 1

    combined_counts: Counter = Counter()
    for text in texts:
        combined_counts.update(_extract_candidate_terms(text))

    repo_root = Path(__file__).resolve().parents[1]
    aliases = _load_aliases(repo_root)

    return_args.output_dir.mkdir(parents=True, exist_ok=True)
    lexicon_path = return_args.output_dir / "lexicon.json"
    overrides_path = return_args.output_dir / "lexicon_overrides.json"
    candidates_path = return_args.output_dir / "candidates.json"

    base_lexicon = {_normalize_key(k): v for k, v in BASE_LEXICON.items()}

    lexicon_path.write_text(json.dumps(base_lexicon, indent=2), encoding="utf-8")
    if not overrides_path.exists():
        overrides_path.write_text("{}", encoding="utf-8")

    candidates = []
    for term, count in combined_counts.most_common(return_args.max_candidates):
        if count < return_args.min_count:
            continue
        if term in aliases:
            continue
        candidates.append({"term": term, "count": count})
    candidates_path.write_text(json.dumps(candidates, indent=2), encoding="utf-8")

    print(f"[INFO] Lexicon written: {lexicon_path}")
    print(f"[INFO] Overrides template: {overrides_path}")
    print(f"[INFO] Candidate terms: {candidates_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
