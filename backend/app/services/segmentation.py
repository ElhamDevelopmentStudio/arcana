import re

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str) -> list[str]:
    sentences = [part.strip() for part in SENTENCE_SPLIT_RE.split(text) if part.strip()]
    return sentences if sentences else [text.strip()]


def _split_long_sentence(sentence: str, max_chars: int) -> list[str]:
    chunks: list[str] = []
    remaining = sentence.strip()

    while len(remaining) > max_chars:
        cut = remaining.rfind(" ", 0, max_chars + 1)
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
    sentences = split_sentences(text)
    segments: list[str] = []
    buffer = ""

    for sentence in sentences:
        sentence_parts = _split_long_sentence(sentence, max_chars)
        for part in sentence_parts:
            candidate = part if not buffer else f"{buffer} {part}"
            if len(candidate) <= max_chars:
                buffer = candidate
                continue

            if buffer:
                segments.append(buffer)
            buffer = part

    if buffer:
        segments.append(buffer)

    return [segment for segment in segments if segment]
