import re
from dataclasses import dataclass, field
from typing import Iterable


_NAME_TOKEN_RE = re.compile(r"[A-Z][a-z]+(?:[-'][A-Za-z]+)?")
_NAME_RE = re.compile(rf"{_NAME_TOKEN_RE.pattern}(?:\s+{_NAME_TOKEN_RE.pattern})?")
_SPEECH_VERB_PATTERN = (
    r"(said|asked|replied|whispered|murmured|shouted|yelled|cried|exclaimed|called|answered|continued|announced)"
)
_DIALOGUE_TRAILING_RE = re.compile(
    rf'"[^"]+?"\s*[—–-]?\s*(?P<name>{_NAME_RE.pattern})\s+{_SPEECH_VERB_PATTERN}\b',
    re.IGNORECASE,
)
_NARRATIVE_SPEAKER_RE = re.compile(
    rf"\b(?P<name>{_NAME_RE.pattern})\s+{_SPEECH_VERB_PATTERN}\b",
    re.IGNORECASE,
)

_KNOWN_BAD_NAMES = {
    "i",
    "he",
    "him",
    "his",
    "she",
    "her",
    "they",
    "them",
    "it",
    "we",
    "us",
    "you",
    "your",
    "the",
    "a",
    "an",
    "this",
    "that",
    "these",
    "those",
    "there",
    "here",
    "and",
    "or",
    "if",
    "as",
    "for",
    "to",
    "in",
    "on",
    "at",
    "by",
}


@dataclass(frozen=True)
class CandidateSourceTrace:
    kind: str
    chapter_index: int
    span_start: int
    span_end: int
    excerpt: str
    weight: float


@dataclass(frozen=True)
class CandidateEvidence:
    name: str
    confidence: float
    source_trace: list[CandidateSourceTrace]


@dataclass
class _CandidateAggregate:
    name: str
    high: int = 0
    medium: int = 0
    source_traces: list[CandidateSourceTrace] = field(default_factory=list)


def _normalize_candidate_name(raw_name: str) -> str:
    compact = re.sub(r"\s+", " ", raw_name).strip()
    return compact.strip(' "“”\t')


def _is_probable_character_name(candidate_name: str) -> bool:
    if not candidate_name:
        return False
    if candidate_name.lower() in _KNOWN_BAD_NAMES:
        return False

    parts = candidate_name.split(" ")
    if not (1 <= len(parts) <= 2):
        return False

    for part in parts:
        if not _NAME_TOKEN_RE.fullmatch(part):
            return False
        if part.lower() in _KNOWN_BAD_NAMES:
            return False

    return True


def _build_trace_excerpt(text: str, start: int, end: int) -> str:
    left = max(0, start - 20)
    right = min(len(text), end + 20)
    excerpt = text[left:right].strip()
    excerpt = re.sub(r"\s+", " ", excerpt)
    if left > 0:
        excerpt = f"...{excerpt}"
    if right < len(text):
        excerpt = f"{excerpt}..."
    return excerpt


def _build_candidate_confidence(high_count: int, medium_count: int) -> float:
    evidence_weight = high_count + (medium_count * 0.6)
    confidence = 0.35 + (evidence_weight * 0.2)
    if confidence < 0.35:
        return 0.35
    return round(min(0.99, confidence), 4)


def _add_candidate(
    aggregates: dict[str, _CandidateAggregate],
    raw_name: str,
    chapter_index: int,
    start: int,
    end: int,
    kind: str,
    text: str,
    high: bool,
) -> None:
    candidate_name = _normalize_candidate_name(raw_name)
    if not _is_probable_character_name(candidate_name):
        return

    key = candidate_name.lower()
    aggregate = aggregates.setdefault(key, _CandidateAggregate(name=candidate_name))
    if high:
        aggregate.high += 1
    else:
        aggregate.medium += 1
    aggregate.source_traces.append(
        CandidateSourceTrace(
            kind=kind,
            chapter_index=chapter_index,
            span_start=start,
            span_end=end,
            excerpt=_build_trace_excerpt(text, start, end),
            weight=1.0 if high else 0.6,
        )
    )


def extract_character_candidates_from_texts(
    chapter_texts: Iterable[str],
    *,
    known_names: set[str] | None = None,
) -> list[CandidateEvidence]:
    known = {name.strip().lower() for name in (known_names or set())}
    aggregates: dict[str, _CandidateAggregate] = {}

    for chapter_index, text in enumerate(chapter_texts, start=1):
        if not isinstance(text, str):
            continue

        for match in _DIALOGUE_TRAILING_RE.finditer(text):
            _add_candidate(
                aggregates=aggregates,
                raw_name=match.group("name"),
                chapter_index=chapter_index,
                start=match.start("name"),
                end=match.end("name"),
                kind="dialogue_attribution",
                text=text,
                high=True,
            )
        for match in _NARRATIVE_SPEAKER_RE.finditer(text):
            _add_candidate(
                aggregates=aggregates,
                raw_name=match.group("name"),
                chapter_index=chapter_index,
                start=match.start("name"),
                end=match.end("name"),
                kind="narrative_attribution",
                text=text,
                high=False,
            )

    if not aggregates:
        return []

    results: list[CandidateEvidence] = []
    for key, aggregate in aggregates.items():
        if key in known:
            continue
        confidence = _build_candidate_confidence(aggregate.high, aggregate.medium)
        trace_list = sorted(
            aggregate.source_traces, key=lambda trace: (trace.chapter_index, trace.span_start, trace.span_end)
        )
        results.append(
            CandidateEvidence(
                name=aggregate.name,
                confidence=confidence,
                source_trace=trace_list,
            )
        )

    return sorted(
        results,
        key=lambda candidate: (-candidate.confidence, candidate.name.lower()),
    )
