from collections.abc import Mapping
from collections.abc import Sequence

import re


def _build_replace_pattern(names: Sequence[str], match_whole_words: bool, case_sensitive: bool) -> re.Pattern[str]:
    if not names:
        raise ValueError("No replacement terms provided.")

    escaped_terms = "|".join(re.escape(name) for name in names)
    if match_whole_words:
        pattern = r"\b(" + escaped_terms + r")\b"
    else:
        pattern = "(" + escaped_terms + ")"

    flags = 0 if case_sensitive else re.IGNORECASE
    return re.compile(pattern, flags=flags)


def _build_replacement_lookup(
    name_to_verbalized: Mapping[str, str],
    case_sensitive: bool,
) -> tuple[dict[str, str], dict[str, str]]:
    if case_sensitive:
        return dict(name_to_verbalized), {}

    lookup: dict[str, str] = {}
    canonical: dict[str, str] = {}
    for term, verbalized in name_to_verbalized.items():
        key = term.lower()
        if key not in lookup:
            lookup[key] = verbalized
            canonical[key] = term
    return lookup, canonical


def replace_pronunciations(
    text: str,
    name_to_verbalized: dict[str, str],
    match_whole_words: bool = True,
    case_sensitive: bool = True,
) -> str:
    if not name_to_verbalized:
        return text

    replacement_lookup, _ = _build_replacement_lookup(name_to_verbalized, case_sensitive)
    names = sorted(name_to_verbalized.keys(), key=len, reverse=True)
    pattern = _build_replace_pattern(
        names=names,
        match_whole_words=match_whole_words,
        case_sensitive=case_sensitive,
    )

    def _replace(match: re.Match[str]) -> str:
        key = match.group(0)
        if case_sensitive:
            return replacement_lookup.get(key, key)

        normalized_key = key.lower()
        verbalized_form = replacement_lookup.get(normalized_key)
        return verbalized_form if verbalized_form is not None else key

    return pattern.sub(_replace, text)


def replace_pronunciations_with_counts(
    text: str,
    name_to_verbalized: Mapping[str, str],
    match_whole_words: bool = True,
    case_sensitive: bool = True,
) -> tuple[str, dict[str, int]]:
    if not name_to_verbalized:
        return text, {}

    replacement_lookup, canonical_terms = _build_replacement_lookup(name_to_verbalized, case_sensitive)
    names = sorted(name_to_verbalized.keys(), key=len, reverse=True)
    pattern = _build_replace_pattern(
        names=names,
        match_whole_words=match_whole_words,
        case_sensitive=case_sensitive,
    )
    replacement_counts: dict[str, int] = {}

    def _replace(match: re.Match[str]) -> str:
        key = match.group(0)
        if case_sensitive:
            verbalized_form = replacement_lookup.get(key)
            if verbalized_form is None:
                return key
            replacement_counts[key] = replacement_counts.get(key, 0) + 1
            return verbalized_form

        normalized_key = key.lower()
        verbalized_form = replacement_lookup.get(normalized_key)
        canonical_term = canonical_terms.get(normalized_key)
        if verbalized_form is None or canonical_term is None:
            return key
        replacement_counts[canonical_term] = replacement_counts.get(canonical_term, 0) + 1
        return verbalized_form

    replaced = pattern.sub(_replace, text)
    return replaced, replacement_counts
