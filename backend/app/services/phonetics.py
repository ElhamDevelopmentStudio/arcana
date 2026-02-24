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
