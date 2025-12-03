from __future__ import annotations

import re
from dataclasses import dataclass

from app.models import Character, Chapter
from app.services.character_merge import normalize_candidate_key


@dataclass(frozen=True)
class ChapterMentionCounter:
    chapter_index: int
    mention_counts: dict[str, int]

    def to_dict(self) -> dict[str, object]:
        return {
            "chapter_index": self.chapter_index,
            "mention_counts": self.mention_counts,
        }


def build_character_first_appearance_chapter_indices(
    chapter_mention_counters: list[ChapterMentionCounter],
) -> dict[str, int | None]:
    if not chapter_mention_counters:
        return {}

    canonical_names = sorted(
        {name for counter in chapter_mention_counters for name in counter.mention_counts}
    )
    first_appearance: dict[str, int | None] = {name: None for name in canonical_names}

    for counter in sorted(chapter_mention_counters, key=lambda row: row.chapter_index):
        for canonical_name, mentions in counter.mention_counts.items():
            if mentions > 0 and first_appearance.get(canonical_name) is None:
                first_appearance[canonical_name] = counter.chapter_index

    return first_appearance


def _normalize_counting_text(raw_text: str) -> str:
    normalized = normalize_candidate_key(raw_text)
    return re.sub(r"\s+", " ", normalized).strip()


def _build_unique_alias_candidates(row: Character) -> list[str]:
    aliases = list(dict.fromkeys([alias.strip() for alias in (row.aliases or []) if str(alias).strip()]))
    aliases.append(row.name.strip())
    return [normalize_candidate_key(alias) for alias in aliases if normalize_candidate_key(alias)]


def _build_alias_to_canonical_terms(chars: list[Character]) -> dict[str, set[str]]:
    alias_map: dict[str, set[str]] = {}
    for row in chars:
        canonical_name = str(row.name).strip()
        if not canonical_name:
            continue
        for alias_candidate in _build_unique_alias_candidates(row):
            alias_map.setdefault(alias_candidate, set()).add(canonical_name)

    return alias_map


def _is_unambiguous_alias(alias: str, alias_to_canonical: dict[str, set[str]]) -> bool:
    return len(alias_to_canonical.get(alias, set())) <= 1


def _build_term_pattern(term: str) -> re.Pattern[str]:
    escaped = re.escape(term)
    return re.compile(rf"(?<!\w){escaped}(?!\w)")


def build_character_mentions_by_chapter(
    chapters: list[Chapter],
    characters: list[Character],
) -> list[ChapterMentionCounter]:
    if not chapters or not characters:
        return []

    alias_to_canonical = _build_alias_to_canonical_terms(characters)
    canonical_to_terms: dict[str, list[str]] = {}

    for row in characters:
        canonical_name = str(row.name).strip()
        if not canonical_name:
            continue

        normalized_terms: list[str] = []
        for alias in _build_unique_alias_candidates(row):
            if not _is_unambiguous_alias(alias, alias_to_canonical):
                continue
            normalized_terms.append(alias)

        if not normalized_terms:
            continue
        canonical_to_terms[canonical_name] = sorted(set(normalized_terms))

    if not canonical_to_terms:
        return []

    canonical_to_patterns = {
        canonical: [_build_term_pattern(term) for term in terms]
        for canonical, terms in canonical_to_terms.items()
    }

    payload: list[ChapterMentionCounter] = []
    for chapter in sorted(chapters, key=lambda row: row.chapter_index):
        if not chapter.normalized_text:
            payload.append(ChapterMentionCounter(chapter_index=chapter.chapter_index, mention_counts={name: 0 for name in canonical_to_patterns}))
            continue

        normalized_text = _normalize_counting_text(chapter.normalized_text)
        mention_counts: dict[str, int] = {}
        for canonical_name, patterns in canonical_to_patterns.items():
            mention_counts[canonical_name] = sum(len(pattern.findall(normalized_text)) for pattern in patterns)
        payload.append(
            ChapterMentionCounter(
                chapter_index=chapter.chapter_index,
                mention_counts=mention_counts,
            )
        )

    return payload
