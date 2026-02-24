#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
import sys
import wave
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ri_attr.alignment import WhisperAligner  # noqa: E402
from ri_attr.gpu_safety import GPUSafetyController, load_gpu_safety  # noqa: E402
from ri_attr.tts_generate import (  # noqa: E402
    SPEAKER_TO_VOICE,
    VoiceAssigner,
    apply_emotion_effects,
    apply_laughter_rewrites,
    apply_phonetics,
    apply_prosody_rewrites,
    build_alias_phonetic,
    build_lexicon_regex,
    build_prosody_rewrite_rules,
    build_segments,
    crop_wav_start,
    crossfade_segments,
    load_alias_regex,
    load_emotion_map,
    load_json,
    load_prosody_rewrites,
    load_pronunciation_lexicon,
    load_voice_palette,
    merge_pronunciation_lexicons,
    normalize_prosody,
    normalize_text,
    post_process_audio,
    prepend_silence_wav,
    should_skip,
    smooth_edges,
    stitch_segments,
    stitch_segments_variable,
    stitch_wavs,
    trim_silence,
    wav_duration,
)
from ri_attr.preflight import load_thresholds, run_preflight  # noqa: E402


DEFAULT_TRANSITION_PROFILE = {
    "same_voice_crossfade_ms": 40,
    "different_voice_silence_ms": 160,
    "same_voice_base_ms": 60,
    "diff_voice_base_ms": 130,
    "pause_length_scale": 1.0,
    "boundary_fade_ms": 25,
    "min_pause_ms": 60,
    "max_pause_ms": 260,
    "punctuation_pause_ms": {
        "...": 200,
        ".": 140,
        "?": 160,
        "!": 160,
    },
}


def load_transition_profile(path: Path | None) -> dict:
    profile = dict(DEFAULT_TRANSITION_PROFILE)
    if path and path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                profile.update({k: data[k] for k in data.keys()})
        except Exception:
            pass
    return profile


def _pause_scale(text: str, profile: dict) -> float:
    base = float(profile.get("pause_length_scale", 1.0))
    length = len(text or "")
    if length <= 40:
        scale = 0.85
    elif length >= 160:
        scale = 1.10
    else:
        scale = 0.85 + (length - 40) * (1.10 - 0.85) / 120.0
    return base * scale


