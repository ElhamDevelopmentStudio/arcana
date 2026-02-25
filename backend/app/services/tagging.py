import re

POSITIVE_WORDS = {
    "happy",
    "joy",
    "relief",
    "smile",
    "calm",
    "hope",
    "good",
    "great",
    "love",
    "warm",
    "grateful",
}

NEGATIVE_WORDS = {
    "angry",
    "sad",
    "fear",
    "pain",
    "hate",
    "cold",
    "grim",
    "dark",
    "despair",
    "bad",
    "terrible",
    "blood",
}

EMOTION_SHIFT_CONNECTOR_HINTS = {
    "but",
    "however",
    "though",
    "although",
    "nevertheless",
    "instead",
    "yet",
}

EMOTION_SHIFT_MIN_DELTA = 0.35
NARRATION_INTERNAL_THOUGHT_CONNECTORS = {
    "but",
    "however",
    "though",
    "while",
    "when",
    "yet",
}
INTERNAL_EXTERNAL_SPEECH_CONNECTORS = {
    "but",
    "however",
    "while",
    "when",
    "then",
    "after",
    "yet",
}

TENSION_SIGNAL_WORDS = {
    "danger",
    "dangerous",
    "threat",
    "threatened",
    "escape",
    "chase",
    "fight",
    "attacked",
    "attack",
    "attackers",
    "blood",
    "knife",
    "gun",
    "gunfire",
    "scream",
    "screamed",
    "alarm",
    "afraid",
    "panic",
    "urgent",
    "desperate",
    "desperately",
    "trapped",
    "siege",
    "battle",
    "collapse",
    "ambush",
    "rushed",
    "racing",
    "breathed",
    "sudden",
    "suddenly",
}

TENSION_INTENSIFIERS = {
    "so",
    "very",
    "deeply",
    "barely",
    "hardly",
    "almost",
    "just",
    "now",
    "still",
    "then",
    "before",
    "while",
}
TONE_REVERSAL_CONNECTORS = {
    "but",
    "however",
    "though",
    "although",
    "nevertheless",
    "instead",
    "yet",
    "still",
}
TONE_REVERSAL_MARKERS = {
    "yeah right",
    "as if",
    "sure",
    "of course",
    "just my luck",
    "what a surprise",
    "great",
    "wonderful",
    "amazing",
    "lucky",
    "brilliant",
    "perfect",
    "excellent",
}

DOMINANCE_PRONOUN_TOKENS = {
    "he",
    "she",
    "they",
    "his",
    "her",
    "their",
    "them",
    "him",
    "i",
    "me",
    "we",
    "us",
    "my",
    "our",
}

EMOTION_SECONDARY_LABEL_HINTS = {
    "positive": [
        ("joyful", {"joy", "happy", "smile", "great"}),
        ("hopeful", {"hope", "warm", "relief"}),
        ("gratitude", {"grateful", "thank"}),
        ("calm", {"calm"}),
    ],
    "negative": [
        ("fearful", {"fear", "despair"}),
        ("angry", {"angry", "hate", "grim", "cold"}),
        ("grief", {"sad", "bad"}),
        ("violent", {"blood", "terrible"}),
    ],
    "neutral": [
        ("neutral", {"neutral"}),
    ],
}

STRUCTURAL_TYPE_NARRATION = "narration"
STRUCTURAL_TYPE_DIALOGUE = "dialogue"
STRUCTURAL_TYPE_INTERNAL_THOUGHT = "internal thought"
STRUCTURAL_TYPE_MIXED = "mixed"
STRUCTURAL_TYPE_DESCRIPTION = "description"
STRUCTURAL_TYPE_ACTION = "action"

SPEAKER_PATTERN = re.compile(r'"[^"]+"\s+([A-Za-z][A-Za-z0-9_-]*)\s+said\b', re.IGNORECASE)
DIALOGUE_QUOTE_RE = re.compile(
    r'"[^"]+"\s*(?:[,;:]?\s*(?:[A-Za-z][A-Za-z0-9_-]*\s+)?'
    r"(?:said|asked|replied|whispered|murmured|shouted|yelled|answered)\b[^.!?\n]*[.!?]?)",
    re.IGNORECASE,
)
DIALOGUE_QUOTE_MARKER_RE = re.compile(r'(["“])[^"“”]*["”]')
DASH_LEADER_RE = re.compile(r"(?m)^\s*-\s+[^\n]+")
INTERNAL_THOUGHT_RE = re.compile(
    r"\b(?:thought|wondered|wondering|realized|realizing|remembered|remembering|decided|deciding|figured|figuring|imagined|imagine|suspected|considered|knew|sensed)\b",
    re.IGNORECASE,
)
ACTION_VERB_RE = re.compile(
    r"\b(?:dashed|rushed|sprinted|entered|entered|opened|closed|smashed|slammed|grabbed|dropped|threw|stabbed|struck|leapt|ran|run|walked|walk|stumbled|collided|lurched|drew|pulled|pushed|shouted|whispered)\b",
    re.IGNORECASE,
)
DESCRIPTION_HINT_RE = re.compile(
    r"\b(?:moonlight|sunlight|silence|shadows|window|door|street|forest|field|hall|room|sky|rain|fog|mist|light|shadow|wind|air|smell|echo)\b",
    re.IGNORECASE,
)


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z']+", text.lower())


