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
    valence, intensity, emotion_confidence, primary_label, secondary_label = compute_valence(text)
    tension = compute_tension_contribution(
        text=text,
        valence=valence,
        intensity=intensity,
        structure=structure,
    )

    return {
        "type": structure,
        "dialogue_blocks": dialogue_blocks,
        "narration_blocks": narration_blocks,
        "speaker": speaker,
        "speaker_confidence": speaker_confidence,
        "emotion_valence": valence,
        "emotion_intensity": intensity,
        "emotion_primary_label": primary_label,
        "emotion_secondary_label": secondary_label,
        "emotion_confidence": emotion_confidence,
        "tension_contribution": {
            "value": tension,
            "level": _tension_contribution_level(tension),
        },
    }
