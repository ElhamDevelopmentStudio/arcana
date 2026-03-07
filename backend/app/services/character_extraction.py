import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Iterable

from app.services.character_merge import normalize_candidate_key


_NAME_TOKEN_RE = re.compile(r"[A-Z][a-z]+(?:[-'][A-Za-z]+)?|[A-Z]{2,4}")
_NAME_PATTERN = rf"(?:{_NAME_TOKEN_RE.pattern})(?:\s+(?:{_NAME_TOKEN_RE.pattern})){{0,2}}"
_NAME_RE = re.compile(rf"{_NAME_PATTERN}")
_SPEECH_VERB_PATTERN = (
    r"(said|asked|replied|whispered|murmured|shouted|yelled|cried|exclaimed|called|answered|continued|announced|"
    r"added|snapped|muttered|spat|remarked|noted|warned|insisted)"
)
_DIALOGUE_TRAILING_DOUBLE_RE = re.compile(
    rf'"[^"\n]{{1,320}}"\s*[—–-]?\s*(?P<name>{_NAME_PATTERN})\s+{_SPEECH_VERB_PATTERN}\b',
    re.IGNORECASE,
)
_DIALOGUE_TRAILING_SINGLE_RE = re.compile(
    rf"'[^'\n]{{1,320}}'\s*[—–-]?\s*(?P<name>{_NAME_PATTERN})\s+{_SPEECH_VERB_PATTERN}\b",
    re.IGNORECASE,
)
_DIALOGUE_LEADING_RE = re.compile(
    rf"\b(?P<name>{_NAME_PATTERN})\s+{_SPEECH_VERB_PATTERN}\s*[,—–-]?\s*[\"'“”]",
    re.IGNORECASE,
)
_NARRATIVE_SPEAKER_RE = re.compile(
    rf"\b(?P<name>{_NAME_PATTERN})\s+{_SPEECH_VERB_PATTERN}\b",
    re.IGNORECASE,
)
_BRACKETED_NAME_RE = re.compile(rf"\[(?P<name>{_NAME_PATTERN})\]")
_LINE_FIELD_RE = re.compile(r"(?m)^\s*(?P<label>[^:\n]{1,80})\s*:\s*(?P<value>[^\n]{0,220})$")
_HEX_ESCAPED_TEXT_RE = re.compile(r"^\\x[0-9a-fA-F]+$")

