from collections.abc import Mapping

import re


def replace_pronunciations(text: str, name_to_verbalized: dict[str, str]) -> str:
    if not name_to_verbalized:
        return text

    names = sorted(name_to_verbalized.keys(), key=len, reverse=True)
    pattern = re.compile(r"\b(" + "|".join(re.escape(name) for name in names) + r")\b")

    def _replace(match: re.Match[str]) -> str:
        key = match.group(0)
        return name_to_verbalized.get(key, key)

    return pattern.sub(_replace, text)


def replace_pronunciations_with_counts(
    text: str,
    name_to_verbalized: Mapping[str, str],
) -> tuple[str, dict[str, int]]:
    if not name_to_verbalized:
        return text, {}

    names = sorted(name_to_verbalized.keys(), key=len, reverse=True)
    pattern = re.compile(r"\b(" + "|".join(re.escape(name) for name in names) + r")\b")
    replacement_counts: dict[str, int] = {}

    def _replace(match: re.Match[str]) -> str:
        key = match.group(0)
        if key in name_to_verbalized:
            replacement_counts[key] = replacement_counts.get(key, 0) + 1
            return name_to_verbalized[key]
        return key

    replaced = pattern.sub(_replace, text)
    return replaced, replacement_counts