def _base_pause_ms(text: str, same_voice: bool, profile: dict) -> int:
    if same_voice:
        return int(profile.get("same_voice_base_ms", profile.get("min_pause_ms", 60)))
    fallback = int(profile.get("different_voice_silence_ms", 160))
    base = int(profile.get("diff_voice_base_ms", fallback))
    if not text:
        return base
    punctuation_map = profile.get("punctuation_pause_ms") or {}
    stripped = text.strip()
    if stripped.endswith("...") and "..." in punctuation_map:
        return int(punctuation_map["..."])
    tail = stripped[-1] if stripped else ""
    if tail in punctuation_map:
        return int(punctuation_map[tail])
    return base

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="STEP 11: XTTS batch audio generation")
    parser.add_argument(
        "--segments-dir",
        type=Path,
        default=Path("data/processed/span_segments"),
        help="Directory containing chapter_XXXX.segments.json",
    )
    parser.add_argument(
        "--out-segments",
        type=Path,
        default=Path("data/processed/audio_segments"),
        help="Output directory for per-segment WAVs",
    )
    parser.add_argument(
        "--out-chapters",
        type=Path,
        default=Path("data/processed/audio_chapters"),
        help="Output directory for stitched chapters",
    )
    parser.add_argument(
        "--name-map",
        type=Path,
        default=Path("data/name_map/name_map.json"),
        help="Canonical name map with phonetic spellings",
    )
    parser.add_argument(
        "--voice-palette",
        type=Path,
        default=Path("data/voice_palette.json"),
        help="Optional voice palette JSON",
    )
    parser.add_argument(
        "--emotion-map",
        type=Path,
        default=Path("data/emotion/emotion_map.json"),
        help="Emotion effect map JSON",
    )
    parser.add_argument(
        "--emotion-effects",
        dest="emotion_effects",
        action="store_true",
        help="Enable emotion post-processing",
    )
    parser.add_argument(
        "--no-emotion-effects",
        dest="emotion_effects",
        action="store_false",
        help="Disable emotion post-processing",
    )
    parser.add_argument(
        "--emotion-min-confidence",
        type=float,
        default=0.35,
        help="Minimum confidence to apply emotion effects",
    )
    parser.add_argument(
        "--emotion-strength",
        type=float,
        default=0.85,
        help="Scale emotion effect intensity (0.0-1.0)",
    )
    parser.add_argument(
        "--pronunciation-lexicon",
        type=Path,
        default=Path("data/pronunciation/lexicon.json"),
        help="Pronunciation lexicon JSON",
    )
    parser.add_argument(
        "--pronunciation-overrides",
        type=Path,
        default=Path("data/pronunciation/lexicon_overrides.json"),
        help="Pronunciation lexicon overrides JSON",
    )
    parser.add_argument(
        "--chapter",
        type=str,
        required=True,
        help='Chapter number (e.g. "1") or "all"',
    )
    parser.add_argument(
        "--resume",
        dest="resume",
        action="store_true",
        help="Skip segments that already exist (default)",
    )
    parser.add_argument(
        "--no-resume",
        dest="resume",
        action="store_false",
        help="Regenerate all segments",
    )
    parser.set_defaults(resume=True)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force regeneration of all segments",
    )
    parser.add_argument(
        "--format",
        type=str,
        default="mp3",
        choices=["mp3"],
        help="Output format for stitched chapter audio",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=1,
        help="Max workers (XTTS is GPU-bound; keep at 1 on 8GB)",
    )
    parser.add_argument(
        "--language",
        type=str,
        default="en",
        help="XTTS language code",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process only the first N segments (0 = no limit)",
    )
    parser.add_argument(
        "--target-minutes",
        type=float,
        default=0.0,
        help="Stop after generating roughly this many minutes of audio (0 = no limit)",
    )
    parser.add_argument(
        "--preflight",
        dest="preflight",
        action="store_true",
        help="Run preflight checks before generating audio",
    )
    parser.add_argument(
        "--no-preflight",
        dest="preflight",
        action="store_false",
        help="Disable preflight checks before generation",
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Run preflight checks and exit without generating audio",
    )
    parser.add_argument(
        "--preflight-thresholds",
        type=Path,
        default=Path("data/processed/preflight/thresholds.json"),
        help="JSON thresholds file for preflight gating",
    )
    parser.set_defaults(preflight=True)
    parser.set_defaults(emotion_effects=True)
    parser.add_argument(
        "--no-trim",
        action="store_true",
        help="Disable silence trimming to debug truncation",
    )
    parser.add_argument(
        "--trim-safe",
        dest="trim_safe",
        action="store_true",
        help="Enable safe trimming rules",
    )
    parser.add_argument(
        "--no-trim-safe",
        dest="trim_safe",
        action="store_false",
        help="Disable safe trimming rules",
    )
    parser.add_argument(
        "--trim-min-score",
        type=float,
        default=85.0,
        help="Minimum alignment score required to allow trimming in safe mode",
    )
    parser.add_argument(
        "--trim-threshold-db",
        type=float,
        default=-50.0,
        help="Silence threshold in dB for trim_silence",
    )
    parser.add_argument(
        "--trim-head-pad-ms",
        type=int,
        default=30,
        help="Prepend silence after trimming to avoid clipped onsets (ms)",
    )
    parser.set_defaults(trim_safe=True)
    parser.add_argument(
        "--ghost-context",
        dest="ghost_context",
        action="store_true",
        help="Enable ghost context + alignment cropping (default)",
    )
    parser.add_argument(
        "--no-ghost-context",
        dest="ghost_context",
        action="store_false",
        help="Disable ghost context usage",
    )
    parser.set_defaults(ghost_context=True)
    parser.add_argument(
        "--ghost-min-chars",
        type=int,
        default=260,
        help="Only apply ghost context for target spans shorter than this length",
    )
    parser.add_argument(
        "--ghost-max-chars",
        type=int,
        default=240,
        help="Cap ghost context + target length to avoid XTTS truncation",
    )
    parser.add_argument(
        "--align-model",
        type=str,
        default="base.en",
        help="Faster-Whisper model name for alignment",
    )
    parser.add_argument(
        "--align-device",
        type=str,
        default="cpu",
        help="Alignment device (cpu/cuda)",
    )
    parser.add_argument(
        "--align-compute",
        type=str,
        default="int8",
        help="Alignment compute type (e.g., int8, float16)",
    )
    parser.add_argument(
        "--align-min-score",
        type=float,
        default=70.0,
        help="Minimum alignment score to accept ghost cropping",
    )
    parser.add_argument(
        "--align-tail-pad",
        type=float,
        default=0.3,
        help="Seconds to extend ghost-cropped end to avoid clipping",
    )
    parser.add_argument(
        "--align-head-pad",
        type=float,
        default=0.06,
        help="Seconds to extend ghost-cropped start (avoid leading cut)",
    )
    parser.add_argument(
        "--align-max-head-crop-sec",
        type=float,
        default=0.6,
        help="Max seconds to crop from start when using ghost context",
    )
    parser.add_argument(
        "--validate",
        dest="validate",
        action="store_true",
        help="Enable ASR validation gate (default)",
    )
    parser.add_argument(
        "--no-validate",
        dest="validate",
        action="store_false",
        help="Disable ASR validation gate",
    )
    parser.set_defaults(validate=True)
    parser.add_argument(
        "--validate-min-score",
        type=float,
        default=70.0,
        help="Minimum alignment score to accept synthesized audio",
    )
    parser.add_argument(
        "--validate-min-chars",
        type=int,
        default=25,
        help="Skip ASR validation for very short segments",
    )
    parser.add_argument(
        "--diagnose-truncation",
        dest="diagnose_truncation",
        action="store_true",
        help="Enable truncation diagnostics (default)",
    )
    parser.add_argument(
        "--no-diagnose-truncation",
        dest="diagnose_truncation",
        action="store_false",
        help="Disable truncation diagnostics",
    )
    parser.set_defaults(diagnose_truncation=True)
    parser.add_argument(
        "--retry-on-truncation",
        dest="retry_on_truncation",
        action="store_true",
        help="Retry synthesis with chunked text when truncation is detected (default)",
    )
    parser.add_argument(
        "--no-retry-on-truncation",
        dest="retry_on_truncation",
        action="store_false",
        help="Disable truncation retry",
    )
    parser.set_defaults(retry_on_truncation=True)
    parser.add_argument(
        "--retry-min-coverage",
        type=float,
        default=0.9,
        help="Minimum word coverage before retrying chunked synthesis",
    )
    parser.add_argument(
        "--retry-min-score",
        type=float,
        default=85.0,
        help="Minimum alignment score before retrying chunked synthesis",
    )
    parser.add_argument(
        "--retry-chunk-chars",
        type=int,
        default=110,
        help="Target max characters per chunk when retrying synthesis",
    )
    parser.add_argument(
        "--retry-force-punct-split",
        action="store_true",
        help="Force punctuation-based chunking during retry even for short text",
    )
    parser.add_argument(
        "--retry-silence-ms",
        type=int,
        default=40,
        help="Silence inserted between retry chunks (ms)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=2,
        help="Maximum regeneration attempts per segment",
    )
    parser.add_argument(
        "--crossfade-ms",
        type=int,
        default=0,
        help="Crossfade duration in ms for stitching (0 disables)",
    )
    parser.add_argument(
        "--transition-profile",
        type=Path,
        default=Path("data/tts/transition_profile.json"),
        help="Transition profile JSON for pauses/crossfades",
    )
    parser.add_argument(
        "--transition-same-voice-crossfade-ms",
        type=int,
        default=0,
        help="Crossfade duration (ms) for same voice (0 = use profile)",
    )
    parser.add_argument(
        "--transition-silence-ms",
        type=int,
        default=0,
        help="Silence between different voices (ms) (0 = use profile)",
    )
    parser.add_argument(
        "--transition-boundary-fade-ms",
        type=int,
        default=0,
        help="Fade duration for different-voice boundaries (ms) (0 = use profile)",
    )
    parser.add_argument(
        "--perf-baseline",
        type=Path,
        default=Path("data/benchmarks/perf_baseline.json"),
        help="Perf baseline JSON (segments/min)",
    )
    parser.add_argument(
        "--write-perf-baseline",
        action="store_true",
        help="Write segments/min to perf baseline after generation",
    )
    parser.add_argument(
        "--tail-pad-ms",
        type=int,
        default=220,
        help="Append silence to each segment (ms) to avoid abrupt cutoffs",
    )
    parser.add_argument(
        "--tail-fade-ms",
        type=int,
        default=140,
        help="Fade out each segment tail (ms) to reduce clicks",
    )
    parser.add_argument(
        "--head-fade-ms",
        type=int,
        default=40,
        help="Fade in each segment head (ms) to reduce clicks",
    )
    parser.add_argument(
        "--prosody-normalize",
        dest="prosody_normalize",
        action="store_true",
        help="Normalize punctuation spacing and repeated emphasis (default)",
    )
    parser.add_argument(
        "--no-prosody-normalize",
        dest="prosody_normalize",
        action="store_false",
        help="Disable prosody normalization",
    )
    parser.add_argument(
        "--denoise",
        dest="denoise",
        action="store_true",
        help="Enable light denoise/EQ post-processing",
    )
    parser.add_argument(
        "--no-denoise",
        dest="denoise",
        action="store_false",
        help="Disable denoise/EQ post-processing",
    )
    parser.add_argument(
        "--denoise-floor-db",
        type=float,
        default=-45.0,
        help="Noise floor (dB) for afftdn when denoise is enabled",
    )
    parser.add_argument(
        "--denoise-highpass-hz",
        type=int,
        default=80,
        help="Highpass cutoff (Hz) for denoise EQ",
    )
    parser.add_argument(
        "--denoise-lowpass-hz",
        type=int,
        default=14000,
        help="Lowpass cutoff (Hz) for denoise EQ",
    )
    parser.set_defaults(denoise=True)
    parser.set_defaults(prosody_normalize=True)
    parser.add_argument(
        "--debug-synth",
        action="store_true",
        help="Log Synthesizer.tts inputs (split_sentences + text length)",
    )
    parser.add_argument(
        "--debug-infer",
        action="store_true",
        help="Log XTTS inference text + tokenizer output sizes",
    )
    parser.add_argument(
        "--debug-in-memory",
        action="store_true",
        help="Call tts.tts() and log wav length before saving",
    )
    parser.add_argument(
        "--direct-synth",
        action="store_true",
        help="Bypass TTS.api.TTS and call Synthesizer.tts directly",
    )
    parser.add_argument(
        "--sample-text",
        type=str,
        default="",
        help="Run a single sample synthesis and exit",
    )
    parser.add_argument(
        "--gpu-config",
        type=Path,
        default=Path("data/system/gpu_safety.json"),
        help="GPU safety config JSON",
    )
    parser.add_argument(
        "--gpu-safety",
        dest="gpu_safety",
        action="store_true",
        help="Enable GPU safety controls (default)",
    )
    parser.add_argument(
        "--no-gpu-safety",
        dest="gpu_safety",
        action="store_false",
        help="Disable GPU safety controls",
    )
    parser.set_defaults(gpu_safety=True)
    parser.add_argument(
        "--gpu-power-limit-percent",
        type=float,
        default=0.0,
        help="Override GPU power limit percent (0 = use config)",
    )
    parser.add_argument(
        "--gpu-max-temp",
        type=float,
        default=0.0,
        help="Override GPU max temp in C (0 = use config)",
    )
    parser.add_argument(
        "--gpu-util-target-min",
        type=float,
        default=0.0,
        help="Override GPU util target min (0 = use config)",
    )
    parser.add_argument(
        "--gpu-util-target-max",
        type=float,
        default=0.0,
        help="Override GPU util target max (0 = use config)",
    )
    parser.add_argument(
        "--gpu-max-slowdown",
        type=float,
        default=0.0,
        help="Override max slowdown ratio (0 = use config)",
    )
    parser.add_argument(
        "--gpu-autotune",
        dest="gpu_autotune",
        action="store_true",
        help="Enable GPU autotune (default)",
    )
    parser.add_argument(
        "--no-gpu-autotune",
        dest="gpu_autotune",
        action="store_false",
        help="Disable GPU autotune",
    )
    parser.set_defaults(gpu_autotune=True)
    return parser.parse_args()


