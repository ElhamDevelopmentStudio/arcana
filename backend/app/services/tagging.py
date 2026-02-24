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

SPEAKER_PATTERN = re.compile(r'"[^"]+"\s+([A-Za-z][A-Za-z0-9_-]*)\s+said\b', re.IGNORECASE)


def detect_structure(text: str) -> str:
    return "dialogue" if '"' in text else "narration"


def compute_valence(text: str) -> tuple[float, float, float]:
    tokens = re.findall(r"[A-Za-z']+", text.lower())
    if not tokens:
        return 0.0, 0.0, 0.4

    positive = sum(1 for token in tokens if token in POSITIVE_WORDS)
    negative = sum(1 for token in tokens if token in NEGATIVE_WORDS)
    raw_valence = (positive - negative) / len(tokens)
    valence = max(-1.0, min(1.0, raw_valence))
    intensity = abs(valence)
    confidence = 0.6 if (positive + negative) > 0 else 0.4
    return round(valence, 4), round(intensity, 4), confidence


def resolve_speaker(text: str) -> tuple[str, float]:
    match = SPEAKER_PATTERN.search(text)
    if match:
        return match.group(1), 0.9
    return "unknown", 0.2


def tag_segment(text: str) -> dict[str, object]:
    structure = detect_structure(text)
    speaker, speaker_confidence = resolve_speaker(text) if structure == "dialogue" else ("unknown", 0.2)
    valence, intensity, emotion_confidence = compute_valence(text)

    return {
        "type": structure,
        "speaker": speaker,
        "speaker_confidence": speaker_confidence,
        "emotion_valence": valence,
        "emotion_intensity": intensity,
        "emotion_confidence": emotion_confidence,
    }
