#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


QUOTE_RE = re.compile(r"[\"“”«»]")
SPEECH_VERB_RE = re.compile(
    r"\b(said|asked|replied|answered|shouted|whispered|murmured|cried|"
    r"called|yelled|snapped|ordered|remarked|responded|explained|announced|declared)\b",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build heuristic turn labels from windows.jsonl")
    parser.add_argument(
        "--windows",
        type=Path,
        default=Path("data/processed/windows/windows.jsonl"),
        help="Windows JSONL path",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/turns/turn_labels.jsonl"),
        help="Output labels JSONL",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.windows.exists():
        raise SystemExit(f"Missing windows file: {args.windows}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with args.windows.open("r", encoding="utf-8") as handle, args.output.open(
        "w", encoding="utf-8", newline="\n"
    ) as out:
        for line in handle:
            if not line.strip():
                continue
            entry = json.loads(line)
            sid = entry.get("sid")
            cur = entry.get("cur", "")
            if not sid:
                continue
            label = "NARRATION"
            if QUOTE_RE.search(cur):
                label = "TURN_START"
            elif SPEECH_VERB_RE.search(cur):
                label = "TURN_CONTINUE"
            out.write(json.dumps({"sid": sid, "label": label, "confidence": 0.6}) + "\n")
            total += 1

    print(f"[INFO] Wrote {total} labels to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
