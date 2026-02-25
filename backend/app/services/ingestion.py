import re

CHAPTER_HEADER_RE = re.compile(r"^\s*(chapter\s+[0-9ivxlcdm]+[^\n]*)\s*$", re.IGNORECASE | re.MULTILINE)
MAX_TITLE_CANDIDATE_LENGTH = 120
DEFAULT_INGESTION_TITLE = "Untitled Novel"


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


def detect_title_with_fallback(raw_text: str, filename: str | None = None) -> str:
    search_window = raw_text
    first_chapter_match = CHAPTER_HEADER_RE.search(raw_text)
    if first_chapter_match is not None:
        search_window = raw_text[: first_chapter_match.start()]

    for line in search_window.splitlines():
        candidate = line.strip().strip("#").strip()
        if not candidate:
            continue
        if CHAPTER_HEADER_RE.match(candidate):
            continue
        if len(candidate) > MAX_TITLE_CANDIDATE_LENGTH:
            continue
        return candidate

    if filename:
        stem = filename.rsplit(".", 1)[0].strip()
        if stem:
            return stem.replace("_", " ").replace("-", " ")

    return DEFAULT_INGESTION_TITLE
