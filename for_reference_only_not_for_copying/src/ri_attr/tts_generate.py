#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
import wave
from dataclasses import dataclass
from pathlib import Path


SPEAKER_TO_VOICE = {
    "narrator": "Damien Black",
    "male": "Damien Black",
    "female": "Ana Florence",
    "internal_thought": "Damien Black",
}

DEFAULT_VOICE_PALETTE = {
    "narrator": ["Damien Black"],
    "male": ["Damien Black"],
    "female": ["Ana Florence"],
    "internal_thought": ["Damien Black"],
    "dialogue_default": ["Damien Black"],
}

DEFAULT_EMOTION_MAP = {
    "neutral": {"tempo": 1.0, "gain_db": 0.0},
    "calm": {"tempo": 0.98, "gain_db": -0.5},
    "tense": {"tempo": 1.02, "gain_db": 0.0},
    "angry": {"tempo": 1.05, "gain_db": 1.0},
    "sad": {"tempo": 0.94, "gain_db": -1.5},
    "excited": {"tempo": 1.06, "gain_db": 1.5},
}


@dataclass(frozen=True)
class SegmentAudio:
    segment_id: str
    speaker_role: str
    speaker_gender: str
    scene_id: str | None
    sids: list[str]
    text: str
    context_prefix: str
    emotion: str
    emotion_confidence: float


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def normalize_alias(alias: str) -> str:
    return alias.strip().lower()


def build_alias_phonetic(name_map: dict) -> dict[str, str]:
    alias_to_phonetic: dict[str, str] = {}
    alias_to_phonetics: dict[str, set[str]] = {}
    for canonical, info in name_map.items():
        phonetic = (info.get("phonetic") or "").strip()
        aliases = info.get("aliases") or []
        for alias in aliases:
            norm = normalize_alias(alias)
            if not phonetic:
                continue
            alias_to_phonetics.setdefault(norm, set()).add(phonetic)
    for alias, phonetics in alias_to_phonetics.items():
        if len(phonetics) == 1:
            alias_to_phonetic[alias] = next(iter(phonetics))
    return alias_to_phonetic


def load_alias_regex(derived_dir: Path, name_map: dict) -> re.Pattern:
    regex_path = derived_dir / "aliases_regex.txt"
    if regex_path.exists():
        pattern = regex_path.read_text(encoding="utf-8").strip()
        return re.compile(pattern)
    aliases = []
    for info in name_map.values():
        for alias in info.get("aliases") or []:
            aliases.append(normalize_alias(alias))
    aliases_sorted = sorted(set(aliases), key=lambda a: (-len(a), a))
    regex_body = "|".join(re.escape(alias) for alias in aliases_sorted)
    return re.compile(rf"(?i)\b(?:{regex_body})\b")