_PERSON_CONTEXT_TERMS = {
    "he",
    "she",
    "his",
    "her",
    "him",
    "hers",
    "they",
    "them",
    "their",
    "theirs",
    "sir",
    "lady",
    "boy",
    "girl",
    "man",
    "woman",
    "child",
    "friend",
    "captain",
    "officer",
    "mother",
    "father",
    "brother",
    "sister",
    "looked",
    "walked",
    "moved",
    "waited",
    "smiled",
    "sighed",
    "laughed",
    "frowned",
}
_OBJECT_CONTEXT_TERMS = {
    "skill",
    "ability",
    "abilities",
    "artifact",
    "sword",
    "blade",
    "bullet",
    "shard",
    "aspect",
    "attribute",
    "attributes",
    "echo",
    "echoes",
    "memory",
    "memories",
    "flaw",
    "core",
    "soul",
    "rank",
    "description",
    "domain",
    "authority",
    "update",
    "features",
    "list",
    "chapter",
    "section",
    "guild",
    "association",
    "academy",
    "system",
    "status",
}
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
    "chapter",
    "prologue",
    "epilogue",
    "once",
    "after",
    "before",
    "later",
    "however",
    "inside",
    "outside",
    "meanwhile",
    "actually",
    "acting",
    "academy",
    "another",
    "something",
    "someone",
    "anything",
    "anyone",
    "everything",
    "everyone",
    "attention",
    "code",
    "black",
    "aspirant",
    "nightmare",
}
_SYSTEM_TERM_TOKENS = {
    "authority",
    "bullet",
    "shard",
    "bond",
    "control",
    "complete",
    "update",
    "features",
    "training",
    "sneakers",
    "strong",
    "clear",
    "conscience",
    "shadow",
    "slave",
    "fated",
}
_LY_NAME_EXCEPTIONS = {"holly", "kelly", "molly", "billy", "lily", "ally"}
_NON_PERSON_SINGLE_TOKEN_TERMS = {
    "aspect",
    "attribute",
    "attributes",
    "echoes",
    "memories",
    "flaw",
    "rank",
    "name",
    "caster",
    "scholar",
    "hero",
    "memories",
    "echoes",
    "academy",
    "school",
    "city",
    "town",
    "village",
    "house",
    "kingdom",
    "church",
    "guild",
    "association",
    "committee",
    "administration",
    "office",
    "department",
    "chapter",
    "section",
    "actually",
    "acting",
    "however",
    "therefore",
    "instead",
    "meanwhile",
}
_OBJECT_NOUN_SUFFIXES = {
    "shroud",
    "bell",
    "sword",
    "blade",
    "dagger",
    "spear",
    "shield",
    "ring",
    "crown",
    "cloak",
    "robe",
    "amulet",
    "necklace",
    "armor",
    "armour",
    "helm",
    "helmet",
    "staff",
    "orb",
    "stone",
}
_SYSTEM_FIELD_LABELS = {
    "name",
    "true name",
    "rank",
    "aspect",
    "aspect rank",
    "aspect description",
    "attribute",
    "attributes",
    "attribute description",
    "ability",
    "abilities",
    "ability description",
    "aspect ability",
    "aspect abilities",
    "divine aspect",
    "ascended aspect",
    "echoes",
    "memories",
    "flaw",
    "soul core",
    "caster",
    "scholar",
    "hero",
}
_NAME_VALUE_FIELD_LABELS = {"name", "true name", "alias", "aliases"}


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
    verbalized_form: str | None = None
    gender: str = "unknown"
    aliases: list[str] = field(default_factory=list)
    notes: str | None = None
    inferred_gender: str = "unknown"
    inferred_confidence: float = 0.0
    inferred_source_trace: list[CandidateSourceTrace] = field(default_factory=list)


@dataclass
class _CandidateAggregate:
    name: str
    dialogue_hits: int = 0
    narrative_hits: int = 0
    heading_hits: int = 0
    label_hits: int = 0
    context_hits: int = 0
    person_context_hits: int = 0
    object_context_hits: int = 0
    system_term_hits: int = 0
    chapters_seen: set[int] = field(default_factory=set)
    source_traces: list[CandidateSourceTrace] = field(default_factory=list)


def _normalize_candidate_name(raw_name: str) -> str:
    compact = re.sub(r"\s+", " ", raw_name).strip()
    return compact.strip(' "“”\t')


def _normalize_label_key(raw_label: str) -> str:
    return re.sub(r"\s+", " ", raw_label.strip()).lower()


def _is_probable_character_name(candidate_name: str) -> bool:
    if not candidate_name:
        return False

    normalized_name = candidate_name.lower()
    if normalized_name in _KNOWN_BAD_NAMES:
        return False

    parts = candidate_name.split(" ")
    if not (1 <= len(parts) <= 3):
        return False

    for part in parts:
        if not _NAME_TOKEN_RE.fullmatch(part):
            return False
        normalized_part = part.lower()
        if normalized_part.endswith("'s"):
            return False
        if normalized_part in _KNOWN_BAD_NAMES:
            return False
        if len(part) == 1:
            return False

    if len(parts) == 1 and len(parts[0]) > 1 and parts[0].isupper() and len(parts[0]) > 4:
        return False

    if all(part.lower() in _SYSTEM_TERM_TOKENS for part in parts):
        return False

    return True


def _build_trace_excerpt(text: str, start: int, end: int) -> str:
    left = max(0, start - 30)
    right = min(len(text), end + 40)
    excerpt = text[left:right].strip()
    excerpt = re.sub(r"\s+", " ", excerpt)
    if left > 0:
        excerpt = f"...{excerpt}"
    if right < len(text):
        excerpt = f"{excerpt}..."
    return excerpt