def _build_trimmed_span(raw_text: str, raw_start: int, candidate: str) -> tuple[int, int]:
    if not candidate:
        return raw_start, raw_start
    leading = len(candidate) - len(candidate.lstrip())
    trailing = len(candidate) - len(candidate.rstrip())
    span_start = raw_start + leading
    span_end = max(span_start, raw_start + len(candidate) - trailing)
    return span_start, span_end


def _clamp_confidence(value: float) -> float:
    return max(0.0, min(1.0, round(float(value), 4)))


def _compute_type_confidence(structure: str) -> float:
    return {
        STRUCTURAL_TYPE_NARRATION: 0.7,
        STRUCTURAL_TYPE_DIALOGUE: 0.92,
        STRUCTURAL_TYPE_INTERNAL_THOUGHT: 0.83,
        STRUCTURAL_TYPE_MIXED: 0.72,
        STRUCTURAL_TYPE_DESCRIPTION: 0.75,
        STRUCTURAL_TYPE_ACTION: 0.78,
    }.get(structure, 0.65)


def detect_dialogue_blocks(text: str) -> list[dict[str, str]]:
    quoted_spans: list[tuple[int, int]] = [
        (match.start(), match.end()) for match in DIALOGUE_QUOTE_RE.finditer(text)
    ]
    if not quoted_spans:
        quoted_spans = [
            (match.start(), match.end()) for match in DIALOGUE_QUOTE_MARKER_RE.finditer(text)
        ]
    dash_line_spans: list[tuple[int, int]] = []
    for match in DASH_LEADER_RE.finditer(text):
        line_start = match.start()
        line_end = text.find("\n", match.end())
        if line_end < 0:
            line_end = len(text)
        dash_line_spans.append((line_start, line_end))

    candidate_spans = sorted(set(quoted_spans + dash_line_spans))
    if not candidate_spans:
        return [{"type": "narration", "text": text.strip()}] if text.strip() else []

    merged_spans: list[tuple[int, int]] = []
    for start, end in candidate_spans:
        if not merged_spans or start > merged_spans[-1][1]:
            merged_spans.append((start, end))
            continue
        merged_spans[-1] = (merged_spans[-1][0], max(merged_spans[-1][1], end))

    blocks: list[dict[str, str]] = []
    cursor = 0
    for start, end in merged_spans:
        if start > cursor:
            narrative = text[cursor:start].strip()
            if narrative:
                blocks.append({"type": "narration", "text": narrative})

        dialogue = text[start:end].strip()
        if dialogue:
            blocks.append({"type": "dialogue", "text": dialogue})
        cursor = end

    if cursor < len(text):
        trailing = text[cursor:].strip()
        if trailing:
            blocks.append({"type": "narration", "text": trailing})

    return blocks


def detect_narration_blocks(text: str) -> list[dict[str, str]]:
    return [block for block in detect_dialogue_blocks(text) if block["type"] == "narration"]


def detect_structure(text: str) -> str:
    blocks = detect_dialogue_blocks(text)
    has_dialogue = any(block["type"] == STRUCTURAL_TYPE_DIALOGUE for block in blocks)
    has_narration = any(block["type"] == STRUCTURAL_TYPE_NARRATION for block in blocks)
    has_internal_thought = bool(INTERNAL_THOUGHT_RE.search(text))
    has_action = bool(ACTION_VERB_RE.search(text))
    has_description = bool(DESCRIPTION_HINT_RE.search(text))

    if has_dialogue and (has_internal_thought or has_narration):
        return STRUCTURAL_TYPE_MIXED
    if has_dialogue:
        return STRUCTURAL_TYPE_DIALOGUE
    if has_internal_thought:
        return STRUCTURAL_TYPE_INTERNAL_THOUGHT
    if has_action:
        return STRUCTURAL_TYPE_ACTION
    if has_description:
        return STRUCTURAL_TYPE_DESCRIPTION
    return STRUCTURAL_TYPE_NARRATION


def _pick_secondary_label(sentiment: str, tokens: list[str]) -> str:
    for label, hints in EMOTION_SECONDARY_LABEL_HINTS.get(sentiment, []):
        if any(token in tokens for token in hints):
            return label
    return "neutral" if sentiment == "neutral" else sentiment


