from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable


_MALE_PRONOUNS = frozenset({"he", "him", "his", "himself", "sir", "mr", "mister"})
_FEMALE_PRONOUNS = frozenset({"she", "her", "hers", "herself", "miss", "ms", "mrs", "madam"})
_NEUTRAL_PRONOUNS = frozenset({"they", "them", "their", "theirs", "themself"})

_MALE_TITLE_PREFIXES = ("mr", "mister", "sir")
_FEMALE_TITLE_PREFIXES = ("mrs", "ms", "miss", "madam")

_MIN_EVIDENCE_WEIGHT = 0.5
_MIN_CONTRAST_MARGIN = 0.3
_TITLE_SIGNAL_WEIGHT = 1.05
_PRONOUN_SIGNAL_WEIGHT = 0.55
_EXCERPT_WINDOW = 45


@dataclass(frozen=True)
class GenderInferenceEvidence:
    kind: str
    chapter_index: int
    span_start: int
    span_end: int
    excerpt: str
    weight: float

    def to_payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "chapter_index": self.chapter_index,
            "span_start": self.span_start,
            "span_end": self.span_end,
            "excerpt": self.excerpt,
            "weight": min(1.0, self.weight),
        }


@dataclass(frozen=True)
class GenderInferenceResult:
    name: str
    inferred_gender: str
    confidence: float
    evidence: tuple[GenderInferenceEvidence, ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "inferred_gender": self.inferred_gender,
            "confidence": self.confidence,
            "evidence": [entry.to_payload() for entry in self.evidence],
        }


def _normalize_name(raw_name: str) -> str:
    return re.sub(r"\s+", " ", raw_name.strip()).strip()


def _build_name_pattern(name: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![\w']){re.escape(name)}(?![\w'])", re.IGNORECASE)


def _build_sentence_bounds(text: str, target_index: int) -> tuple[int, int]:
    delimiters = ".!?\n"
    before_candidates = [text.rfind(delimiter, 0, target_index) for delimiter in delimiters]
    sentence_start = max(before_candidates) + 1
    after_candidates = [text.find(delimiter, target_index) for delimiter in delimiters]
    after_candidates = [candidate for candidate in after_candidates if candidate != -1]
    sentence_end = min(after_candidates) if after_candidates else len(text)
    return sentence_start, sentence_end


def _make_excerpt(text: str, span_start: int, span_end: int) -> str:
    left = max(0, span_start - _EXCERPT_WINDOW)
    right = min(len(text), span_end + _EXCERPT_WINDOW)
    excerpt = re.sub(r"\s+", " ", text[left:right]).strip()
    if left > 0:
        excerpt = f"...{excerpt}"
    if right < len(text):
        excerpt = f"{excerpt}..."
    return excerpt


def _count_gender_pronouns(text: str) -> dict[str, int]:
    tokens = re.findall(r"\b[’'\w]+\b", text.lower())
    counts = {"male": 0, "female": 0, "neutral": 0}
    for token in tokens:
        if token in _MALE_PRONOUNS:
            counts["male"] += 1
        elif token in _FEMALE_PRONOUNS:
            counts["female"] += 1
        elif token in _NEUTRAL_PRONOUNS:
            counts["neutral"] += 1
    return counts


def infer_character_genders(
    character_names: Iterable[str],
    chapter_texts: Iterable[str],
) -> list[dict[str, Any]]:
    canonical_names = [_normalize_name(name) for name in character_names]
    names = [name for name in canonical_names if name]
    if not names:
        return []

    chapter_rows = [(index, (text or "")) for index, text in enumerate(chapter_texts, start=1)]
    results: list[GenderInferenceResult] = []

    for name in names:
        title_pattern = _build_name_pattern(name)
        evidence: list[GenderInferenceEvidence] = []
        scores = {"male": 0.0, "female": 0.0, "neutral": 0.0}

        for chapter_index, chapter_text in chapter_rows:
            if not chapter_text:
                continue
            for prefix in _MALE_TITLE_PREFIXES:
                title_regex = re.compile(
                    rf"\b{prefix}\.?\s+{re.escape(name)}\b",
                    re.IGNORECASE,
                )
                for title_match in title_regex.finditer(chapter_text):
                    scores["male"] += _TITLE_SIGNAL_WEIGHT
                    evidence.append(
                        GenderInferenceEvidence(
                            kind="gender_inference_title",
                            chapter_index=chapter_index,
                            span_start=title_match.start(),
                            span_end=title_match.end(),
                            excerpt=_make_excerpt(chapter_text, title_match.start(), title_match.end()),
                            weight=_TITLE_SIGNAL_WEIGHT,
                        ),
                    )

            for prefix in _FEMALE_TITLE_PREFIXES:
                title_regex = re.compile(
                    rf"\b{prefix}\.?\s+{re.escape(name)}\b",
                    re.IGNORECASE,
                )
                for title_match in title_regex.finditer(chapter_text):
                    scores["female"] += _TITLE_SIGNAL_WEIGHT
                    evidence.append(
                        GenderInferenceEvidence(
                            kind="gender_inference_title",
                            chapter_index=chapter_index,
                            span_start=title_match.start(),
                            span_end=title_match.end(),
                            excerpt=_make_excerpt(chapter_text, title_match.start(), title_match.end()),
                            weight=_TITLE_SIGNAL_WEIGHT,
                        ),
                    )

            for name_match in title_pattern.finditer(chapter_text):
                sentence_start, sentence_end = _build_sentence_bounds(chapter_text, name_match.start())
                sentence = chapter_text[sentence_start:sentence_end]
                pronoun_counts = _count_gender_pronouns(sentence)
                for gender_key, count in pronoun_counts.items():
                    if count <= 0:
                        continue
                    if gender_key == "male":
                        scores[gender_key] += count * _PRONOUN_SIGNAL_WEIGHT
                    elif gender_key == "female":
                        scores[gender_key] += count * _PRONOUN_SIGNAL_WEIGHT
                    elif gender_key == "neutral":
                        scores[gender_key] += count * (_PRONOUN_SIGNAL_WEIGHT - 0.1)

                    evidence.append(
                        GenderInferenceEvidence(
                            kind="gender_inference_sentence_pronouns",
                            chapter_index=chapter_index,
                            span_start=sentence_start,
                            span_end=sentence_end,
                            excerpt=_make_excerpt(sentence, 0, len(sentence)),
                            weight=count * _PRONOUN_SIGNAL_WEIGHT,
                        )
                    )

        total_score = scores["male"] + scores["female"] + scores["neutral"]
        inferred_gender = "unknown"
        confidence = 0.0
        if total_score >= _MIN_EVIDENCE_WEIGHT:
            sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
            dominant_gender, dominant_score = sorted_scores[0]
            _, second_score = sorted_scores[1]
            if dominant_gender and dominant_score - second_score >= _MIN_CONTRAST_MARGIN:
                inferred_gender = dominant_gender
                confidence = min(
                    1.0,
                    0.45 + (dominant_score / total_score) * 0.5 + (dominant_score - second_score) / max(total_score, 1) * 0.35,
                )

        results.append(
            GenderInferenceResult(
                name=name,
                inferred_gender=inferred_gender,
                confidence=round(confidence, 4),
                evidence=tuple(evidence),
            )
        )

    return [
        result.to_payload() | {"source": "inferred"}
        for result in sorted(results, key=lambda payload: payload.name.lower())
    ]