def _build_candidate_confidence(aggregate: _CandidateAggregate) -> float:
    evidence_weight = (
        aggregate.dialogue_hits * 1.25
        + aggregate.narrative_hits * 0.95
        + aggregate.heading_hits * 0.9
        + aggregate.label_hits * 0.8
        + aggregate.context_hits * 0.5
    )
    chapter_spread_bonus = max(0, min(len(aggregate.chapters_seen), 6) - 1) * 0.06
    context_bonus = min(aggregate.person_context_hits, 10) * 0.03
    context_penalty = min(aggregate.object_context_hits, 10) * 0.03
    system_penalty = min(aggregate.system_term_hits, 5) * 0.08
    only_context_hits = (
        aggregate.dialogue_hits == 0
        and aggregate.narrative_hits == 0
        and aggregate.heading_hits == 0
        and aggregate.label_hits == 0
    )
    name_lower = aggregate.name.lower()
    suffix_penalty = 0.25 if (name_lower.endswith("ly") and name_lower not in _LY_NAME_EXCEPTIONS) else 0.0
    object_name_penalty = 0.35 if name_lower in _OBJECT_CONTEXT_TERMS else 0.0
    context_only_penalty = 0.04 if only_context_hits else 0.0

    confidence = (
        0.22
        + (evidence_weight * 0.1)
        + chapter_spread_bonus
        + context_bonus
        - context_penalty
        - system_penalty
        - suffix_penalty
        - object_name_penalty
        - context_only_penalty
    )
    if aggregate.narrative_hits >= 1:
        confidence += 0.1
    if only_context_hits and aggregate.person_context_hits > 0 and aggregate.object_context_hits == 0:
        confidence += 0.06
    if aggregate.dialogue_hits >= 2:
        confidence += 0.08
    if aggregate.heading_hits >= 1 and len(aggregate.name.split()) >= 2:
        confidence += 0.05

    if confidence < 0.05:
        return 0.05
    return round(min(0.99, confidence), 4)


def _decode_hex_escaped_chapter_text(text: str) -> str:
    stripped = text.strip()
    if not stripped or not _HEX_ESCAPED_TEXT_RE.fullmatch(stripped):
        return text

    hex_body = stripped[2:]
    if not hex_body or len(hex_body) % 2 != 0:
        return text

    try:
        decoded = bytes.fromhex(hex_body).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return text

    if not re.search(r"[A-Za-z]{3,}", decoded):
        return text
    return decoded


def _find_context_counters(text: str, start: int, end: int) -> tuple[int, int]:
    window_start = max(0, start - 80)
    window_end = min(len(text), end + 80)
    lowered = text[window_start:window_end].lower()
    person_hits = sum(1 for token in _PERSON_CONTEXT_TERMS if re.search(rf"\b{re.escape(token)}\b", lowered))
    object_hits = sum(1 for token in _OBJECT_CONTEXT_TERMS if re.search(rf"\b{re.escape(token)}\b", lowered))
    return person_hits, object_hits


def _add_candidate(
    aggregates: dict[str, _CandidateAggregate],
    raw_name: str,
    chapter_index: int,
    start: int,
    end: int,
    kind: str,
    text: str,
    trace_weight: float,
) -> None:
    candidate_name = _normalize_candidate_name(raw_name)
    if not _is_probable_character_name(candidate_name):
        return

    key = normalize_candidate_key(candidate_name)
    if not key:
        return

    if kind == "proper_name_context":
        lowered = candidate_name.lower()
        if " " not in candidate_name and lowered in _NON_PERSON_SINGLE_TOKEN_TERMS:
            return
        if " " not in candidate_name and lowered.endswith("ly") and lowered not in _LY_NAME_EXCEPTIONS:
            return
    lowered_parts = [part.lower() for part in candidate_name.split()]
    if len(lowered_parts) >= 2 and lowered_parts[-1] in _OBJECT_NOUN_SUFFIXES:
        return

    aggregate = aggregates.setdefault(key, _CandidateAggregate(name=candidate_name))
    aggregate.chapters_seen.add(chapter_index)

    if kind.startswith("dialogue"):
        aggregate.dialogue_hits += 1
    elif kind == "narrative_attribution":
        aggregate.narrative_hits += 1
    elif kind == "bracketed_heading":
        aggregate.heading_hits += 1
    elif kind in {"line_label", "line_value_name"}:
        aggregate.label_hits += 1
    else:
        aggregate.context_hits += 1

    person_hits, object_hits = _find_context_counters(text, start, end)
    if kind == "line_value_name":
        person_hits = max(person_hits, 1)
        object_hits = 0
    aggregate.person_context_hits += person_hits
    aggregate.object_context_hits += object_hits
    if any(token in candidate_name.lower() for token in _SYSTEM_TERM_TOKENS):
        aggregate.system_term_hits += 1

    if kind == "proper_name_context" and person_hits == 0 and object_hits > 1 and len(candidate_name.split()) == 1:
        return

    aggregate.source_traces.append(
        CandidateSourceTrace(
            kind=kind,
            chapter_index=chapter_index,
            span_start=start,
            span_end=end,
            excerpt=_build_trace_excerpt(text, start, end),
            weight=round(max(0.2, min(1.0, trace_weight + (person_hits * 0.05) - (object_hits * 0.04))), 4),
        )
    )


