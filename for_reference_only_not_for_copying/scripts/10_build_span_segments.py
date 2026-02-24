#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ri_attr.span_segments import (  # noqa: E402
    build_span_segments,
    load_json,
    load_labels,
    load_preds,
    load_emotion_policy,
    load_turn_preds,
)
from ri_attr.director_llm import (  # noqa: E402
    SiliconFlowDirector,
    load_llm_router_from_env,
    load_siliconflow_from_env,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="STEP 10: build span-level TTS segments")
    parser.add_argument(
        "--sentences-dir",
        type=Path,
        default=Path("data/processed/sentences"),
        help="Directory with chapter_XXXX.json",
    )
    parser.add_argument(
        "--blocks-dir",
        type=Path,
        default=Path("data/processed/blocks"),
        help="Directory with chapter_XXXX.blocks.resolved.json",
    )
    parser.add_argument(
        "--preds",
        type=Path,
        default=Path("data/processed/predictions/mode_preds.jsonl"),
        help="Mode prediction JSONL",
    )
    parser.add_argument(
        "--labels",
        type=Path,
        default=Path("data/processed/labels/labels.jsonl"),
        help="Labels JSONL (optional override)",
    )
    parser.add_argument(
        "--no-labels",
        action="store_true",
        help="Disable labels.jsonl override",
    )
    parser.add_argument(
        "--alias-to-gender",
        type=Path,
        default=Path("data/name_map/derived/alias_to_gender.json"),
        help="Alias to gender map",
    )
    parser.add_argument(
        "--alias-to-canonical",
        type=Path,
        default=Path("data/name_map/derived/alias_to_canonical.json"),
        help="Alias to canonical map",
    )
    parser.add_argument(
        "--alias-to-speaker",
        type=Path,
        default=Path("data/name_map/derived/alias_to_speaker.json"),
        help="Alias to speaker map",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed/span_segments"),
        help="Output directory for span segments",
    )
    parser.add_argument(
        "--chapter",
        type=str,
        default="all",
        help='Chapter number to process (e.g. "2139") or "all"',
    )
    parser.add_argument(
        "--include-spans",
        action="store_true",
        help="Include raw spans in output for debugging",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Enable SiliconFlow LLM fallback for ambiguous quotes",
    )
    parser.add_argument(
        "--llm-model",
        type=str,
        default="",
        help="Override SiliconFlow model name",
    )
    parser.add_argument(
        "--llm-base-url",
        type=str,
        default="",
        help="Override SiliconFlow base URL",
    )
    parser.add_argument(
        "--llm-min-confidence",
        type=float,
        default=0.6,
        help="Minimum LLM confidence to accept assignment",
    )
    parser.add_argument(
        "--llm-max-calls",
        type=int,
        default=0,
        help="Max LLM calls per run (0 = unlimited)",
    )
    parser.add_argument(
        "--llm-max-quotes",
        type=int,
        default=12,
        help="Max quote spans per LLM call",
    )
    parser.add_argument(
        "--llm-cache",
        type=Path,
        default=Path("data/processed/llm_cache.json"),
        help="Cache file for LLM assignments",
    )
    parser.add_argument(
        "--emotion-mode",
        type=str,
        default="off",
        choices=["off", "heuristic", "llm", "llm_if_low"],
        help="Emotion tagging mode (default: off)",
    )
    parser.add_argument(
        "--emotion-scope",
        type=str,
        default="dialogue",
        choices=["dialogue", "all"],
        help="Which segments receive emotion tags",
    )
    parser.add_argument(
        "--emotion-llm-max-calls",
        type=int,
        default=10,
        help="Max LLM calls for emotion tagging (0 = unlimited)",
    )
    parser.add_argument(
        "--emotion-llm-min-confidence",
        type=float,
        default=0.8,
        help="Minimum confidence to accept LLM emotion labels",
    )
    parser.add_argument(
        "--emotion-llm-max-segments",
        type=int,
        default=8,
        help="Max segments per LLM emotion call",
    )
    parser.add_argument(
        "--emotion-llm-cache",
        type=Path,
        default=Path("data/processed/emotion_cache.json"),
        help="Cache file for LLM emotion labels",
    )
    parser.add_argument(
        "--emotion-context-chars",
        type=int,
        default=320,
        help="Max context chars per segment for LLM emotion",
    )
    parser.add_argument(
        "--emotion-policy",
        type=Path,
        default=Path("data/emotion/emotion_policy_dynamic.json"),
        help="Emotion policy JSON for gating/thresholds",
    )
    parser.add_argument(
        "--turn-preds",
        type=Path,
        default=Path("data/processed/turns/turn_preds.jsonl"),
        help="Optional turn prediction JSONL",
    )
    parser.add_argument(
        "--turn-min-confidence",
        type=float,
        default=0.6,
        help="Min confidence for turn start boundaries",
    )
    return parser.parse_args()