def _extract_emotion_units(text: str) -> list[dict[str, object]]:
    raw_units = list(re.finditer(r"[^.!?;]+(?:[.!?;]+|$)", text))
    if not raw_units:
        return []

    units: list[dict[str, object]] = []
    split_pattern = re.compile(
        r"\b(?:but|however|though|although|nevertheless|instead|yet)\b",
        re.IGNORECASE,
    )

    for match in raw_units:
        raw = match.group(0)
        start, end = match.span()

        trimmed = raw.strip()
        if not trimmed:
            continue

        unit_start_offset = start + len(raw) - len(raw.lstrip())
        unit_end_offset = unit_start_offset + len(trimmed)
        clause_body = trimmed

        split_matches = list(split_pattern.finditer(clause_body))
        if not split_matches:
            units.append({"text": trimmed, "start_char": unit_start_offset, "end_char": unit_end_offset})
            continue

        segment_cursor = 0
        for split_match in split_matches:
            candidate_raw = clause_body[segment_cursor:split_match.start()]
            candidate = candidate_raw.strip()
            if candidate:
                sub_start, sub_end = _build_trimmed_span(
                    raw_text=clause_body,
                    raw_start=unit_start_offset + segment_cursor,
                    candidate=candidate_raw,
                )
                units.append({"text": candidate, "start_char": sub_start, "end_char": sub_end})
            segment_cursor = split_match.start()

        tail_raw = clause_body[segment_cursor:]
        tail = tail_raw.strip()
        if tail:
            tail_start, tail_end = _build_trimmed_span(
                raw_text=clause_body,
                raw_start=unit_start_offset + segment_cursor,
                candidate=tail_raw,
            )
            units.append({
                "text": tail,
                "start_char": tail_start,
                "end_char": tail_end,
            })

    return units


def _classify_internal_or_narrative_unit(text: str) -> str:
    if INTERNAL_THOUGHT_RE.search(text):
        return STRUCTURAL_TYPE_INTERNAL_THOUGHT
    if DIALOGUE_QUOTE_RE.search(text) or DIALOGUE_QUOTE_MARKER_RE.search(text):
        return STRUCTURAL_TYPE_DIALOGUE
    return STRUCTURAL_TYPE_NARRATION


def _classify_internal_or_dialogue_unit(text: str) -> str:
    if INTERNAL_THOUGHT_RE.search(text):
        return STRUCTURAL_TYPE_INTERNAL_THOUGHT
    if DIALOGUE_QUOTE_RE.search(text) or DIALOGUE_QUOTE_MARKER_RE.search(text):
        return STRUCTURAL_TYPE_DIALOGUE
    return STRUCTURAL_TYPE_NARRATION


def _extract_narration_internal_units(text: str) -> list[dict[str, object]]:
    raw_units = list(re.finditer(r"[^.!?;]+(?:[.!?;]+|$)", text))
    if not raw_units:
        return []

    units: list[dict[str, object]] = []
    split_pattern = re.compile(
        r"\b(?:but|however|though|although|while|when|yet)\b",
        re.IGNORECASE,
    )

    for match in raw_units:
        raw = match.group(0)
        start, end = match.span()
        trimmed = raw.strip()
        if not trimmed:
            continue

        unit_start_offset = start + len(raw) - len(raw.lstrip())
        unit_end_offset = unit_start_offset + len(trimmed)
        clause_body = trimmed

        split_matches = list(split_pattern.finditer(clause_body))
        if not split_matches:
            units.append(
                {
                    "text": trimmed,
                    "start_char": unit_start_offset,
                    "end_char": unit_end_offset,
                    "type": _classify_internal_or_narrative_unit(trimmed),
                }
            )
            continue

        segment_cursor = 0
        for split_match in split_matches:
            candidate_raw = clause_body[segment_cursor:split_match.start()]
            candidate = candidate_raw.strip()
            if candidate:
                candidate_start, candidate_end = _build_trimmed_span(
                    raw_text=clause_body,
                    raw_start=unit_start_offset + segment_cursor,
                    candidate=candidate_raw,
                )
                units.append(
                    {
                        "text": candidate,
                        "start_char": candidate_start,
                        "end_char": candidate_end,
                        "type": _classify_internal_or_narrative_unit(candidate),
                    }
                )
            segment_cursor = split_match.start()

        tail = clause_body[segment_cursor:].strip()
        if tail:
            tail_raw = clause_body[segment_cursor:]
            tail_start, tail_end = _build_trimmed_span(
                raw_text=clause_body,
                raw_start=unit_start_offset + segment_cursor,
                candidate=tail_raw,
            )
            units.append(
                {
                    "text": tail,
                    "start_char": tail_start,
                    "end_char": tail_end,
                    "type": _classify_internal_or_narrative_unit(tail),
                }
            )

    return units


def _extract_internal_external_units(text: str) -> list[dict[str, object]]:
    raw_units = list(re.finditer(r"[^.!?;]+(?:[.!?;]+|$)", text))
    if not raw_units:
        return []

    units: list[dict[str, object]] = []
    split_pattern = re.compile(
        r"\b(?:but|however|though|although|while|when|then|after|yet)\b",
        re.IGNORECASE,
    )

    for match in raw_units:
        raw = match.group(0)
        start, end = match.span()
        trimmed = raw.strip()
        if not trimmed:
            continue

        unit_start_offset = start + len(raw) - len(raw.lstrip())
        unit_end_offset = unit_start_offset + len(trimmed)
        clause_body = trimmed

        split_matches = list(split_pattern.finditer(clause_body))
        if not split_matches:
            units.append(
                {
                    "text": trimmed,
                    "start_char": unit_start_offset,
                    "end_char": unit_end_offset,
                    "type": _classify_internal_or_dialogue_unit(trimmed),
                }
            )
            continue

        segment_cursor = 0
        for split_match in split_matches:
            candidate_raw = clause_body[segment_cursor:split_match.start()]
            candidate = candidate_raw.strip()
            if candidate:
                candidate_start = unit_start_offset + segment_cursor
                candidate_end = unit_start_offset + split_match.start()
                candidate_start, candidate_end = _build_trimmed_span(
                    raw_text=clause_body,
                    raw_start=unit_start_offset + segment_cursor,
                    candidate=candidate_raw,
                )
                units.append(
                    {
                        "text": candidate,
                        "start_char": candidate_start,
                        "end_char": candidate_end,
                        "type": _classify_internal_or_dialogue_unit(candidate),
                    }
                )
            segment_cursor = split_match.start()

        tail = clause_body[segment_cursor:].strip()
        if tail:
            tail_raw = clause_body[segment_cursor:]
            tail_start, tail_end = _build_trimmed_span(
                raw_text=clause_body,
                raw_start=unit_start_offset + segment_cursor,
                candidate=tail_raw,
            )
            units.append(
                {
                    "text": tail,
                    "start_char": tail_start,
                    "end_char": tail_end,
                    "type": _classify_internal_or_dialogue_unit(tail),
                }
            )

    return units


