from __future__ import annotations

from difflib import SequenceMatcher
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any


_TRACE_KEYS = ("kind", "chapter_index", "span_start", "span_end", "excerpt", "weight")
_WS_RE = re.compile(r"\s+")

_SOURCE_PRECEDENCE = {
    "manual": 0,
    "user_import": 0,
    "user_uploaded": 0,
    "user": 0,
    "auto": 1,
    "scrape": 2,
}


def normalize_candidate_key(raw_name: str) -> str:
    normalized = unicodedata.normalize("NFKC", raw_name.strip())
    normalized = _WS_RE.sub(" ", normalized)
    return normalized.strip(' "“”\t').casefold()


def normalize_source_name(raw_source: str) -> str:
    source = str(raw_source or "").strip().lower()
    if source in {"manual", "user", "user_upload", "user_uploaded"}:
        return "user_import"
    return source or "user_import"


def _best_canonical_match_key(
    normalized_name: str,
    canonical_names: dict[str, str],
) -> tuple[str, float] | None:
    if not canonical_names:
        return None

    best_match: tuple[str, float] | None = None

    for canonical_key, canonical_name in canonical_names.items():
        if normalized_name == canonical_key:
            continue

        score = SequenceMatcher(None, normalized_name, canonical_key).ratio()
        if score < 0.82 and normalized_name not in canonical_key and canonical_key not in normalized_name:
            continue

        if (
            normalized_name.startswith(canonical_key)
            or canonical_key.startswith(normalized_name)
            or set(normalized_name.split()) & set(canonical_key.split())
            or abs(len(normalized_name) - len(canonical_key)) <= 2
        ):
            if best_match is None or score > best_match[1]:
                best_match = (canonical_name, score)

    return best_match


def build_canonical_name_merge_suggestions(
    candidate_payloads: list[dict[str, Any]],
    canonical_names: list[str] | set[str] | None = None,
    threshold: float = 0.86,
) -> list[dict[str, Any]]:
    if not candidate_payloads:
        return []

    normalized_canonical_map: dict[str, str] = {}

    if canonical_names is None:
        canonical_names = set()

    for canonical_name in canonical_names:
        if not isinstance(canonical_name, str):
            continue
        normalized_key = normalize_candidate_key(canonical_name)
        if not normalized_key:
            continue
        normalized_canonical_map[normalized_key] = canonical_name.strip()

    if not normalized_canonical_map:
        return []

    canonical_key_set = set(normalized_canonical_map)
    suggestions: list[dict[str, Any]] = []

    for payload in candidate_payloads:
        candidate_name = str(payload.get("name") or "").strip()
        if not candidate_name:
            continue

        candidate_key = normalize_candidate_key(candidate_name)
        if not candidate_key or candidate_key in canonical_key_set:
            continue

        best_match = _best_canonical_match_key(candidate_key, normalized_canonical_map)
        if best_match is None:
            continue
        canonical_name, score = best_match
        if score < threshold:
            continue

        source = str(payload.get("source") or "auto").strip() or "auto"
        suggestions.append(
            {
                "canonical_name": canonical_name,
                "alias_name": candidate_name,
                "score": round(score, 4),
                "candidate_source": source,
                "canonical_source": "user_import",
                "reason": "name_similarity",
            }
        )

    suggestions.sort(key=lambda suggestion: suggestion["score"], reverse=True)
    return suggestions


def detect_alias_conflicts(canonical_rows: list[dict[str, Any]]) -> list[dict[str, object]]:
    alias_to_canonicals: dict[str, set[str]] = {}
    alias_display: dict[str, str] = {}

    for row in canonical_rows:
        canonical_name = str(row.get("name") or "").strip()
        if not canonical_name:
            continue

        aliases = _normalize_aliases(row.get("aliases"))
        for alias in aliases:
            alias_normalized = normalize_candidate_key(alias)
            if not alias_normalized:
                continue
            alias_to_canonicals.setdefault(alias_normalized, set()).add(canonical_name)
            alias_display.setdefault(alias_normalized, alias.strip())

    conflicts: list[dict[str, object]] = []
    for normalized_alias in sorted(alias_to_canonicals):
        canonical_names = sorted(alias_to_canonicals[normalized_alias])
        if len(canonical_names) > 1:
            conflicts.append(
                {
                    "alias": alias_display.get(normalized_alias, normalized_alias),
                    "canonical_names": canonical_names,
                }
            )

    return conflicts