def _normalize_lexicon_key(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def load_pronunciation_lexicon(path: Path | None) -> dict[str, str]:
    if not path or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {_normalize_lexicon_key(k): str(v) for k, v in data.items() if k and v}


def merge_pronunciation_lexicons(base: dict[str, str], overrides: dict[str, str]) -> dict[str, str]:
    merged = dict(base)
    merged.update(overrides)
    return merged


def load_prosody_rewrites(path: Path | None) -> dict[str, str]:
    if not path or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    rewrites: dict[str, str] = {}
    for key, value in data.items():
        if not key or value is None:
            continue
        norm_key = re.sub(r"\s+", " ", str(key).strip().lower())
        if not norm_key:
            continue
        rewrites[norm_key] = str(value)
    return rewrites


def build_prosody_rewrite_rules(rewrites: dict[str, str]) -> list[tuple[re.Pattern, str]]:
    if not rewrites:
        return []
    rules = []
    for key in sorted(rewrites.keys(), key=len, reverse=True):
        pattern = re.escape(key).replace(r"\ ", r"\s+")
        regex = re.compile(rf"(?i)\b(?:{pattern})\b")
        rules.append((regex, rewrites[key]))
    return rules


def apply_prosody_rewrites(text: str, rules: list[tuple[re.Pattern, str]]) -> str:
    if not text or not rules:
        return text
    updated = text
    for regex, repl in rules:
        updated = regex.sub(repl, updated)
    return updated


LAUGHTER_NEGATIVE_CUES = {
    "wrong",
    "nonsense",
    "pretend",
    "pretended",
    "lie",
    "lies",
    "deceive",
    "fool",
    "ridiculous",
    "mock",
    "snort",
    "idiot",
    "sneer",
    "scoff",
    "scorn",
    "contempt",
    "disdain",
    "sarcas",
}
LAUGHTER_BITTER_CUES = {
    "bitter",
    "helpless",
    "sad",
    "sorrow",
    "sorrowful",
    "pain",
    "despair",
    "hopeless",
    "tears",
    "tearful",
    "tragic",
}
LAUGHTER_MANIC_CUES = {
    "insane",
    "mad",
    "crazy",
    "lunatic",
    "maniac",
    "demonic",
    "deranged",
    "berserk",
}
LAUGHTER_JOY_CUES = {
    "happy",
    "joy",
    "delight",
    "congrat",
    "great",
    "wonderful",
    "excited",
    "smile",
    "smiled",
    "grin",
    "grinned",
}
LAUGHTER_TOKEN_RE = re.compile(
    r"\b((?:ha|he|hah|heh)(?:[-\s]?(?:ha|he|hah|heh))+)([.!?]+)?\b",
    re.IGNORECASE,
)
LAUGHTER_SINGLE_RE = re.compile(r"\b(heh|hah)\b", re.IGNORECASE)


def apply_laughter_rewrites(text: str) -> str:
    if not text:
        return text

    def _repl(match: re.Match) -> str:
        token = match.group(1)
        punct = match.group(2) or ""
        start = max(0, match.start() - 80)
        end = min(len(text), match.end() + 80)
        context = text[start:end].lower()
        tone = "neutral"
        if "!" in punct or "!" in context:
            tone = "joy"
        if any(cue in context for cue in LAUGHTER_MANIC_CUES):
            tone = "manic"
        elif any(cue in context for cue in LAUGHTER_BITTER_CUES):
            tone = "bitter"
        elif any(cue in context for cue in LAUGHTER_NEGATIVE_CUES):
            tone = "mock"
        elif any(cue in context for cue in LAUGHTER_JOY_CUES):
            tone = "joy"

        syllables = re.findall(r"(?:ha|he|hah|heh)", token.lower())
        if not syllables:
            return match.group(0)

        count = max(2, min(4, len(syllables)))
        if tone == "manic":
            count = max(count, 4)
        elif tone == "joy":
            count = max(count, 3)

        if tone == "bitter":
            replacement = "ha... ha..."
        elif tone == "mock":
            replacement = "ha. ha."
        else:
            replacement = " ".join(["ha"] * count)
        return f"{replacement}{punct}"

    def _single_repl(match: re.Match) -> str:
        start = max(0, match.start() - 60)
        end = min(len(text), match.end() + 60)
        context = text[start:end].lower()
        tone = "neutral"
        if any(cue in context for cue in LAUGHTER_BITTER_CUES):
            tone = "bitter"
        elif any(cue in context for cue in LAUGHTER_NEGATIVE_CUES):
            tone = "mock"
        elif any(cue in context for cue in LAUGHTER_JOY_CUES):
            tone = "joy"
        if tone == "bitter":
            replacement = "ha..."
        elif tone == "mock":
            replacement = "ha."
        elif tone == "joy":
            replacement = "ha!"
        else:
            replacement = "ha"
        return replacement

    text = LAUGHTER_TOKEN_RE.sub(_repl, text)
    text = LAUGHTER_SINGLE_RE.sub(_single_repl, text)
    return text


def build_lexicon_regex(lexicon: dict[str, str]) -> re.Pattern | None:
    if not lexicon:
        return None
    keys = sorted(lexicon.keys(), key=len, reverse=True)
    escaped = []
    for key in keys:
        pattern = re.escape(key).replace(r"\ ", r"\s+")
        escaped.append(pattern)
    body = "|".join(escaped)
    if not body:
        return None
    return re.compile(rf"(?i)\b(?:{body})\b")


def apply_pronunciation_lexicon(
    text: str, lexicon_regex: re.Pattern | None, lexicon: dict[str, str]
) -> str:
    if not lexicon_regex or not lexicon:
        return text

    def _repl(match: re.Match) -> str:
        key = _normalize_lexicon_key(match.group(0))
        return lexicon.get(key, match.group(0))

    return lexicon_regex.sub(_repl, text)


def apply_phonetics(
    text: str,
    alias_regex: re.Pattern,
    alias_to_phonetic: dict[str, str],
    lexicon_regex: re.Pattern | None = None,
    lexicon: dict[str, str] | None = None,
) -> str:
    lexicon = lexicon or {}
    text = apply_pronunciation_lexicon(text, lexicon_regex, lexicon)
    def _repl(match: re.Match) -> str:
        alias = normalize_alias(match.group(0))
        phonetic = alias_to_phonetic.get(alias)
        return phonetic if phonetic else match.group(0)

    return alias_regex.sub(_repl, text)


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def normalize_prosody(text: str) -> str:
    if not text:
        return ""
    # Ensure a space after sentence-ending punctuation to avoid run-ons.
    text = re.sub(r"([.!?])([A-Za-z])", r"\1 \2", text)
    # Collapse repeated exclamations/questions.
    text = re.sub(r"([!?]){2,}", r"\1", text)
    # Limit excessive ellipses.
    text = re.sub(r"\.{4,}", "...", text)
    # Normalize quote spacing after punctuation.
    text = re.sub(r'([.!?])(")', r"\1 \2", text)
    return text


def resolve_voice(speaker: str) -> str:
    return SPEAKER_TO_VOICE.get(speaker, SPEAKER_TO_VOICE["narrator"])


def load_voice_palette(path: Path | None) -> dict[str, list[str]]:
    palette = {k: list(v) for k, v in DEFAULT_VOICE_PALETTE.items()}
    if path and path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for key, value in data.items():
                if isinstance(value, list) and value:
                    palette[key] = [str(v) for v in value]
        except Exception:
            pass
    return palette


def load_emotion_map(path: Path | None) -> dict[str, dict[str, float]]:
    emotion_map = {k: dict(v) for k, v in DEFAULT_EMOTION_MAP.items()}
    if path and path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for key, value in data.items():
                    if not isinstance(value, dict):
                        continue
                    base = emotion_map.get(key, {"tempo": 1.0, "gain_db": 0.0})
                    merged = {
                        "tempo": float(value.get("tempo", base.get("tempo", 1.0))),
                        "gain_db": float(value.get("gain_db", base.get("gain_db", 0.0))),
                    }
                    emotion_map[str(key)] = merged
        except Exception:
            pass
    return emotion_map


class VoiceAssigner:
    def __init__(self, palette: dict[str, list[str]]) -> None:
        self.palette = palette
        self.scene_slots: dict[tuple[str, str], str] = {}
        self.scene_gender_counts: dict[tuple[str, str], int] = {}

    def _pick_voice(self, gender: str, scene_id: str) -> str:
        if gender == "female":
            pool = self.palette.get("female") or self.palette["dialogue_default"]
        elif gender == "male":
            pool = self.palette.get("male") or self.palette["dialogue_default"]
        else:
            pool = self.palette.get("dialogue_default") or self.palette["narrator"]

        key = (scene_id, gender)
        count = self.scene_gender_counts.get(key, 0)
        self.scene_gender_counts[key] = count + 1
        return pool[count % len(pool)]

    def resolve(self, speaker_role: str, speaker_gender: str, scene_id: str | None) -> str:
        if speaker_role == "internal_thought":
            pool = self.palette.get("internal_thought") or self.palette.get("narrator")
            return pool[0] if pool else resolve_voice("narrator")
        if speaker_role in {"narrator", "male", "female"}:
            return resolve_voice(speaker_role)
        if not (speaker_role.startswith("slot_") or speaker_role.startswith("entity_")):
            return resolve_voice("narrator")

        scene = scene_id or "default"
        key = (scene, speaker_role)
        if key in self.scene_slots:
            return self.scene_slots[key]

        voice = self._pick_voice(speaker_gender, scene)
        self.scene_slots[key] = voice
        return voice


def should_skip(path: Path, resume: bool, force: bool) -> bool:
    if force:
        return False
    if not resume:
        return False
    return path.exists() and path.stat().st_size > 0


def run_ffmpeg(args: list[str]) -> bool:
    if not shutil.which("ffmpeg"):
        return False
    try:
        subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError:
        return False


def crop_wav(path: Path, start_sec: float, end_sec: float) -> bool:
    if not shutil.which("ffmpeg"):
        return False
    if end_sec <= start_sec:
        return False
    tmp_path = path.with_suffix(".crop.wav")
    args = [
        "ffmpeg",
        "-y",
        "-i",
        str(path),
        "-ss",
        f"{start_sec:.3f}",
        "-to",
        f"{end_sec:.3f}",
        "-acodec",
        "pcm_s16le",
        str(tmp_path),
    ]
    if run_ffmpeg(args) and tmp_path.exists():
        tmp_path.replace(path)
        return True
    return False


def crop_wav_start(path: Path, start_sec: float) -> bool:
    if not shutil.which("ffmpeg"):
        return False
    if start_sec <= 0:
        return False
    tmp_path = path.with_suffix(".crop.wav")
    args = [
        "ffmpeg",
        "-y",
        "-i",
        str(path),
        "-ss",
        f"{start_sec:.3f}",
        "-acodec",
        "pcm_s16le",
        str(tmp_path),
    ]
    if run_ffmpeg(args) and tmp_path.exists():
        tmp_path.replace(path)
        return True
    return False


def trim_silence(
    path: Path,
    min_ratio: float = 0.1,
    min_duration_sec: float = 0.3,
    threshold_db: float = -45.0,
) -> None:
    if not shutil.which("ffmpeg"):
        return
    try:
        original_duration = wav_duration(path)
    except Exception:
        original_duration = 0.0
    tmp_path = path.with_suffix(".trim.wav")
    thresh = f"{threshold_db:.0f}dB"
    args = [
        "ffmpeg",
        "-y",
        "-i",
        str(path),
        "-af",
        f"silenceremove=start_periods=1:start_threshold={thresh}:stop_periods=0",
        str(tmp_path),
    ]
    if run_ffmpeg(args) and tmp_path.exists():
        try:
            trimmed_duration = wav_duration(tmp_path)
        except Exception:
            tmp_path.replace(path)
            return
        if original_duration > 0:
            ratio = trimmed_duration / original_duration
            if trimmed_duration < min_duration_sec or ratio < min_ratio:
                tmp_path.unlink(missing_ok=True)
                print(
                    f"[WARN] trim_silence skipped: orig={original_duration:.3f}s "
                    f"trimmed={trimmed_duration:.3f}s ratio={ratio:.2f}"
                )
                return
        tmp_path.replace(path)


def smooth_edges(path: Path, pad_ms: int = 40, fade_out_ms: int = 40, fade_in_ms: int = 0) -> None:
    if (pad_ms <= 0 and fade_out_ms <= 0 and fade_in_ms <= 0) or not shutil.which("ffmpeg"):
        return
    try:
        duration = wav_duration(path)
    except Exception:
        return
    if duration <= 0:
        return
    pad_sec = max(0.0, pad_ms / 1000.0)
    fade_out_sec = max(0.0, fade_out_ms / 1000.0)
    fade_in_sec = max(0.0, fade_in_ms / 1000.0)
    filters = []
    if fade_in_sec > 0:
        filters.append(f"afade=t=in:st=0:d={fade_in_sec:.3f}")
    if fade_out_sec > 0:
        start = max(0.0, duration - fade_out_sec)
        filters.append(f"afade=t=out:st={start:.3f}:d={fade_out_sec:.3f}")
    if pad_sec > 0:
        filters.append(f"apad=pad_dur={pad_sec:.3f}")
    if not filters:
        return
    tmp_path = path.with_suffix(".smooth.wav")
    args = [
        "ffmpeg",
        "-y",
        "-i",
        str(path),
        "-af",
        ",".join(filters),
    ]
    if pad_sec > 0:
        args += ["-t", f"{duration + pad_sec:.3f}"]
    args.append(str(tmp_path))
    if run_ffmpeg(args) and tmp_path.exists():
        tmp_path.replace(path)


def smooth_tail(path: Path, pad_ms: int = 40, fade_ms: int = 40) -> None:
    smooth_edges(path, pad_ms=pad_ms, fade_out_ms=fade_ms, fade_in_ms=0)


def post_process_audio(
    path: Path,
    denoise: bool = True,
    highpass_hz: int = 80,
    lowpass_hz: int = 12000,
    denoise_floor_db: float = -25.0,
) -> None:
    if not denoise or not shutil.which("ffmpeg"):
        return
    filters = [f"afftdn=nf={denoise_floor_db}"]
    if highpass_hz > 0:
        filters.append(f"highpass=f={highpass_hz}")
    if lowpass_hz > 0:
        filters.append(f"lowpass=f={lowpass_hz}")
    tmp_path = path.with_suffix(".denoise.wav")
    args = [
        "ffmpeg",
        "-y",
        "-i",
        str(path),
        "-af",
        ",".join(filters),
        str(tmp_path),
    ]
    if run_ffmpeg(args) and tmp_path.exists():
        tmp_path.replace(path)


def apply_emotion_effects(
    path: Path,
    emotion: str,
    emotion_map: dict[str, dict[str, float]],
    strength: float = 1.0,
) -> None:
    if not shutil.which("ffmpeg"):
        return
    settings = emotion_map.get(emotion)
    if not settings:
        return
    strength = max(0.0, min(1.0, strength))
    tempo = float(settings.get("tempo", 1.0))
    gain_db = float(settings.get("gain_db", 0.0))
    tempo = 1.0 + (tempo - 1.0) * strength
    gain_db = gain_db * strength
    if abs(tempo - 1.0) < 0.005 and abs(gain_db) < 0.1:
        return
    tempo = max(0.5, min(2.0, tempo))
    filters = []
    if abs(tempo - 1.0) >= 0.005:
        filters.append(f"atempo={tempo:.3f}")
    if abs(gain_db) >= 0.1:
        filters.append(f"volume={gain_db:.2f}dB")
    if not filters:
        return
    tmp_path = path.with_suffix(".emotion.wav")
    args = [
        "ffmpeg",
        "-y",
        "-i",
        str(path),
        "-af",
        ",".join(filters),
        str(tmp_path),
    ]
    if run_ffmpeg(args) and tmp_path.exists():
        tmp_path.replace(path)


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as handle:
        frames = handle.getnframes()
        rate = handle.getframerate()
    return frames / float(rate) if rate else 0.0


def build_segments(segments_payload: dict) -> list[SegmentAudio]:
    segments = []
    for seg in segments_payload.get("segments", []):
        speaker_role = seg.get("speaker_role") or seg.get("speaker") or "narrator"
        speaker_gender = seg.get("speaker_gender") or (
            "female" if speaker_role == "female" else "male" if speaker_role == "male" else "unknown"
        )
        segments.append(
            SegmentAudio(
                segment_id=seg["segment_id"],
                speaker_role=speaker_role,
                speaker_gender=speaker_gender,
                scene_id=seg.get("scene_id"),
                sids=seg.get("sids") or [],
                text=seg.get("text") or "",
                context_prefix=seg.get("context_prefix") or "",
                emotion=seg.get("emotion") or "neutral",
                emotion_confidence=float(seg.get("emotion_confidence") or 0.0),
            )
        )
    return segments


def ensure_silence_wav(path: Path, duration_sec: float, sample_rate: int, channels: int) -> bool:
    if path.exists() and path.stat().st_size > 0:
        return True
    if not shutil.which("ffmpeg"):
        return False
    channel_layout = "mono" if channels == 1 else "stereo"
    args = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"anullsrc=channel_layout={channel_layout}:sample_rate={sample_rate}",
        "-t",
        f"{duration_sec:.3f}",
        str(path),
    ]
    return run_ffmpeg(args)