def detect_narration_internal_thought_shift(text: str) -> dict[str, object]:
    units = _extract_narration_internal_units(text)
    if len(units) < 2:
        return {
            "has_shift": False,
            "from": None,
            "to": None,
            "confidence": 0.0,
            "evidence": {
                "unit_count": len(units),
                "shift_count": 0,
                "transition_count": 0,
            },
        }

    transitions: list[dict[str, object]] = []
    for index in range(1, len(units)):
        prev = units[index - 1]
        current = units[index]
        prev_type = str(prev["type"])
        current_type = str(current["type"])

        if prev_type == current_type:
            continue
        if {prev_type, current_type} != {
            STRUCTURAL_TYPE_NARRATION,
            STRUCTURAL_TYPE_INTERNAL_THOUGHT,
        }:
            continue

        transition_span = text[max(0, int(prev["end_char"]) - 24) : int(current["start_char"]) + 24].lower()
        has_connector = any(hint in transition_span for hint in NARRATION_INTERNAL_THOUGHT_CONNECTORS)
        confidence = 0.62 if has_connector else 0.5
        transitions.append(
            {
                "from_type": prev_type,
                "to_type": current_type,
                "from": prev,
                "to": current,
                "has_connector": has_connector,
                "confidence": round(confidence, 4),
            }
        )

    if not transitions:
        return {
            "has_shift": False,
            "from": None,
            "to": None,
            "confidence": 0.0,
            "evidence": {
                "unit_count": len(units),
                "shift_count": 0,
                "transition_count": 0,
            },
        }

    strongest = transitions[0]
    if len(transitions) > 1:
        strongest = max(
            transitions,
            key=lambda entry: (
                float(entry["confidence"]),
                -int(entry["from"]["start_char"]),
            ),
        )

    return {
        "has_shift": True,
        "from": {
            "type": str(strongest["from_type"]),
            "text": str(strongest["from"]["text"]),
            "start_char": int(strongest["from"]["start_char"]),
            "end_char": int(strongest["from"]["end_char"]),
        },
        "to": {
            "type": str(strongest["to_type"]),
            "text": str(strongest["to"]["text"]),
            "start_char": int(strongest["to"]["start_char"]),
            "end_char": int(strongest["to"]["end_char"]),
        },
        "confidence": float(strongest["confidence"]),
        "evidence": {
            "unit_count": len(units),
            "shift_count": len(transitions),
            "transition_count": len(transitions),
            "has_connector": bool(strongest["has_connector"]),
        },
    }


def detect_internal_external_speech_shift(text: str) -> dict[str, object]:
    units = _extract_internal_external_units(text)
    if len(units) < 2:
        return {
            "has_shift": False,
            "from": None,
            "to": None,
            "confidence": 0.0,
            "evidence": {
                "unit_count": len(units),
                "shift_count": 0,
                "transition_count": 0,
            },
        }

    transitions: list[dict[str, object]] = []
    for index in range(1, len(units)):
        prev = units[index - 1]
        current = units[index]
        prev_type = str(prev["type"])
        current_type = str(current["type"])

        if prev_type == current_type:
            continue
        if {prev_type, current_type} != {
            STRUCTURAL_TYPE_INTERNAL_THOUGHT,
            STRUCTURAL_TYPE_DIALOGUE,
        }:
            continue

        transition_span = text[max(0, int(prev["end_char"]) - 26) : int(current["start_char"]) + 26].lower()
        has_connector = any(hint in transition_span for hint in INTERNAL_EXTERNAL_SPEECH_CONNECTORS)
        confidence = 0.64 if has_connector else 0.52
        transitions.append(
            {
                "from_type": prev_type,
                "to_type": current_type,
                "from": prev,
                "to": current,
                "has_connector": has_connector,
                "confidence": round(confidence, 4),
            }
        )

    if not transitions:
        return {
            "has_shift": False,
            "from": None,
            "to": None,
            "confidence": 0.0,
            "evidence": {
                "unit_count": len(units),
                "shift_count": 0,
                "transition_count": 0,
            },
        }

    strongest = transitions[0]
    if len(transitions) > 1:
        strongest = max(
            transitions,
            key=lambda entry: (
                float(entry["confidence"]),
                -int(entry["from"]["start_char"]),
            ),
        )

    return {
        "has_shift": True,
        "from": {
            "type": str(strongest["from_type"]),
            "text": str(strongest["from"]["text"]),
            "start_char": int(strongest["from"]["start_char"]),
            "end_char": int(strongest["from"]["end_char"]),
        },
        "to": {
            "type": str(strongest["to_type"]),
            "text": str(strongest["to"]["text"]),
            "start_char": int(strongest["to"]["start_char"]),
            "end_char": int(strongest["to"]["end_char"]),
        },
        "confidence": float(strongest["confidence"]),
        "evidence": {
            "unit_count": len(units),
            "shift_count": len(transitions),
            "transition_count": len(transitions),
            "has_connector": bool(strongest["has_connector"]),
        },
    }


