import re

PARAGRAPH_SPLIT_RE = re.compile(r"\n{2,}")
MAX_SEGMENT_CHARS_HARD_CAP = 255
_INTELLIGIBILITY_MIN_TAIL_CHARS = 20
_PUNCTUATION_PREFERENCE_WINDOW = 18
_PREFERRED_SPLIT_PUNCTUATION = (".", "!", "?", ";", ":", ",")
_COMMON_ABBREVIATIONS = {
    "mr.",
    "mrs.",
    "ms.",
    "dr.",
    "sr.",
    "jr.",
    "st.",
    "mt.",
    "vs.",
    "e.g.",
    "i.e.",
    "etc.",
    "ph.d.",
    "u.s.",
    "u.s.a.",
    "u.k.",
    "p.m.",
    "a.m.",
    "jan.",
    "feb.",
    "mar.",
    "apr.",
    "jun.",
    "jul.",
    "aug.",
    "sep.",
    "sept.",
    "oct.",
    "nov.",
    "dec.",
}
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


def _build_double_quote_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    open_double_quote: int | None = None
    open_curly_quote: int | None = None

    for index, char in enumerate(text):
        if char == '"':
            if open_double_quote is None:
                open_double_quote = index
            else:
                spans.append((open_double_quote, index + 1))
                open_double_quote = None
        elif char == "“":
            if open_curly_quote is None:
                open_curly_quote = index
            else:
                spans.append((open_curly_quote, index + 1))
                open_curly_quote = None
        elif char == "”":
            if open_curly_quote is None:
                spans.append((index, len(text)))
            else:
                spans.append((open_curly_quote, index + 1))
                open_curly_quote = None

    if open_double_quote is not None:
        spans.append((open_double_quote, len(text)))
    if open_curly_quote is not None:
        spans.append((open_curly_quote, len(text)))
    return spans


def _is_split_inside_quote(split_index: int, quote_spans: list[tuple[int, int]]) -> bool:
    return any(start < split_index < end for start, end in quote_spans)


def _is_abbreviation_cut(remaining: str, split_index: int) -> bool:
    if split_index <= 0 or split_index > len(remaining):
        return False
    if remaining[split_index - 1] != ".":
        return False

    token_start = split_index - 1
    while token_start - 1 >= 0 and (
        remaining[token_start - 1].isalpha() or remaining[token_start - 1] == "."
    ):
        token_start -= 1

    token = remaining[token_start : split_index]
    token_lower = token.lower()

    if token in _COMMON_ABBREVIATIONS:
        return True
    if token_lower in _COMMON_ABBREVIATIONS:
        return True

    if re.fullmatch(r"(?:[A-Za-z]\.){2,}", token):
        return True

    if re.fullmatch(r"[A-Za-z]\.", token):
        return True

    base = token[:-1]
    if not base:
        return False

    return len(base) <= 2 and base.isalpha() and base.isupper()


def _split_points_by_sentence_end(text: str) -> list[int]:
    split_points: list[int] = []
    for i, char in enumerate(text):
        if char not in ".!?":
            continue

        if char == "." and _is_abbreviation_cut(text, i + 1):
            continue
        next_index = i + 1
        if next_index < len(text) and text[next_index].isspace():
            split_points.append(next_index)
        elif next_index >= len(text):
            split_points.append(next_index)
    return split_points


def _find_split_point(remaining: str, max_chars: int) -> int:
    candidates = [index for index, char in enumerate(remaining[: max_chars + 1]) if char == " "]
    if not candidates:
        return max_chars

    quote_spans = _build_double_quote_spans(remaining)
    min_tail_ok_cutoff = _INTELLIGIBILITY_MIN_TAIL_CHARS
    punctuation_window_floor = max(1, max_chars - _PUNCTUATION_PREFERENCE_WINDOW)
    preferred_punctuation_candidates = [
        cut
        for cut in candidates
        if not _is_split_inside_quote(cut, quote_spans)
        and not _is_abbreviation_cut(remaining, cut)
        and cut >= punctuation_window_floor
        and cut - 1 >= 0
        and remaining[cut - 1] in _PREFERRED_SPLIT_PUNCTUATION
        and len(remaining[cut:]) >= min_tail_ok_cutoff
        and not _starts_with_clause_connector(remaining[cut:])
    ]
    if preferred_punctuation_candidates:
        return preferred_punctuation_candidates[-1]

    for cut in reversed(candidates):
        tail = remaining[cut:]
        if _is_split_inside_quote(cut, quote_spans):
            continue
        if _is_abbreviation_cut(remaining, cut):
            continue
        if _starts_with_clause_connector(tail):
            continue
        if len(tail) >= _INTELLIGIBILITY_MIN_TAIL_CHARS:
            return cut

    for cut in reversed(candidates):
        tail = remaining[cut:]
        if _is_split_inside_quote(cut, quote_spans):
            continue
        if _is_abbreviation_cut(remaining, cut):
            continue
        if len(tail) >= _INTELLIGIBILITY_MIN_TAIL_CHARS:
            return cut

    return candidates[-1]


def split_paragraphs(text: str) -> list[str]:
    paragraphs = [paragraph.strip() for paragraph in PARAGRAPH_SPLIT_RE.split(text)]
    non_empty_paragraphs = [paragraph for paragraph in paragraphs if paragraph]
    return non_empty_paragraphs if non_empty_paragraphs else [text.strip()]


def split_sentences(text: str) -> list[str]:
    split_points = _split_points_by_sentence_end(text)
    if not split_points:
        return [text.strip()] if text.strip() else []

    sentences: list[str] = []
    start = 0
    for point in split_points:
        if point < start:
            continue
        part = text[start:point].strip()
        if part:
            sentences.append(part)
        start = point
        while start < len(text) and text[start].isspace():
            start += 1
    tail = text[start:].strip()
    if tail:
        sentences.append(tail)

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


def segment_text_with_parent_paragraph(text: str, max_chars: int = 255) -> list[dict[str, object]]:
    hard_cap = min(int(max_chars), MAX_SEGMENT_CHARS_HARD_CAP)
    if hard_cap < 1:
        hard_cap = 1

    paragraphs_and_sentences = split_paragraphs_into_sentences(text)
    segments: list[dict[str, object]] = []

    for paragraph_index, sentences in enumerate(paragraphs_and_sentences, start=1):
        buffer = ""
        sentence_indexes: set[int] = set()

        for sentence_index, sentence in enumerate(sentences, start=1):
            sentence_parts = _split_long_sentence(sentence, hard_cap)
            for part in sentence_parts:
                candidate = part if not buffer else f"{buffer} {part}"
                if len(candidate) <= hard_cap:
                    buffer = candidate
                    sentence_indexes.add(sentence_index)
                    continue

                if buffer:
                    start_sentence = min(sentence_indexes) if sentence_indexes else sentence_index
                    segments.append(
                        {
                            "text": buffer,
                            "paragraph_index": paragraph_index,
                            "sentence_start_index": start_sentence,
                            "sentence_end_index": max(sentence_indexes) if sentence_indexes else start_sentence,
                        }
                    )
                    sentence_indexes = set()
                buffer = part
                sentence_indexes.add(sentence_index)

        if buffer:
            start_sentence = min(sentence_indexes) if sentence_indexes else 1
            segments.append(
                {
                    "text": buffer,
                    "paragraph_index": paragraph_index,
                    "sentence_start_index": start_sentence,
                    "sentence_end_index": max(sentence_indexes) if sentence_indexes else start_sentence,
                }
            )
            buffer = ""

    return [segment for segment in segments if segment.get("text")]