def _resolve_chapter_path(directory: Path, chapter_num: int, suffix: str) -> Path:
    candidates = [
        directory / f"chapter_{chapter_num}{suffix}",
        directory / f"chapter_{chapter_num:04d}{suffix}",
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def main() -> int:
    args = parse_args()

    if not args.sentences_dir.exists():
        raise SystemExit(f"Missing sentences dir: {args.sentences_dir}")
    if not args.blocks_dir.exists():
        raise SystemExit(f"Missing blocks dir: {args.blocks_dir}")
    if not args.preds.exists():
        raise SystemExit(f"Missing predictions file: {args.preds}")

    preds = load_preds(args.preds)
    labels = None
    if not args.no_labels and args.labels.exists():
        labels = load_labels(args.labels)

    alias_to_gender = load_json(args.alias_to_gender)
    alias_to_canonical = load_json(args.alias_to_canonical)
    alias_to_speaker = load_json(args.alias_to_speaker)

    director = None
    need_llm = args.use_llm or args.emotion_mode in {"llm", "llm_if_low"}
    if need_llm:
        director = load_llm_router_from_env() or load_siliconflow_from_env()
        if director is None:
            if args.use_llm:
                raise SystemExit("Missing SILICONFLOW_API_KEY for LLM fallback")
            print("[WARN] Missing SILICONFLOW_API_KEY; falling back to heuristic emotion mode")
            args.emotion_mode = "heuristic"
        else:
            if args.llm_model or args.llm_base_url:
                if hasattr(director, "providers"):
                    providers = getattr(director, "providers")
                    if providers:
                        if args.llm_model:
                            providers[0].model = args.llm_model
                        if args.llm_base_url:
                            providers[0].base_url = args.llm_base_url
                elif isinstance(director, SiliconFlowDirector):
                    director = SiliconFlowDirector(
                        api_key=director.api_key,
                        model=args.llm_model or director.model,
                        base_url=args.llm_base_url or director.base_url,
                        max_tokens=director.max_tokens,
                        temperature=director.temperature,
                    )

    llm_cache: dict | None = None
    if args.use_llm:
        if args.llm_cache.exists():
            try:
                llm_cache = json.loads(args.llm_cache.read_text(encoding="utf-8"))
            except Exception:
                llm_cache = {}
        else:
            llm_cache = {}

    emotion_cache: dict | None = None
    if args.emotion_mode in {"llm", "llm_if_low"}:
        if args.emotion_llm_cache.exists():
            try:
                emotion_cache = json.loads(args.emotion_llm_cache.read_text(encoding="utf-8"))
            except Exception:
                emotion_cache = {}
        else:
            emotion_cache = {}

    args.output_dir.mkdir(parents=True, exist_ok=True)
    emotion_policy = load_emotion_policy(args.emotion_policy)
    turn_preds = load_turn_preds(args.turn_preds)

    def _chapter_num(path: Path) -> int:
        try:
            return int(path.name.split("_", 1)[1].split(".")[0])
        except Exception:
            return 0

    block_files = sorted(args.blocks_dir.glob("chapter_*.blocks.resolved.json"), key=_chapter_num)
    if not block_files:
        raise SystemExit("No resolved block files found")

    if args.chapter != "all":
        try:
            chapter_num = int(args.chapter)
        except ValueError as exc:
            raise SystemExit(f"Invalid chapter value: {args.chapter}") from exc
        target = args.blocks_dir / f"chapter_{chapter_num}.blocks.resolved.json"
        if not target.exists():
            raise SystemExit(f"Missing resolved block file: {target}")
        block_files = [target]

    total_segments = 0
    for block_path in block_files:
        chapter_num = int(block_path.name.split("_")[1].split(".")[0])
        sentences_path = _resolve_chapter_path(args.sentences_dir, chapter_num, ".json")
        if not sentences_path.exists():
            raise SystemExit(f"Missing sentences file: {sentences_path}")

        chapter_payload = load_json(sentences_path)
        blocks_payload = load_json(block_path)

        result = build_span_segments(
            chapter_payload=chapter_payload,
            blocks_payload=blocks_payload,
            preds=preds,
            labels=labels,
            alias_to_gender=alias_to_gender,
            alias_to_canonical=alias_to_canonical,
            alias_to_speaker=alias_to_speaker,
            include_spans=args.include_spans,
            director=director,
            llm_cache=llm_cache,
            llm_max_calls=args.llm_max_calls,
            llm_min_confidence=args.llm_min_confidence,
            llm_max_quotes=args.llm_max_quotes,
            emotion_mode=args.emotion_mode,
            emotion_scope=args.emotion_scope,
            emotion_director=director,
            emotion_cache=emotion_cache,
            emotion_max_calls=args.emotion_llm_max_calls,
            emotion_min_confidence=args.emotion_llm_min_confidence,
            emotion_max_segments=args.emotion_llm_max_segments,
            emotion_context_chars=args.emotion_context_chars,
            emotion_policy=emotion_policy,
            turn_preds=turn_preds,
            turn_min_confidence=args.turn_min_confidence,
        )

        out_path = args.output_dir / f"chapter_{chapter_num}.segments.json"
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        total_segments += len(result.get("segments", []))

    if args.use_llm and isinstance(llm_cache, dict):
        args.llm_cache.parent.mkdir(parents=True, exist_ok=True)
        args.llm_cache.write_text(json.dumps(llm_cache, indent=2), encoding="utf-8")
    if args.emotion_mode in {"llm", "llm_if_low"} and isinstance(emotion_cache, dict):
        args.emotion_llm_cache.parent.mkdir(parents=True, exist_ok=True)
        args.emotion_llm_cache.write_text(json.dumps(emotion_cache, indent=2), encoding="utf-8")

    print(f"[INFO] Wrote {len(block_files)} chapter span segment files")
    print(f"[INFO] Total segments: {total_segments}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