def detect_tone_reversal(text: str) -> dict[str, object]:
    units = _extract_emotion_units(text)
    if len(units) < 2:
        return {
            "has_tone_reversal": False,
            "tone": None,
            "from": None,
            "to": None,
            "confidence": 0.0,
            "evidence": {
                "unit_count": len(units),
                "candidate_count": 0,
                "transition_count": 0,
            },
        }

    evaluated: list[dict[str, object]] = []
    for unit in units:
        valence, intensity, emotion_confidence, primary_label, secondary_label = compute_valence(str(unit["text"]))
        if primary_label == "neutral":
            continue

        evaluated.append(
            {
                "text": unit["text"],
                "start_char": int(unit["start_char"]),
                "end_char": int(unit["end_char"]),
                "valence": valence,
                "intensity": intensity,
                "primary_label": primary_label,
                "secondary_label": secondary_label,
                "emotion_confidence": emotion_confidence,
            }
        )

    if len(evaluated) < 2:
        return {
            "has_tone_reversal": False,
            "tone": None,
            "from": None,
            "to": None,
            "confidence": 0.0,
            "evidence": {
                "unit_count": len(units),
                "candidate_count": 0,
                "transition_count": 0,
            },
        }

    candidates: list[dict[str, object]] = []
    for index in range(1, len(evaluated)):
        prev = evaluated[index - 1]
        current = evaluated[index]
        prev_label = str(prev["primary_label"])
        current_label = str(current["primary_label"])

        if prev_label == current_label:
            continue
        if {prev_label, current_label} != {"positive", "negative"}:
            continue

        transition_span = text[max(0, int(prev["end_char"]) - 36) : int(current["start_char"]) + 36].lower()
        has_connector = any(connector in transition_span for connector in TONE_REVERSAL_CONNECTORS)
        detected_markers = [marker for marker in TONE_REVERSAL_MARKERS if marker in transition_span]
        has_irony_marker = bool(detected_markers)
        delta = abs(float(current["valence"]) - float(prev["valence"]))

        if delta < 0.4 and not (has_connector or has_irony_marker):
            continue

        confidence = min(
            0.97,
            round(0.33 + 0.05 * delta + (0.20 if has_connector else 0.0) + (0.18 if has_irony_marker else 0.0), 4),
        )
        candidates.append(
            {
                "index": index - 1,
                "from": prev,
                "to": current,
                "from_label": prev_label,
                "to_label": current_label,
                "has_connector": has_connector,
                "has_irony_marker": has_irony_marker,
                "detected_markers": detected_markers,
                "delta": delta,
                "confidence": confidence,
            }
        )

    if not candidates:
        return {
            "has_tone_reversal": False,
            "tone": None,
            "from": None,
            "to": None,
            "confidence": 0.0,
            "evidence": {
                "unit_count": len(units),
                "candidate_count": 0,
                "transition_count": 0,
            },
        }

    strongest = max(candidates, key=lambda entry: (float(entry["confidence"]), -int(entry["from"]["start_char"])))
    return {
        "has_tone_reversal": True,
        "tone": "dark_irony",
        "from": {
            "label": str(strongest["from_label"]),
            "secondary_label": str(strongest["from"]["secondary_label"]),
            "valence": float(strongest["from"]["valence"]),
            "intensity": float(strongest["from"]["intensity"]),
            "start_char": int(strongest["from"]["start_char"]),
            "end_char": int(strongest["from"]["end_char"]),
        },
        "to": {
            "label": str(strongest["to_label"]),
            "secondary_label": str(strongest["to"]["secondary_label"]),
            "valence": float(strongest["to"]["valence"]),
            "intensity": float(strongest["to"]["intensity"]),
            "start_char": int(strongest["to"]["start_char"]),
            "end_char": int(strongest["to"]["end_char"]),
        },
        "confidence": float(strongest["confidence"]),
        "evidence": {
            "unit_count": len(units),
            "candidate_count": len(candidates),
            "transition_count": len(candidates),
            "selected_transition_index": int(strongest["index"]),
            "has_connector": bool(strongest["has_connector"]),
            "has_irony_marker": bool(strongest["has_irony_marker"]),
            "detected_markers": list(strongest["detected_markers"]),
            "delta": float(strongest["delta"]),
        },
    }


