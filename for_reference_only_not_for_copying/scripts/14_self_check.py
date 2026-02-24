#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ri_attr.chaptering import normalize_text, split_chapters  # noqa: E402
from ri_attr.tts_generate import (  # noqa: E402
    apply_phonetics,
    apply_laughter_rewrites,
    apply_prosody_rewrites,
    build_lexicon_regex,
    build_prosody_rewrite_rules,
)


def test_chapter_split() -> None:
    sample = (
        "Chapter 1: First\n"
        "Chapter 1: First The opening line.\n"
        "More text.\n"
        "Chapter 2: Second\n"
        "Second content.\n"
        "Chapter 2: Second\n"
        "Extra.\n"
    )
    chapters = split_chapters(normalize_text(sample))
    assert len(chapters) == 2, "Expected 2 chapters"
    assert chapters[0].number == 1
    assert chapters[1].number == 2
    assert chapters[0].lines[0].startswith("Chapter 1")
    assert "The opening line." in "\n".join(chapters[0].lines)
    assert "Second content." in "\n".join(chapters[1].lines)


def test_lexicon() -> None:
    lexicon = {"gu": "goo"}
    lexicon_regex = build_lexicon_regex(lexicon)
    alias_regex = re.compile(r"$^")  # no-op
    text = "Gu Immortal guards Gus."
    rewritten = apply_phonetics(text, alias_regex, {}, lexicon_regex=lexicon_regex, lexicon=lexicon)
    assert "goo Immortal" in rewritten
    assert "Gus" in rewritten


def test_prosody_rewrites() -> None:
    rewrites = {"hehehe": "heh heh heh", "righteous path": "righteous-path"}
    rules = build_prosody_rewrite_rules(rewrites)
    assert apply_prosody_rewrites("Hehehe.", rules) == "heh heh heh."
    assert apply_prosody_rewrites("righteous path", rules) == "righteous-path"


def test_laughter_rewrites() -> None:
    assert apply_laughter_rewrites("Hehehe. You are wrong.") == "heh heh heh. You are wrong."
    assert apply_laughter_rewrites("Hahaha! Great job.") == "ha ha ha! Great job."


def main() -> int:
    test_chapter_split()
    test_lexicon()
    test_prosody_rewrites()
    test_laughter_rewrites()
    print("[INFO] Self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
