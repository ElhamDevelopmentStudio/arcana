#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build benchmark sets for transitions/emotion")
    parser.add_argument(
        "--segments-dir",
        type=Path,
        default=Path("data/processed/span_segments"),
        help="Directory containing chapter_*.segments.json",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/benchmarks"),
        help="Output directory for benchmark JSON files",
    )
    parser.add_argument(
        "--transition-count",
        type=int,
        default=80,
        help="Number of transition pairs to sample",
    )
    parser.add_argument(
        "--emotion-count",
        type=int,
        default=80,
        help="Number of emotion segments to sample",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=1337,
        help="Random seed",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    args = parse_args()
    if not args.segments_dir.exists():
        raise SystemExit(f"Missing segments dir: {args.segments_dir}")

    files = sorted(args.segments_dir.glob("chapter_*.segments.json"))
    if not files:
        raise SystemExit("No segment files found")

    transition_pairs = []
    emotion_segments = []

    for path in files:
        payload = load_json(path)
        chapter = payload.get("chapter")
        segments = payload.get("segments") or []
        for prev, cur in zip(segments, segments[1:]):
            prev_role = prev.get("speaker_role") or prev.get("speaker")
            cur_role = cur.get("speaker_role") or cur.get("speaker")
            prev_gender = prev.get("speaker_gender")
            cur_gender = cur.get("speaker_gender")
            if prev_role != cur_role or prev_gender != cur_gender:
                transition_pairs.append(
                    {
                        "chapter": chapter,
                        "from_segment_id": prev.get("segment_id"),
                        "to_segment_id": cur.get("segment_id"),
                        "from_speaker_role": prev_role,
                        "to_speaker_role": cur_role,
                        "from_text": prev.get("text", ""),
                        "to_text": cur.get("text", ""),
                    }
                )

        for seg in segments:
            label = seg.get("emotion", "neutral")
            if label != "neutral":
                emotion_segments.append(
                    {
                        "chapter": chapter,
                        "segment_id": seg.get("segment_id"),
                        "speaker_role": seg.get("speaker_role") or seg.get("speaker"),
                        "emotion": label,
                        "emotion_confidence": seg.get("emotion_confidence", 0.0),
                        "text": seg.get("text", ""),
                    }
                )

    random.seed(args.seed)
    random.shuffle(transition_pairs)
    random.shuffle(emotion_segments)

    transition_out = transition_pairs[: args.transition_count]
    emotion_out = sorted(
        emotion_segments, key=lambda s: s.get("emotion_confidence", 0.0), reverse=True
    )[: args.emotion_count]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "transition_eval.json").write_text(
        json.dumps(transition_out, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (args.out_dir / "emotion_eval.json").write_text(
        json.dumps(emotion_out, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"[INFO] Transition samples: {len(transition_out)}")
    print(f"[INFO] Emotion samples: {len(emotion_out)}")
    print(f"[INFO] Output dir: {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