def _extract_sub_segment_label(unit: dict[str, object] | None, keys: tuple[str, ...]) -> str | None:
    if not unit or not isinstance(unit, dict):
        return None
    for key in keys:
        value = unit.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _build_sub_segment_boundaries(*, segment_text: str, tag_payloads: list[tuple[str, dict[str, object]]]) -> list[dict[str, object]]:
    boundaries: list[dict[str, object]] = []

    for shift_type, shift_payload in tag_payloads:
        if not shift_payload:
            continue

        if "has_shift" in shift_payload:
            has_shift = bool(shift_payload.get("has_shift", False))
        else:
            has_shift = bool(shift_payload.get("has_tone_reversal", False))

        if not has_shift:
            continue

        from_payload = shift_payload.get("from")
        to_payload = shift_payload.get("to")
        if not isinstance(from_payload, dict) or not isinstance(to_payload, dict):
            continue

        from_end = int(from_payload.get("end_char", -1))
        to_start = int(to_payload.get("start_char", from_end))
        if from_end < 0 or to_start < 0:
            continue

        from_start = int(from_payload.get("start_char", 0))
        to_end = int(to_payload.get("end_char", 0))

        segment_end = len(segment_text)
        boundary_start = max(0, min(from_end, segment_end))
        boundary_end = max(boundary_start, min(to_start, segment_end))

        if "has_shift" in shift_payload:
            from_key = "type"
            to_key = "type"
        else:
            from_key = "label"
            to_key = "label"

        from_label = _extract_sub_segment_label(
            from_payload,
            keys=(from_key, "primary_label", "secondary_label"),
        )
        to_label = _extract_sub_segment_label(to_payload, keys=(to_key, "primary_label", "secondary_label"))

        from_text = str(from_payload.get("text", ""))
        to_text = str(to_payload.get("text", ""))
        if not from_text.strip():
            from_slice_end = max(0, min(from_end, len(segment_text)))
            from_slice_start = max(0, min(from_start, from_slice_end))
            from_text = segment_text[from_slice_start:from_slice_end]
        if not to_text.strip():
            to_slice_end = max(0, min(to_end, len(segment_text)))
            to_slice_start = max(0, min(to_start, to_slice_end))
            to_text = segment_text[to_slice_start:to_slice_end]

        boundaries.append(
            {
                "shift_type": shift_type,
                "boundary_start_char": boundary_start,
                "boundary_end_char": boundary_end,
                "from_label": from_label,
                "to_label": to_label,
                "from_text": from_text,
                "to_text": to_text,
                "confidence": float(shift_payload.get("confidence", 0.0)),
            }
        )

    return boundaries


def detect_emotion_shift(text: str) -> dict[str, object]:
    units = _extract_emotion_units(text)
    if len(units) < 2:
        return {
            "has_shift": False,
            "from": None,
            "to": None,
            "confidence": 0.0,
            "evidence": {
                "unit_count": len(units),
                "shift_count": 0,
                "max_delta": 0.0,
            },
        }

    evaluated: list[dict[str, object]] = []
    for unit in units:
        valence, intensity, emotion_confidence, primary_label, secondary_label = compute_valence(str(unit["text"]))
        evaluated.append(
            {
                "text": unit["text"],
                "start_char": int(unit["start_char"]),
                "end_char": int(unit["end_char"]),
                "valence": valence,
                "intensity": intensity,
                "primary_label": primary_label,
                "secondary_label": secondary_label,
                "emotion_confidence": emotion_confidence,
            }
        )

    transitions: list[dict[str, object]] = []
    for index in range(1, len(evaluated)):
        prev = evaluated[index - 1]
        current = evaluated[index]
        delta = float(abs(float(current["valence"]) - float(prev["valence"])))
        if delta < EMOTION_SHIFT_MIN_DELTA:
            continue

        from_label = str(prev["primary_label"])
        to_label = str(current["primary_label"])
        if from_label == to_label:
            continue

        connector_span = text[max(0, int(prev["end_char"]) - 30) : int(current["start_char"]) + 30].lower()
        has_connector = any(hint in connector_span for hint in EMOTION_SHIFT_CONNECTOR_HINTS)
        confidence = min(0.95, 0.35 + delta + (0.15 if has_connector else 0.0))

        transitions.append(
            {
                "index": index - 1,
                "from": prev,
                "to": current,
                "delta": delta,
                "has_connector": has_connector,
                "confidence": round(confidence, 4),
            }
        )

    if not transitions:
        return {
            "has_shift": False,
            "from": None,
            "to": None,
            "confidence": 0.0,
            "evidence": {
                "unit_count": len(units),
                "shift_count": 0,
                "max_delta": 0.0,
            },
        }

    strongest = max(transitions, key=lambda entry: float(entry["delta"]))
    return {
        "has_shift": True,
        "from": {
            "label": str(strongest["from"]["primary_label"]),
            "secondary_label": str(strongest["from"]["secondary_label"]),
            "valence": float(strongest["from"]["valence"]),
            "intensity": float(strongest["from"]["intensity"]),
            "start_char": int(strongest["from"]["start_char"]),
            "end_char": int(strongest["from"]["end_char"]),
        },
        "to": {
            "label": str(strongest["to"]["primary_label"]),
            "secondary_label": str(strongest["to"]["secondary_label"]),
            "valence": float(strongest["to"]["valence"]),
            "intensity": float(strongest["to"]["intensity"]),
            "start_char": int(strongest["to"]["start_char"]),
            "end_char": int(strongest["to"]["end_char"]),
        },
        "confidence": float(strongest["confidence"]),
        "evidence": {
            "unit_count": len(units),
            "shift_count": len(transitions),
            "max_delta": float(strongest["delta"]),
            "has_connector": bool(strongest["has_connector"]),
            "transition_index": int(strongest["index"]),
        },
    }