def prepend_silence_wav(path: Path, duration_sec: float) -> bool:
    if duration_sec <= 0:
        return True
    if not path.exists() or path.stat().st_size == 0:
        return False
    if not shutil.which("ffmpeg"):
        return False
    try:
        with wave.open(str(path), "rb") as handle:
            sample_rate = handle.getframerate()
            channels = handle.getnchannels()
    except Exception:
        return False

    silence_path = path.with_suffix(".head_silence.wav")
    if not ensure_silence_wav(silence_path, duration_sec, sample_rate, channels):
        return False

    concat_list = path.with_suffix(".head_concat.txt")
    lines = [
        f"file '{silence_path.resolve().as_posix()}'",
        f"file '{path.resolve().as_posix()}'",
    ]
    concat_list.write_text("\n".join(lines) + "\n", encoding="utf-8")

    tmp_path = path.with_suffix(".headpad.wav")
    args = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_list),
        "-acodec",
        "pcm_s16le",
        "-ar",
        str(sample_rate),
        str(tmp_path),
    ]
    if run_ffmpeg(args) and tmp_path.exists():
        tmp_path.replace(path)
        return True
    return False


def crossfade_segments(
    segment_paths: list[Path],
    out_wav: Path,
    crossfade_ms: int,
    sample_rate: int = 24000,
) -> bool:
    if not segment_paths:
        return False
    if crossfade_ms <= 0:
        return False
    if not shutil.which("ffmpeg"):
        return False

    inputs = []
    for seg_path in segment_paths:
        inputs.extend(["-i", str(seg_path)])
    duration = crossfade_ms / 1000.0
    filter_parts = []
    for idx in range(len(segment_paths) - 1):
        left = f"[{idx}:a]" if idx == 0 else f"[xf{idx - 1}]"
        right = f"[{idx + 1}:a]"
        out = f"[xf{idx}]"
        filter_parts.append(
            f"{left}{right}acrossfade=d={duration:.3f}:c1=tri:c2=tri{out}"
        )
    filter_complex = ";".join(filter_parts)
    map_out = f"[xf{len(segment_paths) - 2}]"
    args = [
        "ffmpeg",
        "-y",
        *inputs,
        "-filter_complex",
        filter_complex,
        "-map",
        map_out,
        "-acodec",
        "pcm_s16le",
        "-ar",
        str(sample_rate),
        str(out_wav),
    ]
    return run_ffmpeg(args)