def _dedupe_trace_list(source_traces: list[CandidateSourceTrace], *, max_trace_count: int = 12) -> list[CandidateSourceTrace]:
    deduped: list[CandidateSourceTrace] = []
    seen: set[tuple[object, ...]] = set()

    for trace in source_traces:
        key = (trace.kind, trace.chapter_index, trace.span_start, trace.span_end, trace.excerpt)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(trace)

    deduped.sort(key=lambda trace: (-trace.weight, trace.chapter_index, trace.span_start, trace.span_end))
    return deduped[:max_trace_count]


def _cluster_similar_candidates(candidates: list[CandidateEvidence]) -> list[CandidateEvidence]:
    if not candidates:
        return []

    groups: list[list[CandidateEvidence]] = []
    for candidate in sorted(candidates, key=lambda row: row.name.lower()):
        assigned = False
        candidate_key = normalize_candidate_key(candidate.name)
        candidate_tokens = set(candidate_key.split())
        for group in groups:
            representative = group[0]
            representative_key = normalize_candidate_key(representative.name)
            representative_tokens = set(representative_key.split())
            similarity = SequenceMatcher(None, candidate_key, representative_key).ratio()
            token_overlap = bool(candidate_tokens & representative_tokens)
            if similarity >= 0.93 or (token_overlap and abs(len(candidate_key) - len(representative_key)) <= 2):
                group.append(candidate)
                assigned = True
                break
        if not assigned:
            groups.append([candidate])

    merged_candidates: list[CandidateEvidence] = []
    for group in groups:
        sorted_group = sorted(group, key=lambda row: (-row.confidence, -len(row.name), row.name.lower()))
        canonical = sorted_group[0]
        aliases = [row.name for row in sorted_group[1:]]
        trace_pool: list[CandidateSourceTrace] = []
        for row in sorted_group:
            trace_pool.extend(row.source_trace)
        merged_candidates.append(
            CandidateEvidence(
                name=canonical.name,
                confidence=max(row.confidence for row in sorted_group),
                source_trace=_dedupe_trace_list(trace_pool),
                verbalized_form=canonical.verbalized_form or canonical.name,
                aliases=list(dict.fromkeys(aliases + list(canonical.aliases))),
                gender="unknown",
                notes=canonical.notes,
                inferred_gender=canonical.inferred_gender,
                inferred_confidence=canonical.inferred_confidence,
                inferred_source_trace=canonical.inferred_source_trace,
            )
        )

    return merged_candidates