def build_ambiguous_alias_collision_warnings(
    canonical_rows: list[dict[str, Any]],
    source: str = "character",
) -> list[dict[str, object]]:
    warnings: list[dict[str, object]] = []
    for conflict in detect_alias_conflicts(canonical_rows):
        alias = str(conflict.get("alias") or "").strip()
        canonical_names = conflict.get("canonical_names")
        if not alias or not isinstance(canonical_names, list):
            continue

        warnings.append(
            {
                "type": "ambiguous_alias_collision",
                "level": "warning",
                "source": source,
                "alias": alias,
                "canonical_names": canonical_names,
                "message": f"Alias '{alias}' is used by multiple canonical names: {', '.join(canonical_names)}.",
            }
        )
    return warnings


def build_duplicate_canonical_candidate_warnings(
    candidate_payloads: list[dict[str, Any]],
    source: str = "character",
) -> list[dict[str, object]]:
    duplicates: dict[str, list[str]] = {}

    for row in candidate_payloads:
        candidate_name = str(row.get("name") or "").strip()
        if not candidate_name:
            continue

        normalized_name = normalize_candidate_key(candidate_name)
        if not normalized_name:
            continue

        duplicates.setdefault(normalized_name, []).append(candidate_name)

    warnings: list[dict[str, object]] = []
    for normalized_name, names in duplicates.items():
        if len(names) <= 1:
            continue

        canonical_names = list(dict.fromkeys(names))
        canonical_label = canonical_names[0]
        warnings.append(
            {
                "type": "duplicate_canonical_candidates",
                "level": "warning",
                "source": source,
                "alias": canonical_label,
                "canonical_names": canonical_names,
                "candidate_name": canonical_label,
                "message": (
                    f"Duplicate canonical candidate '{canonical_label}' appeared "
                    f"{len(names)} times from source '{source}'."
                ),
            }
        )

    return warnings


def build_low_confidence_extracted_character_warnings(
    candidate_payloads: list[dict[str, Any]],
    source: str = "character",
    confidence_threshold: float = 0.7,
) -> list[dict[str, object]]:
    if not candidate_payloads:
        return []

    warnings: list[dict[str, object]] = []
    for payload in candidate_payloads:
        candidate_name = str(payload.get("name") or "").strip()
        if not candidate_name:
            continue

        try:
            confidence = float(payload.get("confidence"))
        except (TypeError, ValueError):
            continue

        if confidence >= confidence_threshold:
            continue

        confidence_rounded = round(confidence, 4)
        warnings.append(
            {
                "type": "low_confidence_character_candidate",
                "level": "warning",
                "source": source,
                "alias": candidate_name,
                "canonical_names": [],
                "candidate_name": candidate_name,
                "confidence": confidence_rounded,
                "threshold": round(confidence_threshold, 4),
                "message": (
                    f"Low-confidence extracted character '{candidate_name}' (confidence "
                    f"{round(confidence * 100, 2)}%) from source '{source}'."
                ),
            }
        )

    return warnings


def resolve_alias_to_canonical_name(
    alias_text: str,
    canonical_rows: list[dict[str, Any]],
) -> tuple[str | None, str]:
    normalized_alias = normalize_candidate_key(alias_text)
    if not normalized_alias:
        return None, "none"

    canonical_matches: dict[str, str] = {}
    for row in canonical_rows:
        canonical_name = str(row.get("name") or "").strip()
        if not canonical_name:
            continue

        if normalize_candidate_key(canonical_name) == normalized_alias:
            canonical_matches[canonical_name] = "canonical"

    for row in canonical_rows:
        canonical_name = str(row.get("name") or "").strip()
        if not canonical_name:
            continue

        aliases = _normalize_aliases(row.get("aliases"))
        for alias in aliases:
            alias_normalized = normalize_candidate_key(alias)
            if not alias_normalized:
                continue
            if alias_normalized == normalized_alias:
                canonical_matches.setdefault(canonical_name, "alias")

    if len(canonical_matches) == 0:
        return None, "none"
    if len(canonical_matches) > 1:
        return None, "conflict"

    canonical_name, match_source = next(iter(canonical_matches.items()))
    return canonical_name, match_source


def _coerce_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 1.0
    if confidence < 0.0:
        return 0.0
    if confidence > 1.0:
        return 1.0
    return round(confidence, 4)


def _coerce_trace(trace: Any) -> dict[str, Any] | None:
    if not isinstance(trace, dict):
        return None
    return {
        "kind": str(trace.get("kind") or ""),
        "chapter_index": int(trace.get("chapter_index", 0) or 0),
        "span_start": int(trace.get("span_start", 0) or 0),
        "span_end": int(trace.get("span_end", 0) or 0),
        "excerpt": str(trace.get("excerpt") or ""),
        "weight": float(trace.get("weight", 0.0) or 0.0),
    }


