#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


LABELS = {"NARRATION", "INTERNAL_THOUGHT", "EXTERNAL_SPEECH"}
TURN_LABELS = {"TURN_START", "TURN_CONTINUE", "NARRATION"}

INTERNAL_THOUGHT_RE = re.compile(
    r"\b("
    r"thought|wondered|pondered|mused|considered|reflected|realized|remembered|"
    r"to himself|to herself|to myself|to themselves|inwardly|"
    r"in his mind|in her mind|in my mind|in their mind|"
    r"in his heart|in her heart|in my heart|in their heart"
    r")\b",
    re.IGNORECASE,
)
MAX_CHARS = 220
MAX_SPANS = 8
MIN_SEG_CHARS = 25
CONTEXT_WORDS = 8

QUOTE_CHARS = {'"', "“", "”", "«", "»"}
PROPER_NAME_RE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b")

SPEECH_VERBS = [
    "said",
    "asked",
    "replied",
    "answered",
    "called",
    "shouted",
    "yelled",
    "whispered",
    "murmured",
    "cried",
    "screamed",
    "roared",
    "snapped",
    "commanded",
    "ordered",
    "remarked",
    "responded",
    "explained",
    "announced",
    "declared",
    "added",
    "continued",
    "interrupted",
]

MALE_PRONOUNS = ["he", "him", "his"]
FEMALE_PRONOUNS = ["she", "her", "hers"]

EMOTION_LABELS = ["neutral", "calm", "tense", "angry", "sad", "excited"]
EMOTION_KEYWORDS = {
    "angry": [
        "angry",
        "furious",
        "rage",
        "roared",
        "shouted",
        "yelled",
        "snarled",
        "snapped",
        "screamed",
        "bellowed",
        "cursed",
        "glared",
        "scowled",
        "sneered",
        "growled",
    ],
    "sad": [
        "sad",
        "sorrow",
        "sob",
        "wept",
        "tears",
        "mourned",
        "lamented",
        "sighed",
        "sigh",
        "despaired",
        "grief",
        "regret",
        "regretted",
        "melancholy",
        "lonely",
    ],
    "excited": [
        "excited",
        "thrilled",
        "delighted",
        "cheered",
        "joy",
        "joyful",
        "happy",
        "happily",
        "laughed",
        "laughing",
        "grinned",
        "smile",
        "smiled",
        "beamed",
        "hahaha",
        "haha",
    ],
    "tense": [
        "tense",
        "nervous",
        "anxious",
        "worried",
        "uneasy",
        "grim",
        "stern",
        "coldly",
        "grimly",
        "serious",
        "threatened",
        "shocked",
        "surprised",
        "incredulous",
        "stunned",
        "shook",
        "shaken",
    ],
    "calm": [
        "calmly",
        "softly",
        "gently",
        "quietly",
        "peacefully",
        "murmured",
        "whispered",
        "soothing",
    ],
}

DEFAULT_EMOTION_POLICY = {
    "enabled": True,
    "suppress_narration": True,
    "min_confidence": {
        "default": 0.8,
        "angry": 0.85,
        "excited": 0.85,
        "sad": 0.82,
        "tense": 0.8,
        "calm": 0.78,
    },
    "cool_down_segments": 1,
    "max_consecutive_emotion": 2,
    "min_chars": 40,
    "strong_confidence": 0.88,
}


@dataclass(frozen=True)
class Span:
    span_id: str
    span_group_id: str
    sid: str
    mode: str
    text: str
    is_dialogue: bool
    char_start: int
    char_end: int
    base_gender: str
    chain_id: int | None
    explicit_role: str | None
    explicit_gender: str | None
    speaker_role: str | None
    speaker_gender: str | None


@dataclass(frozen=True)
class Segment:
    segment_id: str
    speaker_role: str
    speaker_gender: str
    scene_id: str | None
    text: str
    context_prefix: str
    span_ids: list[str]
    sids: list[str]
    emotion: str
    emotion_confidence: float


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_labels(labels_path: Path) -> dict[str, str]:
    labels: dict[str, str] = {}
    with labels_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            entry = json.loads(line)
            sid = entry.get("sid")
            mode = entry.get("mode")
            if sid and mode in LABELS:
                labels[sid] = mode
    return labels


def load_preds(preds_path: Path) -> dict[str, dict[str, float]]:
    preds: dict[str, dict[str, float]] = {}
    with preds_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            entry = json.loads(line)
            sid = entry.get("sid")
            probs = entry.get("probs")
            if sid and isinstance(probs, dict):
                preds[sid] = probs
    return preds


def load_turn_preds(preds_path: Path) -> dict[str, dict[str, float | str]]:
    preds: dict[str, dict[str, float | str]] = {}
    if not preds_path or not preds_path.exists():
        return preds
    with preds_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            entry = json.loads(line)
            sid = entry.get("sid")
            label = entry.get("label")
            conf = entry.get("confidence", 0.0)
            if sid and label in TURN_LABELS:
                try:
                    conf_val = float(conf)
                except Exception:
                    conf_val = 0.0
                preds[sid] = {"label": label, "confidence": conf_val}
    return preds