def load_chapter_files(segments_dir: Path, chapter_arg: str) -> list[Path]:
    if chapter_arg == "all":
        def _chapter_num(path: Path) -> int:
            try:
                return int(path.name.split("_", 1)[1].split(".")[0])
            except Exception:
                return 0

        return sorted(segments_dir.glob("chapter_*.segments.json"), key=_chapter_num)
    chapter_num = int(chapter_arg)
    candidates = [
        segments_dir / f"chapter_{chapter_num}.segments.json",
        segments_dir / f"chapter_{chapter_num:04d}.segments.json",
    ]
    for path in candidates:
        if path.exists():
            return [path]
    return [candidates[0]]


def _normalize_word(word: str) -> str:
    return re.sub(r"[^a-z0-9']+", "", word.lower())


def _tokenize_tail(text: str) -> list[str]:
    return [_normalize_word(w) for w in text.split() if _normalize_word(w)]


def tail_guard_failed(
    target_text: str,
    transcript_tokens: list[str],
    tail_words: int = 3,
    window: int = 12,
) -> bool:
    target_tokens = _tokenize_tail(target_text)
    if not target_tokens:
        return False
    if not transcript_tokens:
        return True
    tail_len = min(tail_words, len(target_tokens))
    tail = target_tokens[-tail_len:]
    window_tokens = transcript_tokens[-window:] if len(transcript_tokens) > window else transcript_tokens
    idx = 0
    for token in window_tokens:
        if token == tail[idx]:
            idx += 1
            if idx == len(tail):
                return False
    return True