def extract_character_candidates_from_texts(
    chapter_texts: Iterable[str],
    *,
    known_names: set[str] | None = None,
    min_confidence: float = 0.25,
    max_candidates: int = 250,
) -> list[CandidateEvidence]:
    known = {normalize_candidate_key(name) for name in (known_names or set()) if str(name).strip()}
    aggregates: dict[str, _CandidateAggregate] = {}

    for chapter_index, text in enumerate(chapter_texts, start=1):
        if not isinstance(text, str):
            continue
        resolved_text = _decode_hex_escaped_chapter_text(text)

        for matcher in (_DIALOGUE_TRAILING_DOUBLE_RE, _DIALOGUE_TRAILING_SINGLE_RE, _DIALOGUE_LEADING_RE):
            for match in matcher.finditer(resolved_text):
                _add_candidate(
                    aggregates=aggregates,
                    raw_name=match.group("name"),
                    chapter_index=chapter_index,
                    start=match.start("name"),
                    end=match.end("name"),
                    kind="dialogue_attribution",
                    text=resolved_text,
                    trace_weight=1.0,
                )

        for match in _NARRATIVE_SPEAKER_RE.finditer(resolved_text):
            _add_candidate(
                aggregates=aggregates,
                raw_name=match.group("name"),
                chapter_index=chapter_index,
                start=match.start("name"),
                end=match.end("name"),
                kind="narrative_attribution",
                text=resolved_text,
                trace_weight=0.78,
            )

        for match in _BRACKETED_NAME_RE.finditer(resolved_text):
            _add_candidate(
                aggregates=aggregates,
                raw_name=match.group("name"),
                chapter_index=chapter_index,
                start=match.start("name"),
                end=match.end("name"),
                kind="bracketed_heading",
                text=resolved_text,
                trace_weight=0.72,
            )

        for match in _LINE_FIELD_RE.finditer(resolved_text):
            label_raw = _normalize_candidate_name(match.group("label"))
            if not label_raw:
                continue
            label_key = _normalize_label_key(label_raw)
            value_text = match.group("value")

            if label_key in _NAME_VALUE_FIELD_LABELS:
                for value_match in _NAME_RE.finditer(value_text):
                    _add_candidate(
                        aggregates=aggregates,
                        raw_name=value_match.group(0),
                        chapter_index=chapter_index,
                        start=match.start("value") + value_match.start(0),
                        end=match.start("value") + value_match.end(0),
                        kind="line_value_name",
                        text=resolved_text,
                        trace_weight=0.86,
                    )
                continue

            if label_key in _SYSTEM_FIELD_LABELS:
                continue

            _add_candidate(
                aggregates=aggregates,
                raw_name=label_raw,
                chapter_index=chapter_index,
                start=match.start("label"),
                end=match.end("label"),
                kind="line_label",
                text=resolved_text,
                trace_weight=0.68,
            )

        for match in _NAME_RE.finditer(resolved_text):
            raw_name = match.group(0)
            normalized_name = _normalize_candidate_name(raw_name)
            if not _is_probable_character_name(normalized_name):
                continue
            _add_candidate(
                aggregates=aggregates,
                raw_name=normalized_name,
                chapter_index=chapter_index,
                start=match.start(0),
                end=match.end(0),
                kind="proper_name_context",
                text=resolved_text,
                trace_weight=0.42,
            )

    if not aggregates:
        return []

    results: list[CandidateEvidence] = []
    for key, aggregate in aggregates.items():
        if key in known:
            continue

        confidence = _build_candidate_confidence(aggregate)
        if confidence < min_confidence:
            continue
        trace_list = _dedupe_trace_list(aggregate.source_traces)
        if not trace_list:
            continue
        results.append(
            CandidateEvidence(
                name=aggregate.name,
                confidence=confidence,
                source_trace=trace_list,
                verbalized_form=aggregate.name,
                gender="unknown",
                aliases=[],
                notes=None,
                inferred_gender="unknown",
                inferred_confidence=0.0,
                inferred_source_trace=[],
            )
        )

    clustered = _cluster_similar_candidates(results)
    clustered.sort(key=lambda candidate: (-candidate.confidence, candidate.name.lower()))
    return clustered[:max_candidates]
    "name",
    "true name",
    "rank",
    "aspect",
    "attributes",
    "echoes",
    "memories",
    "flaw",
    "soul core",
    "aspect rank",
    "aspect description",
    "attribute description",
    "ability description",
    "aspect ability",
    "aspect abilities",
    "ascended aspect",
    "divine aspect",
    "caster",
    "scholar",
    "hero",
    "aspect",
    "attribute",
    "attributes",
    "echo",
    "echoes",
    "memory",
    "memories",
    "flaw",
    "core",
    "rank",
    "ability",
    "abilities",
    "description",
    "ascended",
    "divine",