def load_emotion_policy(path: Path | None) -> dict:
    policy = dict(DEFAULT_EMOTION_POLICY)
    if path and path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                policy.update({k: data[k] for k in data.keys()})
        except Exception:
            pass
    return policy


def looks_like_internal_thought(text: str) -> bool:
    if not text:
        return False
    return bool(INTERNAL_THOUGHT_RE.search(text))


def _emotion_score(text: str) -> dict[str, float]:
    lowered = text.lower()
    scores = {label: 0.0 for label in EMOTION_LABELS}
    for label, keywords in EMOTION_KEYWORDS.items():
        hits = 0
        for kw in keywords:
            if kw in lowered:
                hits += 1
        if hits:
            scores[label] += hits * 1.0
    # Punctuation cues
    exclamations = lowered.count("!")
    questions = lowered.count("?")
    ellipses = lowered.count("...")
    if exclamations:
        scores["excited"] += exclamations * 0.6
        scores["angry"] += exclamations * 0.4
    if questions and not exclamations:
        scores["tense"] += questions * 0.3
    if ellipses:
        scores["sad"] += ellipses * 0.3
        scores["tense"] += ellipses * 0.2
    return scores


def heuristic_emotion(text: str) -> tuple[str, float]:
    if not text:
        return ("neutral", 0.0)
    scores = _emotion_score(text)
    top_label = "neutral"
    top_score = 0.0
    for label, score in scores.items():
        if score > top_score:
            top_label = label
            top_score = score
    if top_score <= 0.0:
        return ("neutral", 0.0)
    confidence = min(1.0, 0.25 + (top_score / 4.0))
    return (top_label, confidence)


def mode_for_sid(
    sid: str,
    labels: dict[str, str] | None,
    preds: dict[str, dict[str, float]],
    text: str | None = None,
) -> str:
    if labels and sid in labels:
        return labels[sid]
    if text and looks_like_internal_thought(text):
        return "INTERNAL_THOUGHT"
    probs = preds.get(sid)
    if not probs:
        return "NARRATION"
    ordered = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)
    top_label, top_val = ordered[0]
    runner_up = ordered[1][1] if len(ordered) > 1 else 0.0
    if top_val >= 0.55 and (top_val - runner_up) >= 0.12:
        return top_label
    return "NARRATION"


def build_block_lookup(blocks_payload: dict, sentences: list[dict]) -> dict[str, dict]:
    sid_to_block: dict[str, dict] = {}
    blocks = blocks_payload.get("blocks", [])
    sid_sequence = [entry["sid"] for entry in sentences]
    sid_to_index = {sid: idx for idx, sid in enumerate(sid_sequence)}

    for block in blocks:
        start_sid = block.get("span_start_sid")
        end_sid = block.get("span_end_sid")
        if start_sid not in sid_to_index or end_sid not in sid_to_index:
            continue
        start_idx = sid_to_index[start_sid]
        end_idx = sid_to_index[end_sid]
        if end_idx < start_idx:
            start_idx, end_idx = end_idx, start_idx
        for sid in sid_sequence[start_idx : end_idx + 1]:
            sid_to_block[sid] = block
    return sid_to_block


def compile_alias_regex(aliases: Iterable[str]) -> re.Pattern:
    ordered = sorted(set(aliases), key=len, reverse=True)
    escaped = [re.escape(alias) for alias in ordered if alias]
    pattern = r"\b(?:" + "|".join(escaped) + r")\b"
    return re.compile(pattern, re.IGNORECASE)


def _canonical_name(alias: str, alias_to_canonical: dict[str, list[str] | str]) -> str | None:
    canonical = alias_to_canonical.get(alias)
    if isinstance(canonical, list):
        canonical = canonical[0] if canonical else None
    if isinstance(canonical, str) and canonical.strip():
        return canonical.strip()
    return None


def _canonical_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _gender_for_name(
    name: str,
    alias_to_gender: dict[str, str],
    alias_to_canonical: dict[str, list[str] | str],
) -> str:
    key = name.lower()
    if key in alias_to_gender:
        return alias_to_gender[key]
    for alias, canonical in alias_to_canonical.items():
        if isinstance(canonical, list) and name in canonical:
            return alias_to_gender.get(alias, "unknown")
        if isinstance(canonical, str) and canonical == name:
            return alias_to_gender.get(alias, "unknown")
    return "unknown"


def _find_named_alias(
    text: str,
    alias_regex: re.Pattern,
    alias_to_speaker: dict[str, bool],
    prefer_last: bool = False,
) -> str | None:
    matches = []
    for match in alias_regex.finditer(text):
        alias = match.group(0).lower()
        if not alias_to_speaker.get(alias, False):
            continue
        matches.append(alias)
    if not matches:
        return None
    return matches[-1] if prefer_last else matches[0]


def _find_proper_name(text: str, prefer_last: bool = False) -> str | None:
    matches = list(PROPER_NAME_RE.finditer(text))
    if not matches:
        return None

    possessive = []
    for match in matches:
        tail = text[match.end() :].lstrip()
        if tail.startswith("'s") or tail.startswith("’s"):
            possessive.append(match)

    pool = possessive or matches
    chosen = pool[-1] if prefer_last else pool[0]
    return chosen.group(1)