def stitch_segments(
    segment_paths: list[Path],
    out_mp3: Path,
    silence_ms: int = 20,
    bitrate: str = "192k",
    crossfade_ms: int = 0,
) -> bool:
    if not segment_paths:
        return False
    if not shutil.which("ffmpeg"):
        return False

    if crossfade_ms > 0 and len(segment_paths) > 1:
        inputs = []
        for seg_path in segment_paths:
            inputs.extend(["-i", str(seg_path)])
        duration = crossfade_ms / 1000.0
        filter_parts = []
        for idx in range(len(segment_paths) - 1):
            left = f"[{idx}:a]" if idx == 0 else f"[xf{idx - 1}]"
            right = f"[{idx + 1}:a]"
            out = f"[xf{idx}]"
            filter_parts.append(
                f"{left}{right}acrossfade=d={duration:.3f}:c1=tri:c2=tri{out}"
            )
        filter_complex = ";".join(filter_parts)
        map_out = f"[xf{len(segment_paths) - 2}]"
        args = [
            "ffmpeg",
            "-y",
            *inputs,
            "-filter_complex",
            filter_complex,
            "-map",
            map_out,
            "-c:a",
            "libmp3lame",
            "-b:a",
            bitrate,
            str(out_mp3),
        ]
        return run_ffmpeg(args)

    # Determine audio format from first segment
    with wave.open(str(segment_paths[0]), "rb") as handle:
        sample_rate = handle.getframerate()
        channels = handle.getnchannels()

    silence_path = out_mp3.with_suffix(".silence.wav")
    if not ensure_silence_wav(silence_path, silence_ms / 1000.0, sample_rate, channels):
        return False

    concat_list = out_mp3.with_suffix(".concat.txt")
    lines = []
    for idx, seg_path in enumerate(segment_paths):
        lines.append(f"file '{seg_path.resolve().as_posix()}'")
        if idx < len(segment_paths) - 1:
            lines.append(f"file '{silence_path.resolve().as_posix()}'")
    concat_list.write_text("\n".join(lines) + "\n", encoding="utf-8")

    args = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_list),
        "-acodec",
        "pcm_s16le",
        "-ar",
        str(sample_rate),
        "-c:a",
        "libmp3lame",
        "-b:a",
        bitrate,
        str(out_mp3),
    ]
    return run_ffmpeg(args)