def main() -> int:
    args = parse_args()

    if args.max_workers != 1:
        print("[WARN] max-workers > 1 is not recommended for XTTS; running single-threaded")

    if not args.segments_dir.exists():
        raise SystemExit(f"Missing segments dir: {args.segments_dir}")
    if not args.name_map.exists():
        raise SystemExit(f"Missing name map: {args.name_map}")

    name_map = load_json(args.name_map)
    alias_to_phonetic = build_alias_phonetic(name_map)
    derived_dir = args.name_map.parent / "derived"
    alias_regex = load_alias_regex(derived_dir, name_map)
    lexicon_base = load_pronunciation_lexicon(args.pronunciation_lexicon)
    lexicon_overrides = load_pronunciation_lexicon(args.pronunciation_overrides)
    lexicon = merge_pronunciation_lexicons(lexicon_base, lexicon_overrides)
    lexicon_regex = build_lexicon_regex(lexicon)
    prosody_rewrites = load_prosody_rewrites(
        Path("data/pronunciation/prosody_rewrites.json")
    )
    prosody_rules = build_prosody_rewrite_rules(prosody_rewrites)

    palette = load_voice_palette(args.voice_palette)
    voice_assigner = VoiceAssigner(palette)
    emotion_map = load_emotion_map(args.emotion_map)
    transition_profile = load_transition_profile(args.transition_profile)
    transition_same_voice_ms = (
        args.transition_same_voice_crossfade_ms
        if args.transition_same_voice_crossfade_ms > 0
        else int(transition_profile.get("same_voice_crossfade_ms", 40))
    )
    transition_diff_voice_ms = (
        args.transition_silence_ms
        if args.transition_silence_ms > 0
        else int(transition_profile.get("different_voice_silence_ms", 160))
    )
    if "diff_voice_base_ms" not in transition_profile or args.transition_silence_ms > 0:
        transition_profile["diff_voice_base_ms"] = transition_diff_voice_ms
    boundary_fade_ms = (
        args.transition_boundary_fade_ms
        if args.transition_boundary_fade_ms > 0
        else int(transition_profile.get("boundary_fade_ms", 0))
    )
    transition_profile["same_voice_crossfade_ms"] = transition_same_voice_ms
    transition_profile["different_voice_silence_ms"] = transition_diff_voice_ms
    transition_profile["boundary_fade_ms"] = boundary_fade_ms

    gpu_config_path = args.gpu_config if args.gpu_config.is_absolute() else REPO_ROOT / args.gpu_config
    gpu_config = load_gpu_safety(gpu_config_path)
    if args.gpu_power_limit_percent > 0:
        gpu_config["power_limit_mode"] = "percent"
        gpu_config["power_limit_percent"] = float(args.gpu_power_limit_percent)
    if args.gpu_max_temp > 0:
        gpu_config["max_temp_c"] = float(args.gpu_max_temp)
    if args.gpu_util_target_min > 0:
        gpu_config["util_target_min"] = float(args.gpu_util_target_min)
    if args.gpu_util_target_max > 0:
        gpu_config["util_target_max"] = float(args.gpu_util_target_max)
    if args.gpu_max_slowdown > 0:
        gpu_config["max_slowdown_ratio"] = float(args.gpu_max_slowdown)
    gpu_config["autotune"] = bool(args.gpu_autotune)
    gpu_config["enabled"] = bool(args.gpu_safety)

    baseline_segments_per_min = None
    perf_baseline_path = args.perf_baseline if args.perf_baseline.is_absolute() else REPO_ROOT / args.perf_baseline
    if perf_baseline_path.exists():
        try:
            data = json.loads(perf_baseline_path.read_text(encoding="utf-8"))
            baseline_segments_per_min = data.get("generation_segments_per_min")
        except Exception:
            baseline_segments_per_min = None

    gpu_controller = GPUSafetyController(
        gpu_config,
        baseline_throughput=baseline_segments_per_min,
        mode="generation",
    )
    gpu_controller.apply_initial_limit()

    aligner = None
    if args.ghost_context or args.validate:
        try:
            aligner = WhisperAligner(
                model_name=args.align_model,
                device=args.align_device,
                compute_type=args.align_compute,
            )
        except RuntimeError as exc:
            if args.ghost_context:
                raise SystemExit(str(exc)) from exc
            print(f"[WARN] Alignment disabled: {exc}")
            aligner = None

    args.out_segments.mkdir(parents=True, exist_ok=True)
    args.out_chapters.mkdir(parents=True, exist_ok=True)
    logs_dir = Path("data/processed/audio_logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    failed_log_path = logs_dir / "failed_segments.jsonl"
    generation_log_path = logs_dir / "generation_log.jsonl"
    truncation_log_path = logs_dir / "truncation_report.jsonl"

    try:
        from TTS.api import TTS  # type: ignore
    except ImportError as exc:
        raise SystemExit(f"Missing TTS.api.TTS dependency: {exc}") from exc
    try:
        import torch
        from TTS.config.shared_configs import BaseDatasetConfig
        from TTS.tts.configs.xtts_config import XttsConfig
        from TTS.tts.models.xtts import XttsArgs, XttsAudioConfig

        torch.serialization.add_safe_globals(
            [BaseDatasetConfig, XttsConfig, XttsAudioConfig, XttsArgs]
        )
    except Exception:
        pass

    tts = TTS(
        model_name="tts_models/multilingual/multi-dataset/xtts_v2",
        gpu=True,
    )
    if args.debug_synth or args.debug_infer:
        try:
            import inspect
            import TTS as tts_pkg  # type: ignore

            print(f"[DEBUG] Python: {sys.executable}")
            print(f"[DEBUG] TTS version: {getattr(tts_pkg, '__version__', 'unknown')}")
            print(f"[DEBUG] TTS api path: {inspect.getfile(TTS)}")
            print(f"[DEBUG] XTTS model: {tts.synthesizer.tts_config.model}")
            print(f"[DEBUG] XTTS speakers: {tts.speakers}")
            print(f"[DEBUG] XTTS languages: {tts.languages}")
        except Exception as exc:
            print(f"[WARN] Could not log TTS environment details: {exc}")

    if args.debug_synth:
        try:
            orig_synth_tts = tts.synthesizer.tts

            def synth_debug(*dbg_args, **dbg_kwargs):
                text = dbg_kwargs.get("text", dbg_args[0] if dbg_args else "")
                print(f"[DEBUG] Synth split_sentences: {dbg_kwargs.get('split_sentences')}")
                print(f"[DEBUG] Synth text len: {len(text)}")
                return orig_synth_tts(*dbg_args, **dbg_kwargs)

            tts.synthesizer.tts = synth_debug  # type: ignore[assignment]
        except Exception as exc:
            print(f"[WARN] Could not attach Synthesizer.tts debug hook: {exc}")

    if args.debug_infer:
        try:
            xtts_model = tts.synthesizer.tts_model
            orig_infer = xtts_model.inference

            def infer_debug(text, language, *dbg_args, **dbg_kwargs):
                lang = language.split("-")[0]
                sent = text.strip().lower()
                tok = xtts_model.tokenizer
                pre = tok.preprocess_text(sent, lang)
                ids = tok.encode(sent, lang=language)
                print(f"[DEBUG] Infer raw len: {len(text)} repr: {text[:80]!r}")
                print(f"[DEBUG] Infer pre len: {len(pre)} repr: {pre[:80]!r}")
                print(f"[DEBUG] Infer ids len: {len(ids)} head: {ids[:10]}")
                return orig_infer(text, language, *dbg_args, **dbg_kwargs)

            xtts_model.inference = infer_debug  # type: ignore[assignment]
        except Exception as exc:
            print(f"[WARN] Could not attach XTTS inference debug hook: {exc}")

    try:
        synth = tts.synthesizer
        if hasattr(synth, "tts_config"):
            if hasattr(synth.tts_config, "split_sentences"):
                synth.tts_config.split_sentences = False
            if hasattr(synth.tts_config, "max_text_len"):
                synth.tts_config.max_text_len = 2000
            if hasattr(synth.tts_config, "use_vad"):
                synth.tts_config.use_vad = False
    except Exception as exc:
        print(f"[WARN] Could not fully disable XTTS internal splitting: {exc}")

    if args.sample_text:
        sample_voice = voice_assigner.resolve("narrator", "unknown", None)
        sample_out = Path("data/processed/audio_logs") / "sample_test.wav"
        sample_out.parent.mkdir(parents=True, exist_ok=True)
        print(f"[INFO] Sample text len={len(args.sample_text)} voice={sample_voice}")
        if args.debug_in_memory or args.direct_synth:
            if args.direct_synth:
                sample_wav = tts.synthesizer.tts(
                    text=args.sample_text,
                    speaker_name=sample_voice,
                    language_name=args.language,
                    split_sentences=False,
                )
            else:
                sample_wav = tts.tts(
                    text=args.sample_text,
                    speaker=sample_voice,
                    language=args.language,
                    split_sentences=False,
                )
            sample_rate = getattr(tts.synthesizer, "output_sample_rate", 24000)
            print(f"[INFO] Sample wav samples={len(sample_wav)} sr={sample_rate}")
            tts.synthesizer.save_wav(sample_wav, str(sample_out))
        else:
            tts.tts_to_file(
                text=args.sample_text,
                speaker=sample_voice,
                language=args.language,
                file_path=str(sample_out),
                split_sentences=False,
            )
        if not args.no_trim:
            trim_silence(sample_out)
        try:
            duration = wav_duration(sample_out)
            print(f"[INFO] Sample audio duration={duration:.3f}s")
        except Exception as exc:
            print(f"[WARN] Could not read sample duration: {exc}")
        print(f"[INFO] Sample audio saved: {sample_out}")
        return 0

    chapter_files = load_chapter_files(args.segments_dir, args.chapter)
    if not chapter_files:
        raise SystemExit("No chapter segment files found")

    if args.preflight or args.preflight_only:
        preflight_dir = Path("data/processed/preflight")
        preflight_dir.mkdir(parents=True, exist_ok=True)
        thresholds = load_thresholds(args.preflight_thresholds)
        any_violations = False
        for chapter_path in chapter_files:
            result = run_preflight(chapter_path, thresholds)
            report = result.report
            chapter = report.get("chapter")
            out_path = preflight_dir / f"chapter_{chapter}.report.json"
            out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            if result.violations:
                any_violations = True
        if args.preflight_only:
            if any_violations:
                raise SystemExit("Preflight violations detected")
            return 0
        if any_violations:
            raise SystemExit("Preflight violations detected; aborting generation")

    for chapter_path in chapter_files:
        segments_payload = load_json(chapter_path)
        chapter_num = int(segments_payload.get("chapter", 0))
        source_file = segments_payload.get("source_file")
        segments = build_segments(segments_payload)
        segments_to_process = segments if args.limit <= 0 else segments[: args.limit]
        target_seconds = args.target_minutes * 60.0 if args.target_minutes > 0 else 0.0

        chapter_out_dir = args.out_segments / f"chapter_{chapter_num}"
        chapter_out_dir.mkdir(parents=True, exist_ok=True)
        chapter_failed: set[str] = set()
        chapter_segment_paths = []
        chapter_metadata_segments = []
        current_start = 0.0
        processed_segments: list = []
        accumulated_duration = 0.0
        perf_start = time.time()
        perf_segments_done = 0

        def synthesize_to_file(text: str, out_path: Path, voice_name: str) -> None:
            if args.debug_in_memory or args.direct_synth:
                if args.direct_synth:
                    wav = tts.synthesizer.tts(
                        text=text,
                        speaker_name=voice_name,
                        language_name=args.language,
                        split_sentences=False,
                    )
                else:
                    wav = tts.tts(
                        text=text,
                        speaker=voice_name,
                        language=args.language,
                        split_sentences=False,
                    )
                sample_rate = getattr(tts.synthesizer, "output_sample_rate", 24000)
                print(
                    f"[DEBUG] In-memory wav samples={len(wav)} sr={sample_rate} "
                    f"text_len={len(text)}"
                )
                tts.synthesizer.save_wav(wav, str(out_path))
            else:
                tts.tts_to_file(
                    text=text,
                    speaker=voice_name,
                    language=args.language,
                    file_path=str(out_path),
                    split_sentences=False,
                )

        def split_text_for_tts(
            text: str,
            max_chars: int,
            force_punct_split: bool = False,
        ) -> list[str]:
            cleaned = text.strip()
            if not cleaned:
                return []
            if len(cleaned) <= max_chars and not force_punct_split:
                return [cleaned]
            sentences = re.split(r"(?<=[.!?])\\s+", cleaned)
            chunks: list[str] = []
            for sent in sentences:
                if not sent:
                    continue
                if len(sent) <= max_chars:
                    chunks.append(sent)
                    continue
                clauses = re.split(r"(?<=[,;:])\\s+", sent)
                buf = ""
                for clause in clauses:
                    if not buf:
                        buf = clause
                        continue
                    if len(buf) + 1 + len(clause) <= max_chars:
                        buf = f"{buf} {clause}"
                    else:
                        chunks.append(buf)
                        buf = clause
                if buf:
                    chunks.append(buf)
            return [c for c in chunks if c]

        def synthesize_chunked(text: str, out_path: Path, voice_name: str) -> bool:
            parts = split_text_for_tts(
                text,
                args.retry_chunk_chars,
                force_punct_split=args.retry_force_punct_split,
            )
            if len(parts) <= 1:
                return False
            part_paths: list[Path] = []
            for idx_part, part in enumerate(parts, start=1):
                part_path = out_path.with_suffix(f".part{idx_part:02d}.wav")
                synthesize_to_file(part, part_path, voice_name)
                if not args.no_trim:
                    trim_silence(
                        part_path,
                        min_ratio=0.2,
                        min_duration_sec=0.5,
                        threshold_db=args.trim_threshold_db,
                    )
                if args.tail_pad_ms or args.tail_fade_ms or args.head_fade_ms:
                    smooth_edges(
                        part_path,
                        pad_ms=args.tail_pad_ms,
                        fade_out_ms=args.tail_fade_ms,
                        fade_in_ms=args.head_fade_ms,
                    )
                part_paths.append(part_path)
            stitched = stitch_wavs(part_paths, out_path, silence_ms=args.retry_silence_ms)
            for part_path in part_paths:
                part_path.unlink(missing_ok=True)
            if stitched and args.denoise:
                post_process_audio(
                    out_path,
                    denoise=True,
                    highpass_hz=args.denoise_highpass_hz,
                    lowpass_hz=args.denoise_lowpass_hz,
                    denoise_floor_db=args.denoise_floor_db,
                )
            return stitched

        for idx, segment in enumerate(segments_to_process, start=1):
            voice = voice_assigner.resolve(
                segment.speaker_role,
                segment.speaker_gender,
                segment.scene_id,
            )
            wav_name = f"{segment.segment_id}.{segment.speaker_role}.wav"
            wav_path = chapter_out_dir / wav_name

            if should_skip(wav_path, args.resume, args.force):
                if wav_path.exists():
                    chapter_segment_paths.append(wav_path)
                    processed_segments.append(segment)
                continue

            try:
                rewritten = apply_laughter_rewrites(segment.text)
                rewritten = apply_prosody_rewrites(rewritten, prosody_rules)
                rewritten = apply_phonetics(
                    rewritten,
                    alias_regex,
                    alias_to_phonetic,
                    lexicon_regex=lexicon_regex,
                    lexicon=lexicon,
                )
                cleaned = normalize_text(rewritten)
                if args.prosody_normalize:
                    cleaned = normalize_prosody(cleaned)
                if not cleaned:
                    with generation_log_path.open("a", encoding="utf-8") as handle:
                        handle.write(
                            json.dumps(
                                {
                                    "chapter": chapter_num,
                                    "segment_id": segment.segment_id,
                                    "speaker_role": segment.speaker_role,
                                    "speaker_gender": segment.speaker_gender,
                                    "status": "skipped_empty",
                                }
                            )
                            + "\n"
                        )
                    continue

                start_t = time.time()
                success = False
                attempts = 0
                final_score = None
                while not success and attempts <= args.max_retries:
                    attempts += 1
                    temp_path = wav_path
                    used_ghost = False
                    alignment_score = None

                    if (
                        args.ghost_context
                        and aligner is not None
                        and segment.context_prefix
                        and segment.speaker_role != "narrator"
                        and len(cleaned) < args.ghost_min_chars
                    ):
                        context_rewritten = apply_laughter_rewrites(segment.context_prefix)
                        context_rewritten = apply_prosody_rewrites(
                            context_rewritten, prosody_rules
                        )
                        context_rewritten = apply_phonetics(
                            context_rewritten,
                            alias_regex,
                            alias_to_phonetic,
                            lexicon_regex=lexicon_regex,
                            lexicon=lexicon,
                        )
                        context_clean = normalize_text(context_rewritten)
                        if args.prosody_normalize:
                            context_clean = normalize_prosody(context_clean)
                        if args.ghost_max_chars > 0:
                            available = args.ghost_max_chars - len(cleaned) - 1
                            if available < 0:
                                available = 0
                            if len(context_clean) > available:
                                words = context_clean.split()
                                while words and len(" ".join(words)) > available:
                                    words.pop(0)
                                context_clean = " ".join(words)
                        ghost_text = f"{context_clean} {cleaned}".strip()
                        ghost_path = wav_path.with_suffix(".ghost.wav")
                        synthesize_to_file(ghost_text, ghost_path, voice)
                        result = aligner.align(
                            str(ghost_path), cleaned, min_score=0.0
                        )
                        if result:
                            start_sec = max(0.0, result.start_sec - args.align_head_pad)
                        else:
                            start_sec = 0.0
                        if (
                            result
                            and result.score >= args.align_min_score
                            and start_sec <= args.align_max_head_crop_sec
                            and crop_wav_start(ghost_path, start_sec)
                        ):
                            ghost_path.replace(wav_path)
                            used_ghost = True
                            alignment_score = result.score
                        else:
                            ghost_path.unlink(missing_ok=True)

                    if not used_ghost:
                        synthesize_to_file(cleaned, wav_path, voice)

                    final_score = alignment_score
                    if (
                        args.validate
                        and aligner is not None
                        and len(cleaned) >= args.validate_min_chars
                    ):
                        score = alignment_score
                        if score is None:
                            score = aligner.score(str(wav_path), cleaned)
                        final_score = score
                        if score < args.validate_min_score:
                            wav_path.unlink(missing_ok=True)
                            continue

                    success = True

                elapsed = round(time.time() - start_t, 3)
                if not success:
                    raise RuntimeError("Validation failed after retries")
                retry_used = False
                diag_result = None
                tail_missing = False
                if aligner is not None and (args.retry_on_truncation or args.diagnose_truncation):
                    try:
                        diag_result, transcript_tokens = aligner.align_with_words(
                            str(wav_path), cleaned, min_score=0.0
                        )
                        if diag_result:
                            coverage = diag_result.matched_words / max(1, diag_result.total_words)
                            tail_missing = tail_guard_failed(cleaned, transcript_tokens)
                            if (
                                args.retry_on_truncation
                                and (
                                    coverage < args.retry_min_coverage
                                    or diag_result.score < args.retry_min_score
                                    or tail_missing
                                )
                            ):
                                if synthesize_chunked(cleaned, wav_path, voice):
                                    retry_used = True
                                    diag_result, transcript_tokens = aligner.align_with_words(
                                        str(wav_path), cleaned, min_score=0.0
                                    )
                                    tail_missing = tail_guard_failed(cleaned, transcript_tokens)
                    except Exception:
                        diag_result = None
                        tail_missing = False
                if not args.no_trim:
                    prev_seg = segments_to_process[idx - 2] if idx > 1 else None
                    next_seg = segments_to_process[idx] if idx < len(segments_to_process) else None
                    boundary_change = False
                    if prev_seg:
                        boundary_change |= (
                            prev_seg.speaker_role != segment.speaker_role
                            or prev_seg.speaker_gender != segment.speaker_gender
                        )
                    if next_seg:
                        boundary_change |= (
                            next_seg.speaker_role != segment.speaker_role
                            or next_seg.speaker_gender != segment.speaker_gender
                        )
                    if not args.trim_safe or (
                        final_score is not None
                        and final_score >= args.trim_min_score
                        and not boundary_change
                        and not tail_missing
                    ):
                        trim_silence(
                            wav_path,
                            min_ratio=0.2,
                            min_duration_sec=0.5,
                            threshold_db=args.trim_threshold_db,
                        )
                        if args.trim_head_pad_ms > 0:
                            prepend_silence_wav(wav_path, args.trim_head_pad_ms / 1000.0)
                if args.tail_pad_ms or args.tail_fade_ms or args.head_fade_ms:
                    smooth_edges(
                        wav_path,
                        pad_ms=args.tail_pad_ms,
                        fade_out_ms=args.tail_fade_ms,
                        fade_in_ms=args.head_fade_ms,
                    )
                if (
                    args.emotion_effects
                    and segment.emotion
                    and segment.emotion_confidence >= args.emotion_min_confidence
                ):
                    emotion_applied = True
                    apply_emotion_effects(
                        wav_path,
                        segment.emotion,
                        emotion_map,
                        strength=args.emotion_strength,
                    )
                else:
                    emotion_applied = False
                emotion_log_path = logs_dir / "emotion_report.jsonl"
                with emotion_log_path.open("a", encoding="utf-8") as handle:
                    handle.write(
                        json.dumps(
                            {
                                "chapter": chapter_num,
                                "segment_id": segment.segment_id,
                                "speaker_role": segment.speaker_role,
                                "emotion": segment.emotion,
                                "emotion_confidence": segment.emotion_confidence,
                                "applied": emotion_applied,
                                "min_confidence": args.emotion_min_confidence,
                                "strength": args.emotion_strength,
                            }
                        )
                        + "\n"
                    )
                if args.denoise:
                    post_process_audio(
                        wav_path,
                        denoise=True,
                        highpass_hz=args.denoise_highpass_hz,
                        lowpass_hz=args.denoise_lowpass_hz,
                        denoise_floor_db=args.denoise_floor_db,
                    )
                if args.diagnose_truncation and aligner is not None:
                    try:
                        duration = wav_duration(wav_path)
                        if duration > 0 and diag_result:
                            ratio = diag_result.end_sec / duration
                            coverage = diag_result.matched_words / max(1, diag_result.total_words)
                            if ratio < 0.85 or coverage < 0.9 or tail_missing:
                                with truncation_log_path.open("a", encoding="utf-8") as handle:
                                    handle.write(
                                        json.dumps(
                                            {
                                                "chapter": chapter_num,
                                                "segment_id": segment.segment_id,
                                                "duration_sec": round(duration, 3),
                                                "align_end_sec": round(diag_result.end_sec, 3),
                                                "ratio": round(ratio, 3),
                                                "coverage": round(coverage, 3),
                                                "score": round(diag_result.score, 2),
                                                "tail_missing": tail_missing,
                                                "retry_used": retry_used,
                                                "text_preview": cleaned[:120],
                                            }
                                        )
                                        + "\n"
                                    )
                    except Exception:
                        pass
                chapter_segment_paths.append(wav_path)
                processed_segments.append(segment)
                perf_segments_done += 1
                elapsed_min = max((time.time() - perf_start) / 60.0, 1e-6)
                segments_per_min = perf_segments_done / elapsed_min
                gpu_controller.update(segments_per_min)

                with generation_log_path.open("a", encoding="utf-8") as handle:
                    handle.write(
                        json.dumps(
                            {
                                "chapter": chapter_num,
                                "segment_id": segment.segment_id,
                                    "speaker_role": segment.speaker_role,
                                    "speaker_gender": segment.speaker_gender,
                                    "scene_id": segment.scene_id,
                                    "emotion": segment.emotion,
                                    "emotion_confidence": segment.emotion_confidence,
                                    "voice": voice,
                                    "retry_chunked": retry_used,
                                    "path": str(wav_path),
                                    "text_preview": cleaned[:120],
                                    "elapsed_sec": elapsed,
                                    "status": "ok",
                            }
                        )
                        + "\n"
                    )
            except Exception as exc:  # noqa: BLE001
                chapter_failed.add(segment.segment_id)
                with failed_log_path.open("a", encoding="utf-8") as handle:
                    handle.write(
                        json.dumps(
                            {
                                "chapter": chapter_num,
                                "segment_id": segment.segment_id,
                                "speaker_role": segment.speaker_role,
                                "speaker_gender": segment.speaker_gender,
                                "error": str(exc),
                                "text_preview": segment.text[:120],
                            }
                        )
                        + "\n"
                    )
                with generation_log_path.open("a", encoding="utf-8") as handle:
                    handle.write(
                        json.dumps(
                            {
                                "chapter": chapter_num,
                                "segment_id": segment.segment_id,
                                "speaker_role": segment.speaker_role,
                                "speaker_gender": segment.speaker_gender,
                                "voice": voice,
                                "path": str(wav_path),
                                "status": "failed",
                            }
                        )
                        + "\n"
                    )

            if idx % 75 == 0:
                try:
                    import torch

                    torch.cuda.empty_cache()
                except Exception:
                    pass

            if target_seconds > 0 and wav_path.exists():
                try:
                    seg_duration = wav_duration(wav_path)
                    accumulated_duration += seg_duration
                except Exception:
                    pass
                if accumulated_duration >= target_seconds:
                    break

        for segment in processed_segments:
            wav_name = f"{segment.segment_id}.{segment.speaker_role}.wav"
            wav_path = chapter_out_dir / wav_name
            if not wav_path.exists() or wav_path.stat().st_size == 0:
                chapter_failed.add(segment.segment_id)
                continue
            try:
                duration = wav_duration(wav_path)
            except Exception:
                chapter_failed.add(segment.segment_id)
                continue
            chapter_metadata_segments.append(
                {
                    "segment_id": segment.segment_id,
                    "speaker_role": segment.speaker_role,
                    "speaker_gender": segment.speaker_gender,
                    "scene_id": segment.scene_id,
                    "emotion": segment.emotion,
                    "emotion_confidence": segment.emotion_confidence,
                    "sids": segment.sids,
                    "start_sec": round(current_start, 3),
                    "duration_sec": round(duration, 3),
                    "path": str(wav_path),
                }
            )
            current_start += duration

        mp3_path = args.out_chapters / f"chapter_{chapter_num}.mp3"

        stitch_entries = []
        if transition_same_voice_ms > 0 and len(processed_segments) > 1:
            groups = []
            current_paths = []
            current_segs = []
            current_meta = None
            for seg, path in zip(processed_segments, chapter_segment_paths):
                meta = (seg.speaker_role, seg.speaker_gender)
                if current_meta is None or meta == current_meta:
                    current_paths.append(path)
                    current_segs.append(seg)
                    current_meta = meta
                else:
                    groups.append((current_meta, list(current_paths), list(current_segs)))
                    current_paths = [path]
                    current_segs = [seg]
                    current_meta = meta
            if current_paths:
                groups.append((current_meta, list(current_paths), list(current_segs)))

            for idx, (meta, paths, segs) in enumerate(groups, start=1):
                if len(paths) > 1:
                    out_path = chapter_out_dir / f"group_{idx:04d}.xfade.wav"
                    try:
                        with wave.open(str(paths[0]), "rb") as handle:
                            sample_rate = handle.getframerate()
                    except Exception:
                        sample_rate = 24000
                    if crossfade_segments(
                        paths,
                        out_path,
                        crossfade_ms=max(transition_same_voice_ms, args.crossfade_ms),
                        sample_rate=sample_rate,
                    ):
                        stitch_entries.append(
                            {
                                "path": out_path,
                                "meta": meta,
                                "first_segment_id": segs[0].segment_id,
                                "last_segment_id": segs[-1].segment_id,
                                "last_text": segs[-1].text,
                            }
                        )
                        continue
                for seg, path in zip(segs, paths):
                    stitch_entries.append(
                        {
                            "path": path,
                            "meta": meta,
                            "first_segment_id": seg.segment_id,
                            "last_segment_id": seg.segment_id,
                            "last_text": seg.text,
                        }
                    )
        else:
            for seg, path in zip(processed_segments, chapter_segment_paths):
                stitch_entries.append(
                    {
                        "path": path,
                        "meta": (seg.speaker_role, seg.speaker_gender),
                        "first_segment_id": seg.segment_id,
                        "last_segment_id": seg.segment_id,
                        "last_text": seg.text,
                    }
                )

        if boundary_fade_ms > 0 and stitch_entries:
            needs_head: set[Path] = set()
            needs_tail: set[Path] = set()
            for idx in range(len(stitch_entries) - 1):
                left = stitch_entries[idx]
                right = stitch_entries[idx + 1]
                if left["meta"] != right["meta"]:
                    needs_tail.add(left["path"])
                    needs_head.add(right["path"])
            for entry in stitch_entries:
                path = entry["path"]
                fade_in = boundary_fade_ms if path in needs_head else 0
                fade_out = boundary_fade_ms if path in needs_tail else 0
                if fade_in or fade_out:
                    smooth_edges(path, pad_ms=0, fade_out_ms=fade_out, fade_in_ms=fade_in)

        stitch_paths = [entry["path"] for entry in stitch_entries]
        silence_ms_list = []
        transition_log_path = logs_dir / "transition_report.jsonl"
        min_pause = int(transition_profile.get("min_pause_ms", 60))
        max_pause = int(transition_profile.get("max_pause_ms", 260))
        for idx in range(len(stitch_entries) - 1):
            left = stitch_entries[idx]
            right = stitch_entries[idx + 1]
            same_voice = left["meta"] == right["meta"]
            base_ms = _base_pause_ms(left["last_text"], same_voice, transition_profile)
            scale = _pause_scale(left["last_text"], transition_profile)
            pause_ms = int(round(base_ms * scale))
            pause_ms = max(min_pause, min(pause_ms, max_pause))
            silence_ms_list.append(int(pause_ms))
            with transition_log_path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        {
                            "chapter": chapter_num,
                            "from_segment_id": left["last_segment_id"],
                            "to_segment_id": right["first_segment_id"],
                            "same_voice": same_voice,
                            "pause_ms": int(pause_ms),
                        }
                    )
                    + "\n"
                )

        stitched_ok = stitch_segments_variable(
            stitch_paths,
            mp3_path,
            silence_ms_list=silence_ms_list,
            bitrate="192k",
        )

        metadata_path = args.out_chapters / f"chapter_{chapter_num}.metadata.json"
        metadata_path.write_text(
            json.dumps(
                {
                    "chapter": chapter_num,
                    "source_file": source_file,
                    "output_mp3": mp3_path.name if stitched_ok else None,
                    "segments": chapter_metadata_segments,
                    "failed_segments": sorted(chapter_failed),
                    "voices": SPEAKER_TO_VOICE,
                    "voice_palette": palette,
                    "emotion_map": emotion_map,
                    "emotion_effects": args.emotion_effects,
                    "emotion_strength": args.emotion_strength,
                    "generated_seconds": round(current_start, 3),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        print(
            f"[INFO] Chapter {chapter_num}: segments={len(processed_segments)} "
            f"failed={len(set(chapter_failed))} "
            f"stitched={'yes' if stitched_ok else 'no'}"
        )

        if args.write_perf_baseline and perf_segments_done > 0:
            elapsed_min = max((time.time() - perf_start) / 60.0, 1e-6)
            segments_per_min = perf_segments_done / elapsed_min
            perf_baseline_path.parent.mkdir(parents=True, exist_ok=True)
            baseline = {}
            if perf_baseline_path.exists():
                try:
                    baseline = json.loads(perf_baseline_path.read_text(encoding="utf-8"))
                except Exception:
                    baseline = {}
            baseline["generation_segments_per_min"] = round(segments_per_min, 4)
            perf_baseline_path.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