def _dedupe_and_sort_traces(traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique_traces: list[tuple[str, ...] | tuple[Any, ...]] = []
    deduped: list[dict[str, Any]] = []

    for trace in traces:
        key = tuple(trace.get(field_name) for field_name in _TRACE_KEYS)
        if key in unique_traces:
            continue
        unique_traces.append(key)
        deduped.append(trace)

    deduped.sort(key=lambda value: (value["kind"], value["chapter_index"], value["span_start"], value["span_end"]))
    return deduped


def _source_priority(source: str) -> int:
    return _SOURCE_PRECEDENCE.get(source.strip().lower(), 3)


def _merge_source_label(sources: set[str]) -> str:
    if not sources:
        return "user_import"
    if len(sources) == 1:
        return next(iter(sources))
    return "merged:" + "|".join(sorted(sources))


def _normalize_aliases(aliases: Any) -> list[str]:
    if not aliases:
        return []

    normalized = []
    for alias in aliases:
        cleaned = str(alias).strip()
        if cleaned:
            normalized.append(cleaned)

    return list(dict.fromkeys(normalized))


def _has_manual_source(source_set: set[str]) -> bool:
    return "user_import" in source_set


@dataclass
class _CandidateAccumulator:
    name: str
    verbalized_form: str
    gender: str
    aliases: list[str]
    notes: str | None
    confidence: float
    source: str
    source_set: set[str] = field(default_factory=set)
    source_trace: list[dict[str, Any]] = field(default_factory=list)
    canonical_key: str = ""

    def add_aliases(self, aliases: list[str]) -> None:
        if not aliases:
            return
        self.aliases = list(dict.fromkeys(self.aliases + aliases))

    def add_trace(self, traces: list[dict[str, Any]]) -> None:
        self.source_trace.extend([trace for trace in traces if trace])


def _candidate_signature(candidate: dict[str, Any]) -> _CandidateAccumulator:
    name = str(candidate.get("name") or "").strip()
    verbalized_form = str(candidate.get("verbalized_form") or name).strip() or name
    gender = str(candidate.get("gender") or "unknown").strip().lower() or "unknown"
    aliases = _normalize_aliases(candidate.get("aliases"))
    notes = candidate.get("notes")
    if isinstance(notes, str):
        notes = notes.strip() or None

    source = normalize_source_name(candidate.get("source"))
    traces: list[dict[str, Any]] = []
    for raw_trace in candidate.get("source_trace") or []:
        trace = _coerce_trace(raw_trace)
        if trace:
            traces.append(trace)

    return _CandidateAccumulator(
        name=name,
        verbalized_form=verbalized_form,
        gender=gender,
        aliases=aliases,
        notes=notes,
        confidence=_coerce_confidence(candidate.get("confidence")),
        source=source,
        source_set={source},
        source_trace=traces,
        canonical_key=normalize_candidate_key(name),
    )


def merge_character_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not candidates:
        return []

    buckets: dict[str, _CandidateAccumulator] = {}

    for candidate in candidates:
        normalized = normalize_candidate_key(str(candidate.get("name") or ""))
        if not normalized:
            continue

        candidate_payload = _candidate_signature(candidate)
        existing = buckets.get(normalized)
        if existing is None:
            buckets[normalized] = candidate_payload
            continue

        if _source_priority(candidate_payload.source) < _source_priority(existing.source):
            existing.name = candidate_payload.name
            existing.verbalized_form = candidate_payload.verbalized_form
            existing.gender = candidate_payload.gender
            existing.notes = candidate_payload.notes or existing.notes
            existing.confidence = candidate_payload.confidence
            existing.source = candidate_payload.source
        elif (
            not _has_manual_source(existing.source_set)
            and existing.gender == "unknown"
            and candidate_payload.gender != "unknown"
        ):
            existing.gender = candidate_payload.gender
        if existing.notes is None and candidate_payload.notes:
            existing.notes = candidate_payload.notes

        if candidate_payload.confidence > existing.confidence:
            existing.confidence = candidate_payload.confidence

        existing.add_aliases(candidate_payload.aliases)
        existing.add_trace(candidate_payload.source_trace)
        existing.source_set.add(candidate_payload.source)

    merged: list[dict[str, Any]] = []
    for bucket in buckets.values():
        merged.append(
            {
                "name": bucket.name,
                "verbalized_form": bucket.verbalized_form,
                "gender": bucket.gender,
                "aliases": bucket.aliases,
                "notes": bucket.notes,
                "source": _merge_source_label(bucket.source_set),
                "confidence": round(bucket.confidence, 4),
                "source_trace": _dedupe_and_sort_traces(bucket.source_trace),
            }
        )

    merged.sort(key=lambda item: item["name"].lower())
    return merged
