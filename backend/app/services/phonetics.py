from collections.abc import Mapping
from collections.abc import Sequence

import re


def _build_replace_pattern(names: Sequence[str], match_whole_words: bool) -> re.Pattern[str]:
    if not names:
        raise ValueError("No replacement terms provided.")

    escaped_terms = "|".join(re.escape(name) for name in names)
    if match_whole_words:
        return re.compile(r"\b(" + escaped_terms + r")\b")
    return re.compile("(" + escaped_terms + ")")


def replace_pronunciations(
    text: str,
    name_to_verbalized: dict[str, str],
    match_whole_words: bool = True,
) -> str:
    if not name_to_verbalized:
        return text

    names = sorted(name_to_verbalized.keys(), key=len, reverse=True)
    pattern = _build_replace_pattern(names=names, match_whole_words=match_whole_words)

    def _replace(match: re.Match[str]) -> str:
        key = match.group(0)
        return name_to_verbalized.get(key, key)

    return pattern.sub(_replace, text)


def replace_pronunciations_with_counts(
    text: str,
    name_to_verbalized: Mapping[str, str],
    match_whole_words: bool = True,
) -> tuple[str, dict[str, int]]:
    if not name_to_verbalized:
        return text, {}

    names = sorted(name_to_verbalized.keys(), key=len, reverse=True)
    pattern = _build_replace_pattern(names=names, match_whole_words=match_whole_words)
    replacement_counts: dict[str, int] = {}

    def _replace(match: re.Match[str]) -> str:
        key = match.group(0)
        if key in name_to_verbalized:
            replacement_counts[key] = replacement_counts.get(key, 0) + 1
            return name_to_verbalized[key]
        return key

    replaced = pattern.sub(_replace, text)
    return replaced, replacement_counts