def _find_leading_name(
    text: str, alias_regex: re.Pattern, alias_to_speaker: dict[str, bool]
) -> str | None:
    if not text:
        return None
    stripped = text.lstrip()
    for match in alias_regex.finditer(stripped):
        if match.start() > 3:
            break
        alias = match.group(0).lower()
        if alias_to_speaker.get(alias, False):
            return match.group(0)
    match = PROPER_NAME_RE.match(stripped)
    if match:
        return match.group(1)
    return None


def is_strong_boundary(text: str) -> bool:
    if not text:
        return False
    stripped = text.lstrip()
    if stripped.startswith("Chapter") or stripped.startswith("CHAPTER"):
        return True
    if text.endswith("\n\n"):
        return True
    upper = stripped.strip()
    if upper.isupper():
        return True
    if upper.endswith(":") and len(upper) <= 60 and upper.count(" ") <= 6:
        return True
    return False


def split_by_quotes(text: str) -> list[tuple[str, bool, int, int]]:
    if not any(ch in text for ch in QUOTE_CHARS):
        return [(text, False, 0, len(text))]

    spans: list[tuple[str, bool, int, int]] = []
    buf: list[str] = []
    in_quote = False
    span_start = 0
    for idx, ch in enumerate(text):
        if ch in QUOTE_CHARS:
            if buf:
                spans.append(("".join(buf), in_quote, span_start, idx))
                buf = []
            in_quote = not in_quote
            span_start = idx + 1
            continue
        if not buf:
            span_start = idx
        buf.append(ch)

    if buf:
        spans.append(("".join(buf), in_quote, span_start, len(text)))

    if in_quote:
        return [(text, False, 0, len(text))]

    return spans


def _is_punct_only(text: str) -> bool:
    return re.search(r"[A-Za-z0-9]", text) is None


def split_long_span(text: str, rel_start: int, max_chars: int = MAX_CHARS) -> list[tuple[str, int, int]]:
    if len(text) <= max_chars:
        return [(text, rel_start, rel_start + len(text))]

    parts: list[tuple[str, int, int]] = []
    offset = 0
    length = len(text)
    min_cut = max(20, int(max_chars * 0.4))
    break_chars = ".!?;:,\n"

    while offset < length:
        remaining = length - offset
        if remaining <= max_chars:
            parts.append((text[offset:], rel_start + offset, rel_start + length))
            break

        window = text[offset : offset + max_chars + 1]
        cut = -1
        for idx in range(len(window) - 1, min_cut - 1, -1):
            if window[idx] in break_chars:
                cut = idx + 1
                break
        if cut == -1:
            space = window.rfind(" ")
            if space >= min_cut:
                cut = space + 1
        if cut == -1:
            cut = max_chars
        if cut > max_chars:
            cut = max_chars

        end = offset + cut
        parts.append((text[offset:end], rel_start + offset, rel_start + end))
        offset = end

    return parts


def _normalize_word(word: str) -> str:
    return re.sub(r"[^a-z0-9']+", "", word.lower())


def _tokenize_words(text: str) -> list[str]:
    return [_normalize_word(w) for w in text.split() if _normalize_word(w)]


def _context_words(text: str) -> list[str]:
    if not text:
        return []
    return re.findall(r"[A-Za-z0-9']+", text)


def infer_gender_from_text(
    text: str,
    alias_regex: re.Pattern,
    alias_to_gender: dict[str, str],
    alias_to_speaker: dict[str, bool],
) -> str:
    if not text:
        return "unknown"
    matches = list(alias_regex.finditer(text))
    for match in matches:
        alias = match.group(0).lower()
        if not alias_to_speaker.get(alias, False):
            continue
        gender = alias_to_gender.get(alias)
        if gender in {"male", "female"}:
            return gender
    words = _tokenize_words(text)
    if any(w in MALE_PRONOUNS for w in words):
        return "male"
    if any(w in FEMALE_PRONOUNS for w in words):
        return "female"
    return "unknown"


def infer_gender_from_pronouns(text: str) -> str:
    if not text:
        return "unknown"
    words = _tokenize_words(text)
    if any(w in MALE_PRONOUNS for w in words):
        return "male"
    if any(w in FEMALE_PRONOUNS for w in words):
        return "female"
    return "unknown"


def is_attribution_span(text: str) -> bool:
    if not text:
        return False
    if len(text) > 160:
        return False
    if "\n\n" in text:
        return False
    lowered = text.lower()
    for verb in SPEECH_VERBS:
        if re.search(rf"\b{re.escape(verb)}\b", lowered):
            return True
    return False


def _assemble_text(chunks: list[str]) -> str:
    if not chunks:
        return ""
    text = chunks[0]
    for prev, cur in zip(chunks, chunks[1:]):
        if prev.endswith("\n"):
            text += cur
        else:
            text += " " + cur
    return text