def compute_valence(text: str) -> tuple[float, float, float, str, str]:
    tokens = _tokenize(text)
    if not tokens:
        return 0.0, 0.0, 0.4, "neutral", "neutral"

    positive = sum(1 for token in tokens if token in POSITIVE_WORDS)
    negative = sum(1 for token in tokens if token in NEGATIVE_WORDS)
    raw_valence = (positive - negative) / len(tokens)
    valence = max(-1.0, min(1.0, raw_valence))
    intensity = abs(valence)
    sentiment_signal_total = positive + negative
    if sentiment_signal_total > 0:
        confidence = 0.6
    else:
        confidence = 0.4

    if valence >= 0.2:
        primary_label = "positive"
    elif valence <= -0.2:
        primary_label = "negative"
    else:
        primary_label = "neutral"

    secondary_label = _pick_secondary_label(sentiment=primary_label, tokens=tokens)
    return round(valence, 4), round(intensity, 4), confidence, primary_label, secondary_label


def _tension_contribution_level(value: float) -> str:
    if value >= 0.75:
        return "high"
    if value >= 0.5:
        return "moderate"
    if value >= 0.25:
        return "low"
    return "calm"


def _compute_tension_confidence(value: float, structure: str, signal_count: int, intensifier_count: int) -> float:
    base_confidence = 0.32 + (0.56 * value)
    if structure in {STRUCTURAL_TYPE_ACTION, STRUCTURAL_TYPE_MIXED, STRUCTURAL_TYPE_DIALOGUE}:
        base_confidence += 0.08
    elif structure == STRUCTURAL_TYPE_DESCRIPTION:
        base_confidence -= 0.07
    signal_boost = min(0.12, 0.03 * signal_count)
    intensifier_boost = min(0.06, 0.02 * intensifier_count)
    return _clamp_confidence(base_confidence + signal_boost + intensifier_boost)


def compute_tension_contribution(text: str, valence: float, intensity: float, structure: str) -> float:
    tokens = _tokenize(text)
    signal_count = sum(1 for token in tokens if token in TENSION_SIGNAL_WORDS)
    intensifier_count = sum(1 for token in tokens if token in TENSION_INTENSIFIERS)

    base_tension = intensity
    if structure in {STRUCTURAL_TYPE_ACTION, STRUCTURAL_TYPE_MIXED, STRUCTURAL_TYPE_DIALOGUE}:
        base_tension += 0.18
    elif structure == STRUCTURAL_TYPE_DESCRIPTION:
        base_tension -= 0.12

    signal_boost = min(0.45, 0.12 * signal_count)
    intensifier_boost = min(0.15, 0.03 * intensifier_count)
    tension_value = base_tension + signal_boost + intensifier_boost

    if valence > 0.25:
        tension_value *= 0.7
    elif valence < -0.2:
        tension_value *= 1.1

    normalized = max(0.0, min(1.0, round(tension_value, 4)))
    return normalized


def _dominance_contribution_level(value: float) -> str:
    if value >= 0.8:
        return "dominant"
    if value >= 0.6:
        return "strong"
    if value >= 0.35:
        return "moderate"
    return "low"


def _compute_dominance_confidence(value: float, speaker: str, structure: str, evidence: dict[str, object]) -> float:
    pronoun_score = 0.06 * int(bool(evidence.get("speaker_resolved")))
    pronoun_ref_count = int(evidence.get("pronoun_reference_count", 0))
    proper_noun_count = int(evidence.get("proper_noun_hits", 0))
    proper_noun_score = min(0.2, 0.02 * proper_noun_count)
    pronoun_ref_score = min(0.12, 0.02 * pronoun_ref_count)
    structure_bonus = {
        STRUCTURAL_TYPE_DIALOGUE: 0.12,
        STRUCTURAL_TYPE_MIXED: 0.06,
        STRUCTURAL_TYPE_ACTION: 0.06,
    }.get(structure, 0.0)

    base_confidence = 0.33 + (0.52 * value) + pronoun_score + pronoun_ref_score + proper_noun_score + structure_bonus
    if not speaker or speaker == "unknown":
        base_confidence -= 0.12
    return _clamp_confidence(base_confidence)


