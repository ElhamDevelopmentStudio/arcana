import re

PARAGRAPH_SPLIT_RE = re.compile(r"\n{2,}")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
MAX_SEGMENT_CHARS_HARD_CAP = 255
_INTELLIGIBILITY_MIN_TAIL_CHARS = 20
_CLAUSE_CONNECTOR_PREFIXES = (
    "and ",
    "but ",
    "or ",
    "so ",
    "then ",
    "because ",
    "since ",
    "while ",
    "if ",
    "when ",
    "as ",
    "although ",
    "though ",
    "until ",
    "unless ",
    "after ",
    "before ",
    "once ",
)


def _starts_with_clause_connector(text: str) -> bool:
    stripped = text.strip().lower()
    return any(stripped.startswith(prefix) for prefix in _CLAUSE_CONNECTOR_PREFIXES)


def _find_split_point(remaining: str, max_chars: int) -> int:
    candidates = [index for index, char in enumerate(remaining[: max_chars + 1]) if char == " "]
    if not candidates:
        return max_chars

    for cut in reversed(candidates):
        tail = remaining[cut:]
        if _starts_with_clause_connector(tail):
            continue
        if len(tail) >= _INTELLIGIBILITY_MIN_TAIL_CHARS:
            return cut

    for cut in reversed(candidates):
        tail = remaining[cut:]
        if len(tail) >= _INTELLIGIBILITY_MIN_TAIL_CHARS:
            return cut

    return candidates[-1]


def split_paragraphs(text: str) -> list[str]:
    paragraphs = [paragraph.strip() for paragraph in PARAGRAPH_SPLIT_RE.split(text)]
    non_empty_paragraphs = [paragraph for paragraph in paragraphs if paragraph]
    return non_empty_paragraphs if non_empty_paragraphs else [text.strip()]


def split_sentences(text: str) -> list[str]:
    sentences = [part.strip() for part in SENTENCE_SPLIT_RE.split(text) if part.strip()]
    return sentences if sentences else [text.strip()]


def split_paragraphs_into_sentences(text: str) -> list[list[str]]:
    paragraphs = split_paragraphs(text)
    return [split_sentences(paragraph) for paragraph in paragraphs if paragraph]


def _split_long_sentence(sentence: str, max_chars: int) -> list[str]:
    chunks: list[str] = []
    remaining = sentence.strip()

    while len(remaining) > max_chars:
        cut = _find_split_point(remaining, max_chars)
        if cut <= 0:
            cut = max_chars
        chunk = remaining[:cut].strip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[cut:].strip()

    if remaining:
        chunks.append(remaining)
    return chunks


def segment_text(text: str, max_chars: int = 255) -> list[str]:
    hard_cap = min(int(max_chars), MAX_SEGMENT_CHARS_HARD_CAP)
    if hard_cap < 1:
        hard_cap = 1

    paragraphs_and_sentences = split_paragraphs_into_sentences(text)
    segments: list[str] = []

    for sentences in paragraphs_and_sentences:
        buffer = ""
        for sentence in sentences:
            sentence_parts = _split_long_sentence(sentence, hard_cap)
            for part in sentence_parts:
                candidate = part if not buffer else f"{buffer} {part}"
                if len(candidate) <= hard_cap:
                    buffer = candidate
                    continue

                if buffer:
                    segments.append(buffer)
                buffer = part

        if buffer:
            segments.append(buffer)

    return [segment for segment in segments if segment]