def build_span_segments(
    chapter_payload: dict,
    blocks_payload: dict,
    preds: dict[str, dict[str, float]],
    labels: dict[str, str] | None,
    alias_to_gender: dict[str, str],
    alias_to_canonical: dict[str, list[str] | str],
    alias_to_speaker: dict[str, bool],
    include_spans: bool = False,
    director=None,
    llm_cache: dict | None = None,
    llm_max_calls: int = 0,
    llm_min_confidence: float = 0.6,
    llm_max_quotes: int = 12,
    emotion_mode: str = "off",
    emotion_scope: str = "dialogue",
    emotion_director=None,
    emotion_cache: dict | None = None,
    emotion_max_calls: int = 0,
    emotion_min_confidence: float = 0.6,
    emotion_max_segments: int = 8,
    emotion_context_chars: int = 320,
    emotion_policy: dict | None = None,
    turn_preds: dict[str, dict[str, float | str]] | None = None,
    turn_min_confidence: float = 0.6,
) -> dict:
    sentences = chapter_payload.get("sentences") or []
    sid_to_text = {entry["sid"]: entry["text"] for entry in sentences}

    sid_to_block = build_block_lookup(blocks_payload, sentences)
    alias_regex = compile_alias_regex(alias_to_canonical.keys())

    spans: list[Span] = []
    span_counter = 0
    group_counter = 0

    for entry in sentences:
        sid = entry["sid"]
        text = entry["text"]
        mode = mode_for_sid(sid, labels, preds, text)
        block = sid_to_block.get(sid)
        base_gender = "unknown"
        if block:
            resolved = block.get("resolved_gender")
            if resolved in {"male", "female"}:
                base_gender = resolved

        parts = split_by_quotes(text)
        if len(parts) == 1 and not parts[0][1] and mode == "EXTERNAL_SPEECH":
            parts = [(parts[0][0], True, parts[0][2], parts[0][3])]

        for span_text, in_quote, rel_start, rel_end in parts:
            group_counter += 1
            group_id = f"{sid}-G{group_counter:03d}"
            for chunk_text, chunk_start, chunk_end in split_long_span(span_text, rel_start):
                leading = len(chunk_text) - len(chunk_text.lstrip())
                trailing = len(chunk_text) - len(chunk_text.rstrip())
                cleaned = chunk_text.strip()
                if not cleaned or _is_punct_only(cleaned):
                    continue
                span_counter += 1
                is_dialogue = bool(in_quote) or (mode == "EXTERNAL_SPEECH" and len(parts) == 1)
                gender_hint = base_gender if is_dialogue else "unknown"
                if is_dialogue and gender_hint == "unknown":
                    inferred = infer_gender_from_text(chunk_text, alias_regex, alias_to_gender, alias_to_speaker)
                    if inferred in {"male", "female"}:
                        gender_hint = inferred

                spans.append(
                    Span(
                        span_id=f"{sid}-P{span_counter:03d}",
                        span_group_id=group_id,
                        sid=sid,
                        mode=mode,
                        text=cleaned,
                        is_dialogue=is_dialogue,
                        char_start=entry.get("char_start", 0) + chunk_start + leading,
                        char_end=entry.get("char_start", 0) + chunk_end - trailing,
                        base_gender=gender_hint,
                        chain_id=None,
                        explicit_role=None,
                        explicit_gender=None,
                        speaker_role=None,
                        speaker_gender=None,
                    )
                )

    # Pass 1: assign chain ids based on dialogue continuity
    chain_id = 0
    in_chain = False
    updated_spans: list[Span] = []
    for span in spans:
        if span.is_dialogue:
            if not in_chain:
                chain_id += 1
                in_chain = True
            updated_spans.append(span.__class__(**{**span.__dict__, "chain_id": chain_id}))
            continue

        if in_chain and is_attribution_span(span.text) and not is_strong_boundary(span.text):
            updated_spans.append(span.__class__(**{**span.__dict__, "chain_id": chain_id}))
            continue

        in_chain = False
        updated_spans.append(span)

    spans = updated_spans

    def _assign_explicit(idx: int, name: str, context_text: str | None = None) -> None:
        key = name.lower()
        canonical = _canonical_name(key, alias_to_canonical) or name
        if not canonical:
            return
        gender = _gender_for_name(canonical, alias_to_gender, alias_to_canonical)
        if gender == "unknown" and context_text:
            inferred = infer_gender_from_pronouns(context_text)
            if inferred in {"male", "female"}:
                gender = inferred
        role = f"entity_{_canonical_key(canonical)}"
        span = spans[idx]
        spans[idx] = span.__class__(
            **{**span.__dict__, "explicit_role": role, "explicit_gender": gender}
        )

    # Pass 1.5: explicit attribution binding (Stop-Gate is absolute, no overlap)
    for idx, span in enumerate(spans):
        if not span.is_dialogue:
            continue
        # Rule A: Subject + Colon (bind to nearest named subject before colon)
        if idx > 0:
            prev_span = spans[idx - 1]
            if (not prev_span.is_dialogue) and prev_span.text.rstrip().endswith(":"):
                alias = _find_named_alias(
                    prev_span.text, alias_regex, alias_to_speaker, prefer_last=True
                )
                if not alias:
                    alias = _find_proper_name(prev_span.text, prefer_last=True)
                if alias:
                    _assign_explicit(idx, alias, context_text=prev_span.text)
                    continue
        # Rule B: Quote + Speech Verb (bind to name in following attribution span)
        if idx + 1 < len(spans):
            next_span = spans[idx + 1]
            if (not next_span.is_dialogue) and is_attribution_span(next_span.text):
                alias = _find_named_alias(
                    next_span.text, alias_regex, alias_to_speaker, prefer_last=False
                )
                if not alias:
                    alias = _find_proper_name(next_span.text, prefer_last=False)
                if alias:
                    _assign_explicit(idx, alias, context_text=next_span.text)
                    continue
            if not span.explicit_role and (not next_span.is_dialogue):
                leading = _find_leading_name(
                    next_span.text, alias_regex, alias_to_speaker
                )
                if leading:
                    _assign_explicit(idx, leading, context_text=next_span.text)

    # Pass 1.6: quote-attribution-quote chaining (same speaker on both sides)
    for idx, span in enumerate(spans):
        if not span.is_dialogue:
            continue
        if idx + 2 >= len(spans):
            continue
        mid = spans[idx + 1]
        nxt = spans[idx + 2]
        if mid.is_dialogue or not nxt.is_dialogue:
            continue
        if not is_attribution_span(mid.text):
            continue
        alias = _find_named_alias(mid.text, alias_regex, alias_to_speaker, prefer_last=False)
        if not alias:
            alias = _find_proper_name(mid.text, prefer_last=False)
        if alias:
            if spans[idx].explicit_role is None:
                _assign_explicit(idx, alias, context_text=mid.text)
            if spans[idx + 2].explicit_role is None:
                _assign_explicit(idx + 2, alias, context_text=mid.text)

    # Group spans by chain
    chain_to_indices: dict[int, list[int]] = {}
    for idx, span in enumerate(spans):
        if span.chain_id is None:
            continue
        chain_to_indices.setdefault(span.chain_id, []).append(idx)

    # Optional LLM fallback for unresolved dialogue spans
    llm_calls = 0
    if director is not None:
        for cid, indices in chain_to_indices.items():
            unresolved = [
                i
                for i in indices
                if spans[i].is_dialogue and spans[i].explicit_role is None
            ]
            if not unresolved:
                continue
            if llm_max_calls and llm_calls >= llm_max_calls:
                break

            # Build chain text with quote markers
            qid_to_index: dict[str, int] = {}
            chain_chunks: list[str] = []
            qid_counter = 1
            for idx in indices:
                span = spans[idx]
                if span.is_dialogue:
                    qid = f"Q{qid_counter}"
                    qid_to_index[qid] = idx
                    chain_chunks.append(f"[{qid}] {span.text} [/{qid}]")
                    qid_counter += 1
                else:
                    chain_chunks.append(span.text)
            chain_text = " ".join(chain_chunks)

            # Build candidate list from named aliases in chain
            candidates: list[str] = []
            for match in alias_regex.finditer(chain_text):
                alias = match.group(0).lower()
                if not alias_to_speaker.get(alias, False):
                    continue
                canonical = _canonical_name(alias, alias_to_canonical) or match.group(0)
                if canonical not in candidates:
                    candidates.append(canonical)
            for match in PROPER_NAME_RE.finditer(chain_text):
                name = match.group(1)
                if name not in candidates:
                    candidates.append(name)

            if not candidates:
                continue

            quote_ids = [qid for qid, idx in qid_to_index.items() if idx in unresolved]
            if not quote_ids or len(quote_ids) > llm_max_quotes:
                continue

            cache_key = f"{chapter_payload.get('chapter')}:C{cid}"
            cached = llm_cache.get(cache_key) if isinstance(llm_cache, dict) else None
            assignments = cached
            if assignments is None:
                try:
                    assignments = director.assign(chain_text, quote_ids, candidates)
                except Exception:
                    assignments = {}
                if isinstance(llm_cache, dict):
                    llm_cache[cache_key] = assignments
                llm_calls += 1

            if not isinstance(assignments, dict):
                continue

            for qid, assignment in assignments.items():
                if qid not in quote_ids:
                    continue
                idx = qid_to_index.get(qid)
                if idx is None:
                    continue
                if spans[idx].explicit_role is not None:
                    continue
                speaker = getattr(assignment, 'speaker', None) if hasattr(assignment, 'speaker') else None
                confidence = getattr(assignment, 'confidence', 0.0) if hasattr(assignment, 'confidence') else None
                if speaker is None and isinstance(assignment, dict):
                    speaker = assignment.get('speaker')
                    confidence = assignment.get('confidence', 0.0)
                if speaker is None:
                    continue
                if isinstance(confidence, str):
                    try:
                        confidence = float(confidence)
                    except ValueError:
                        confidence = 0.0
                if confidence is None:
                    confidence = 0.0
                if confidence < llm_min_confidence:
                    continue
                if str(speaker).strip().upper() == 'UNKNOWN':
                    continue
                _assign_explicit(idx, str(speaker))

    # Propagate explicit role across chunks from the same original span
    group_to_explicit: dict[str, tuple[str, str | None]] = {}
    for span in spans:
        if not span.is_dialogue:
            continue
        if span.explicit_role:
            group_to_explicit[span.span_group_id] = (span.explicit_role, span.explicit_gender)

    if group_to_explicit:
        updated_spans: list[Span] = []
        for span in spans:
            if not span.is_dialogue:
                updated_spans.append(span)
                continue
            explicit = group_to_explicit.get(span.span_group_id)
            if explicit and span.explicit_role is None:
                role, gender = explicit
                updated_spans.append(
                    span.__class__(
                        **{
                            **span.__dict__,
                            "explicit_role": role,
                            "explicit_gender": gender,
                        }
                    )
                )
            else:
                updated_spans.append(span)
        spans = updated_spans

    # Pass 2: assign speaker roles within each chain
    for cid, indices in chain_to_indices.items():
        slots: list[dict] = []
        slot_counter = 0
        last_slot = None
        last_explicit_slot = None
        pending_gender = None
        dialogue_spans = [spans[i] for i in indices if spans[i].is_dialogue]
        chain_has_explicit = any(spans[i].explicit_role for i in indices)
        avg_len = sum(len(s.text) for s in dialogue_spans) / max(1, len(dialogue_spans))
        should_alternate = len(dialogue_spans) >= 3 and avg_len < 120

        def _register_role(role: str, gender: str, is_explicit: bool) -> dict:
            nonlocal slots
            for slot in slots:
                if slot["role"] == role:
                    return slot
            if not is_explicit:
                slot_roles = [s for s in slots if s["role"].startswith("slot_")]
                if len(slot_roles) >= 4:
                    return slots[0]
            slot = {"role": role, "gender": gender or "unknown", "last_used": -1}
            slots.append(slot)
            return slot

        def _get_or_create_slot(gender: str) -> dict:
            nonlocal slots, slot_counter
            for slot in slots:
                if slot["role"].startswith("slot_") and slot["gender"] == gender:
                    return slot
            if slot_counter < 4:
                role = f"slot_{chr(ord('A') + slot_counter)}"
                slot_counter += 1
                return _register_role(role, gender, is_explicit=False)
            return slots[0]

        def _pick_alternate_slot() -> dict:
            nonlocal slots
            if not slots:
                return _get_or_create_slot("unknown")
            if len(slots) == 1:
                return slots[0]
            if last_slot is None:
                return slots[0]
            for slot in slots:
                if slot is not last_slot:
                    return slot
            return slots[0]

        for idx in indices:
            span = spans[idx]
            if not span.is_dialogue:
                if is_attribution_span(span.text):
                    inferred = infer_gender_from_text(span.text, alias_regex, alias_to_gender, alias_to_speaker)
                    if inferred in {"male", "female"}:
                        pending_gender = inferred
                continue

            if span.explicit_role:
                gender = span.explicit_gender or span.base_gender
                slot = _register_role(span.explicit_role, gender, is_explicit=True)
                slot["last_used"] = idx
                last_slot = slot
                last_explicit_slot = slot
                spans[idx] = span.__class__(
                    **{
                        **span.__dict__,
                        "speaker_role": slot["role"],
                        "speaker_gender": slot["gender"],
                    }
                )
                continue

            if last_explicit_slot is not None:
                slot = last_explicit_slot
                slot["last_used"] = idx
                last_slot = slot
                spans[idx] = span.__class__(
                    **{
                        **span.__dict__,
                        "speaker_role": slot["role"],
                        "speaker_gender": slot["gender"],
                    }
                )
                continue

            gender = span.base_gender
            if pending_gender in {"male", "female"}:
                gender = pending_gender
                pending_gender = None

            if gender not in {"male", "female"}:
                if chain_has_explicit and last_slot is not None:
                    slot = last_slot
                elif should_alternate:
                    slot = _pick_alternate_slot()
                elif last_slot is not None:
                    slot = last_slot
                else:
                    slot = _get_or_create_slot("unknown")
            else:
                slot = _get_or_create_slot(gender)

            slot["last_used"] = idx
            last_slot = slot

            speaker_role = slot["role"]
            speaker_gender = slot["gender"] if slot["gender"] in {"male", "female"} else gender
            spans[idx] = span.__class__(
                **{**span.__dict__, "speaker_role": speaker_role, "speaker_gender": speaker_gender}
            )

    # Assign narrator role to non-dialogue spans
    spans = [
        span.__class__(
            **{
                **span.__dict__,
                "speaker_role": span.speaker_role
                or ("internal_thought" if span.mode == "INTERNAL_THOUGHT" else "narrator"),
                "speaker_gender": span.speaker_gender or "unknown",
            }
        )
        for span in spans
    ]

    # Enforce continuity across chunk groups without explicit roles
    group_last: dict[str, tuple[str, str]] = {}
    updated_spans = []
    for span in spans:
        if not span.is_dialogue:
            updated_spans.append(span)
            continue
        if span.explicit_role is None:
            last = group_last.get(span.span_group_id)
            if last is not None:
                role, gender = last
                span = span.__class__(
                    **{
                        **span.__dict__,
                        "speaker_role": role,
                        "speaker_gender": gender,
                    }
                )
        if span.speaker_role and span.speaker_gender:
            group_last[span.span_group_id] = (span.speaker_role, span.speaker_gender)
        updated_spans.append(span)
    spans = updated_spans

    # Build segments from spans
    segments: list[Segment] = []
    current_role = None
    current_gender = None
    current_scene = None
    current_texts: list[str] = []
    current_span_ids: list[str] = []
    current_sids: list[str] = []
    current_len = 0

    def finalize_segment():
        nonlocal current_texts, current_span_ids, current_sids, current_len, current_role, current_gender, current_scene
        if not current_texts:
            return
        segment_id = f"{chapter_payload.get('chapter')}-SP{len(segments)+1:04d}"
        segments.append(
            Segment(
                segment_id=segment_id,
                speaker_role=current_role or "narrator",
                speaker_gender=current_gender or "unknown",
                scene_id=current_scene,
                text=_assemble_text(current_texts),
                context_prefix="",
                span_ids=current_span_ids,
                sids=current_sids,
                emotion="neutral",
                emotion_confidence=0.0,
            )
        )
        current_texts = []
        current_span_ids = []
        current_sids = []
        current_len = 0

    def _turn_start(sid: str) -> bool:
        if not turn_preds:
            return False
        entry = turn_preds.get(sid)
        if not entry:
            return False
        if entry.get("label") != "TURN_START":
            return False
        try:
            conf = float(entry.get("confidence", 0.0))
        except Exception:
            conf = 0.0
        return conf >= turn_min_confidence

    for span in spans:
        scene_id = f"{chapter_payload.get('chapter')}-C{span.chain_id:04d}" if span.chain_id else None
        if current_role is None or not current_texts:
            current_role = span.speaker_role
            current_gender = span.speaker_gender
            current_scene = scene_id

        if _turn_start(span.sid) and current_texts:
            finalize_segment()
            current_role = span.speaker_role
            current_gender = span.speaker_gender
            current_scene = scene_id

        boundary = is_strong_boundary(span.text)
        if (
            span.speaker_role != current_role
            or span.speaker_gender != current_gender
            or scene_id != current_scene
        ) and current_texts:
            finalize_segment()
            current_role = span.speaker_role
            current_gender = span.speaker_gender
            current_scene = scene_id

        if boundary and current_texts:
            finalize_segment()
            current_role = span.speaker_role
            current_gender = span.speaker_gender
            current_scene = scene_id

        projected_len = current_len + (1 if current_texts and not current_texts[-1].endswith("\n") else 0) + len(span.text)
        if current_texts and (projected_len > MAX_CHARS or len(current_texts) >= MAX_SPANS):
            finalize_segment()
            current_role = span.speaker_role
            current_gender = span.speaker_gender
            current_scene = scene_id

        current_texts.append(span.text)
        current_span_ids.append(span.span_id)
        current_sids.append(span.sid)
        current_len = projected_len

        if boundary:
            finalize_segment()

    if current_texts:
        finalize_segment()

    # Merge very short segments with neighbors of the same speaker to reduce choppiness.
    if segments:
        merged: list[Segment] = []

        def _join_text(left: str, right: str) -> str:
            if not left:
                return right
            if left.endswith("\n"):
                return left + right
            return left + " " + right

        idx = 0
        while idx < len(segments):
            seg = segments[idx]
            if len(seg.text) < MIN_SEG_CHARS:
                if merged:
                    prev = merged[-1]
                    if (
                        prev.speaker_role == seg.speaker_role
                        and prev.speaker_gender == seg.speaker_gender
                        and prev.scene_id == seg.scene_id
                        and len(prev.text) + 1 + len(seg.text) <= MAX_CHARS
                    ):
                        merged[-1] = prev.__class__(
                            **{
                                **prev.__dict__,
                                "text": _join_text(prev.text, seg.text),
                                "span_ids": prev.span_ids + seg.span_ids,
                                "sids": prev.sids + seg.sids,
                            }
                        )
                        idx += 1
                        continue
                if idx + 1 < len(segments):
                    nxt = segments[idx + 1]
                    if (
                        nxt.speaker_role == seg.speaker_role
                        and nxt.speaker_gender == seg.speaker_gender
                        and nxt.scene_id == seg.scene_id
                        and len(seg.text) + 1 + len(nxt.text) <= MAX_CHARS
                    ):
                        merged.append(
                            seg.__class__(
                                **{
                                    **seg.__dict__,
                                    "text": _join_text(seg.text, nxt.text),
                                    "span_ids": seg.span_ids + nxt.span_ids,
                                    "sids": seg.sids + nxt.sids,
                                }
                            )
                        )
                        idx += 2
                        continue
            merged.append(seg)
            idx += 1
        segments = merged

    # Add context prefixes
    prev_words: deque[str] = deque(maxlen=CONTEXT_WORDS)
    updated_segments: list[Segment] = []
    for segment in segments:
        context_prefix = " ".join(prev_words)
        updated_segments.append(
            segment.__class__(**{**segment.__dict__, "context_prefix": context_prefix})
        )
        for word in _context_words(segment.text):
            prev_words.append(word)

    # Emotion tagging (heuristic with optional LLM override)
    def _should_emote(seg: Segment) -> bool:
        scope = (emotion_scope or "dialogue").lower()
        if scope == "all":
            return True
        if scope == "dialogue":
            return seg.speaker_role != "narrator"
        return False

    def _emotion_context(seg: Segment) -> str:
        context = f"{seg.context_prefix} {seg.text}".strip()
        if len(context) > emotion_context_chars:
            context = context[-emotion_context_chars:]
        return context

    emotion_mode = (emotion_mode or "off").lower()
    emotion_segments: list[Segment] = []
    pending: list[tuple[Segment, str, str, float]] = []
    for seg in updated_segments:
        label = "neutral"
        conf = 0.0
        if emotion_mode != "off" and _should_emote(seg):
            label, conf = heuristic_emotion(seg.text)
        cache_key = f"emotion:{chapter_payload.get('chapter')}:{seg.segment_id}"
        if (
            emotion_mode in {"llm", "llm_if_low"}
            and _should_emote(seg)
            and emotion_director is not None
        ):
            cached = emotion_cache.get(cache_key) if isinstance(emotion_cache, dict) else None
            if isinstance(cached, dict):
                cached_label = str(cached.get("label", label))
                cached_conf = float(cached.get("confidence", conf) or 0.0)
                label, conf = cached_label, cached_conf
            elif emotion_mode == "llm" or conf < emotion_min_confidence:
                pending.append((seg, cache_key, label, conf))

        emotion_segments.append(
            seg.__class__(
                **{
                    **seg.__dict__,
                    "emotion": label,
                    "emotion_confidence": round(float(conf), 4),
                }
            )
        )

    if pending and emotion_director is not None and emotion_mode in {"llm", "llm_if_low"}:
        calls = 0
        idx = 0
        while idx < len(pending):
            if emotion_max_calls and calls >= emotion_max_calls:
                break
            batch = pending[idx : idx + max(1, emotion_max_segments)]
            idx += len(batch)
            items = [(seg.segment_id, _emotion_context(seg)) for seg, _, _, _ in batch]
            try:
                results = emotion_director.classify_emotions(items, EMOTION_LABELS)
            except Exception:
                results = {}
            calls += 1
            if not isinstance(results, dict):
                continue
            for seg, cache_key, base_label, base_conf in batch:
                assignment = results.get(seg.segment_id)
                if assignment is None and isinstance(results, dict):
                    assignment = results.get(str(seg.segment_id))
                label = base_label
                conf = base_conf
                if assignment is not None:
                    if hasattr(assignment, "label"):
                        label = getattr(assignment, "label", base_label)
                        conf = getattr(assignment, "confidence", base_conf)
                    elif isinstance(assignment, dict):
                        label = assignment.get("label", base_label)
                        conf = assignment.get("confidence", base_conf)
                try:
                    conf = float(conf)
                except (TypeError, ValueError):
                    conf = base_conf
                if label not in EMOTION_LABELS or conf < emotion_min_confidence:
                    label, conf = base_label, base_conf
                if isinstance(emotion_cache, dict):
                    emotion_cache[cache_key] = {"label": label, "confidence": conf}
                # update the segment in place
                for i, existing in enumerate(emotion_segments):
                    if existing.segment_id == seg.segment_id:
                        emotion_segments[i] = existing.__class__(
                            **{
                                **existing.__dict__,
                                "emotion": label,
                                "emotion_confidence": round(float(conf), 4),
                            }
                        )
                        break

    # Apply emotion policy gating
    policy = emotion_policy or DEFAULT_EMOTION_POLICY
    if policy.get("enabled", True):
        min_conf_map = policy.get("min_confidence") or {}
        min_chars = int(policy.get("min_chars", 0))
        max_consecutive = int(policy.get("max_consecutive_emotion", 0))
        cool_down = int(policy.get("cool_down_segments", 0))
        strong_conf = float(policy.get("strong_confidence", 0.85))
        suppress_narration = bool(policy.get("suppress_narration", True))

        gated: list[Segment] = []
        consecutive = 0
        cooldown_remaining = 0
        for seg in emotion_segments:
            label = seg.emotion
            conf = seg.emotion_confidence
            if label == "neutral":
                consecutive = 0
                cooldown_remaining = max(0, cooldown_remaining - 1)
                gated.append(seg)
                continue

            if suppress_narration and seg.speaker_role in {"narrator", "internal_thought"}:
                label = "neutral"
                conf = 0.0
            elif min_chars and len(seg.text) < min_chars:
                label = "neutral"
                conf = 0.0
            elif cooldown_remaining > 0:
                label = "neutral"
                conf = 0.0
            else:
                min_conf = float(min_conf_map.get(label, min_conf_map.get("default", 0.0)))
                if conf < min_conf:
                    label = "neutral"
                    conf = 0.0

            if label == "neutral":
                consecutive = 0
                cooldown_remaining = max(0, cooldown_remaining - 1)
                gated.append(
                    seg.__class__(
                        **{
                            **seg.__dict__,
                            "emotion": label,
                            "emotion_confidence": round(float(conf), 4),
                        }
                    )
                )
                continue

            consecutive += 1
            if max_consecutive and consecutive > max_consecutive:
                label = "neutral"
                conf = 0.0
                consecutive = 0
            if conf >= strong_conf and cool_down > 0:
                cooldown_remaining = cool_down

            gated.append(
                seg.__class__(
                    **{
                        **seg.__dict__,
                        "emotion": label,
                        "emotion_confidence": round(float(conf), 4),
                    }
                )
            )

        emotion_segments = gated

    payload = {
        "chapter": chapter_payload.get("chapter"),
        "source_file": chapter_payload.get("source_file"),
        "segments": [segment.__dict__ for segment in emotion_segments],
    }
    if include_spans:
        payload["spans"] = [span.__dict__ for span in spans]
    return payload