def stitch_segments_variable(
    segment_paths: list[Path],
    out_mp3: Path,
    silence_ms_list: list[int],
    bitrate: str = "192k",
) -> bool:
    if not segment_paths:
        return False
    if len(silence_ms_list) != max(0, len(segment_paths) - 1):
        return stitch_segments(segment_paths, out_mp3, silence_ms=20, bitrate=bitrate, crossfade_ms=0)
    if not shutil.which("ffmpeg"):
        return False

    with wave.open(str(segment_paths[0]), "rb") as handle:
        sample_rate = handle.getframerate()
        channels = handle.getnchannels()

    silence_cache: dict[int, Path] = {}
    for silence_ms in sorted(set(silence_ms_list)):
        silence_path = out_mp3.with_suffix(f".silence_{silence_ms}ms.wav")
        if ensure_silence_wav(silence_path, silence_ms / 1000.0, sample_rate, channels):
            silence_cache[silence_ms] = silence_path

    concat_list = out_mp3.with_suffix(".concat.txt")
    lines = []
    for idx, seg_path in enumerate(segment_paths):
        lines.append(f"file '{seg_path.resolve().as_posix()}'")
        if idx < len(segment_paths) - 1:
            silence_ms = silence_ms_list[idx]
            silence_path = silence_cache.get(silence_ms)
            if silence_path is None:
                return False
            lines.append(f"file '{silence_path.resolve().as_posix()}'")
    concat_list.write_text("\n".join(lines) + "\n", encoding="utf-8")

    args = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_list),
        "-acodec",
        "pcm_s16le",
        "-ar",
        str(sample_rate),
        "-c:a",
        "libmp3lame",
        "-b:a",
        bitrate,
        str(out_mp3),
    ]
    return run_ffmpeg(args)


def stitch_wavs(
    segment_paths: list[Path],
    out_wav: Path,
    silence_ms: int = 20,
) -> bool:
    if not segment_paths:
        return False
    if not shutil.which("ffmpeg"):
        return False

    with wave.open(str(segment_paths[0]), "rb") as handle:
        sample_rate = handle.getframerate()
        channels = handle.getnchannels()

    silence_path = out_wav.with_suffix(".silence.wav")
    if not ensure_silence_wav(silence_path, silence_ms / 1000.0, sample_rate, channels):
        return False

    concat_list = out_wav.with_suffix(".concat.txt")
    with concat_list.open("w", encoding="utf-8") as handle:
        for idx, seg_path in enumerate(segment_paths):
            handle.write(f"file '{seg_path.as_posix()}'\n")
            if idx + 1 < len(segment_paths):
                handle.write(f"file '{silence_path.as_posix()}'\n")

    args = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_list),
        "-acodec",
        "pcm_s16le",
        "-ar",
        str(sample_rate),
        str(out_wav),
    ]
    return run_ffmpeg(args)