def compute_dominance_contribution(
    text: str,
    speaker: str,
    structure: str,
) -> tuple[float, str, str, dict]:
    tokens = _tokenize(text)
    proper_noun_hits = re.findall(r"\b[A-Z][a-z]{1,}\b", text)

    if speaker and speaker != "unknown":
        base = 0.72
    elif structure == STRUCTURAL_TYPE_DIALOGUE:
        base = 0.55
    elif structure == STRUCTURAL_TYPE_MIXED:
        base = 0.48
    elif structure == STRUCTURAL_TYPE_INTERNAL_THOUGHT:
        base = 0.44
    else:
        base = 0.32

    if structure == STRUCTURAL_TYPE_ACTION:
        base += 0.08
    if structure == STRUCTURAL_TYPE_DESCRIPTION:
        base -= 0.08

    reference_boost = min(0.2, 0.03 * len(set(token for token in tokens if token in DOMINANCE_PRONOUN_TOKENS)))
    proper_noun_boost = min(0.15, 0.02 * len(proper_noun_hits))
    dominance_value = base + reference_boost + proper_noun_boost

    dominance_value = max(0.0, min(1.0, round(dominance_value, 4)))
    dominant_agent = speaker.lower() if speaker and speaker != "unknown" else "narrative_guide"
    evidence = {
        "speaker_resolved": speaker != "unknown",
        "pronoun_reference_count": sum(token in DOMINANCE_PRONOUN_TOKENS for token in tokens),
        "proper_noun_hits": len(proper_noun_hits),
    }
    return (
        dominance_value,
        _dominance_contribution_level(dominance_value),
        dominant_agent,
        evidence,
    )


def resolve_speaker(text: str) -> tuple[str, float]:
    match = SPEAKER_PATTERN.search(text)
    if match:
        return match.group(1), 0.9
    return "unknown", 0.2


def tag_segment(text: str) -> dict[str, object]:
    dialogue_blocks = detect_dialogue_blocks(text)
    narration_blocks = detect_narration_blocks(text)
    structure = detect_structure(text)
    speaker, speaker_confidence = resolve_speaker(text) if structure == "dialogue" else ("unknown", 0.2)
    type_confidence = _compute_type_confidence(structure)
    valence, intensity, emotion_confidence, primary_label, secondary_label = compute_valence(text)
    emotion_shift = detect_emotion_shift(text)
    narration_internal_thought_shift = detect_narration_internal_thought_shift(text)
    internal_external_speech_shift = detect_internal_external_speech_shift(text)
    tone_reversal = detect_tone_reversal(text)
    sub_segment_boundaries = _build_sub_segment_boundaries(
        segment_text=text,
        tag_payloads=[
            ("emotion_shift", emotion_shift),
            ("narration_internal_thought_shift", narration_internal_thought_shift),
            ("internal_external_speech_shift", internal_external_speech_shift),
            ("tone_reversal", tone_reversal),
        ],
    )
    tension = compute_tension_contribution(
        text=text,
        valence=valence,
        intensity=intensity,
        structure=structure,
    )
    tension_confidence = _compute_tension_confidence(
        value=tension,
        structure=structure,
        signal_count=sum(1 for token in _tokenize(text) if token in TENSION_SIGNAL_WORDS),
        intensifier_count=sum(1 for token in _tokenize(text) if token in TENSION_INTENSIFIERS),
    )
    dominance_value, dominance_level, dominant_agent, dominance_evidence = compute_dominance_contribution(
        text=text,
        speaker=speaker,
        structure=structure,
    )
    dominance_confidence = _compute_dominance_confidence(
        value=dominance_value,
        speaker=speaker,
        structure=structure,
        evidence=dominance_evidence,
    )
    summary_tag = {
        "tag_type": "segment_summary",
        "dominant_tone": (
            str(tone_reversal["tone"])
            if isinstance(tone_reversal, dict) and bool(tone_reversal.get("has_tone_reversal", False))
            else (
                str(emotion_shift["to"]["label"])
                if isinstance(emotion_shift, dict)
                and bool(emotion_shift.get("has_shift", False)
                and isinstance(emotion_shift.get("to"), dict))
                else primary_label
            )
        ),
        "dominant_state": structure,
        "dominant_agent": dominant_agent,
        "confidence": max(
            float(emotion_confidence),
            float(emotion_shift.get("confidence", 0.0))
            if isinstance(emotion_shift, dict)
            else 0.0,
            float(tone_reversal.get("confidence", 0.0))
            if isinstance(tone_reversal, dict)
            else 0.0,
        ),
    }

    return {
        "type": structure,
        "type_confidence": type_confidence,
        "dialogue_blocks": dialogue_blocks,
        "narration_blocks": narration_blocks,
        "speaker": speaker,
        "speaker_confidence": speaker_confidence,
        "emotion_valence": valence,
        "emotion_intensity": intensity,
        "emotion_primary_label": primary_label,
        "emotion_secondary_label": secondary_label,
        "emotion_confidence": emotion_confidence,
        "emotion_shift": emotion_shift,
        "narration_internal_thought_shift": narration_internal_thought_shift,
        "internal_external_speech_shift": internal_external_speech_shift,
        "tone_reversal": tone_reversal,
        "summary_tag": summary_tag,
        "sub_segment_boundaries": sub_segment_boundaries,
        "tension_contribution": {
            "value": tension,
            "level": _tension_contribution_level(tension),
            "confidence": tension_confidence,
        },
        "dominance_contribution": {
            "value": dominance_value,
            "level": dominance_level,
            "dominant_agent": dominant_agent,
            "evidence": dominance_evidence,
            "confidence": dominance_confidence,
        },
    }
