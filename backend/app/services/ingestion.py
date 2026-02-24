import re

CHAPTER_HEADER_RE = re.compile(r"^\s*(chapter\s+[0-9ivxlcdm]+[^\n]*)\s*$", re.IGNORECASE | re.MULTILINE)


def decode_text(raw_bytes: bytes) -> str:
    return raw_bytes.decode("utf-8", errors="replace")


def detect_chapters(raw_text: str) -> list[tuple[str, str]]:
    matches = list(CHAPTER_HEADER_RE.finditer(raw_text))
    if not matches:
        return [("Chapter 1", raw_text.strip())]

    chapters: list[tuple[str, str]] = []
    for index, match in enumerate(matches, start=1):
        start = match.end()
        end = matches[index].start() if index < len(matches) else len(raw_text)
        title = match.group(1).strip()
        content = raw_text[start:end].strip()
        if not content:
            continue
        chapters.append((title, content))

    if not chapters:
        return [("Chapter 1", raw_text.strip())]
    return chapters
