import re

CHAPTER_HEADER_RE = re.compile(r"^\s*(chapter\s+[0-9ivxlcdm]+[^\n]*)\s*$", re.IGNORECASE | re.MULTILINE)
CHAPTER_FILENAME_SPLIT_RE = re.compile(r"(\d+)")
MARKDOWN_FENCE_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
MARKDOWN_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
MAX_TITLE_CANDIDATE_LENGTH = 120
DEFAULT_INGESTION_TITLE = "Untitled Novel"

ENCODING_BOM_MAP: tuple[tuple[bytes, str, float], ...] = (
    (b"\xff\xfe\x00\x00", "utf-32-le", 1.0),
    (b"\x00\x00\xfe\xff", "utf-32-be", 1.0),
    (b"\xef\xbb\xbf", "utf-8-sig", 1.0),
    (b"\xff\xfe", "utf-16-le", 1.0),
    (b"\xfe\xff", "utf-16-be", 1.0),
)


def decode_text(raw_bytes: bytes) -> str:
    decoded_text, _encoding, _confidence = decode_text_with_metadata(raw_bytes)
    return decoded_text


def decode_text_with_metadata(raw_bytes: bytes) -> tuple[str, str, float]:
    encoding, _confidence = detect_text_encoding(raw_bytes)
    return (to_internal_utf8(raw_bytes.decode(encoding, errors="replace")), encoding, _confidence)


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


def contains_explicit_chapter_header(raw_text: str) -> bool:
    return CHAPTER_HEADER_RE.search(raw_text) is not None


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


def chapter_filename_sort_key(filename: str) -> list[int | str]:
    tokens: list[int | str] = []
    for chunk in CHAPTER_FILENAME_SPLIT_RE.split(filename.lower()):
        if not chunk:
            continue
        if chunk.isdigit():
            tokens.append(int(chunk))
        else:
            tokens.append(chunk)
    return tokens


def chapter_title_from_filename(filename: str, chapter_index: int) -> str:
    stem = filename.rsplit(".", 1)[0].strip()
    if not stem:
        return f"Chapter {chapter_index}"
    normalized = stem.replace("_", " ").replace("-", " ").strip()
    if not normalized:
        return f"Chapter {chapter_index}"
    return normalized


def normalize_markdown_for_ingestion(markdown_text: str) -> str:
    normalized = markdown_text.replace("\r\n", "\n")
    normalized = MARKDOWN_FENCE_RE.sub("", normalized)
    normalized = MARKDOWN_HEADING_RE.sub("", normalized)
    normalized = MARKDOWN_LINK_RE.sub(r"\1", normalized)
    normalized = normalized.replace("**", "").replace("__", "").replace("*", "").replace("`", "")
    return to_internal_utf8(normalized.strip())


def detect_text_encoding(raw_bytes: bytes) -> tuple[str, float]:
    if not raw_bytes:
        return ("utf-8", 1.0)

    for bom, encoding, confidence in ENCODING_BOM_MAP:
        if raw_bytes.startswith(bom):
            return (encoding, confidence)

    try:
        raw_bytes.decode("utf-8", errors="strict")
        return ("utf-8", 0.95)
    except UnicodeDecodeError:
        pass

    return ("cp1252", 0.4)


def to_internal_utf8(value: str) -> str:
    return value.encode("utf-8", errors="replace").decode("utf-8", errors="replace")


def build_encoding_warning(source: str, encoding: str, confidence: float) -> dict[str, str | float] | None:
    normalized_encoding = encoding.strip().lower()
    if normalized_encoding in {"utf-8", "utf-8-sig"} and confidence >= 0.9:
        return None

    message = (
        f"Decoded {source} using {normalized_encoding} "
        f"(confidence {confidence:.2f}); normalized to UTF-8 internal form."
    )
    return {
        "source": source,
        "encoding": normalized_encoding,
        "confidence": round(confidence, 4),
        "level": "warning",
        "message": message,
    }


def extract_single_append_chapter(
    chapters: list[tuple[str, str]],
    fallback_title: str,
) -> tuple[str, str]:
    non_empty = [(title.strip(), content.strip()) for title, content in chapters if content.strip()]
    if len(non_empty) != 1:
        raise ValueError("Append chapter endpoint requires exactly one non-empty chapter in the uploaded file")

    title, content = non_empty[0]
    normalized_title = title or fallback_title
    return (normalized_title, content)


def _normalize_for_overlap(value: str) -> str:
    return " ".join(value.split()).strip().lower()


def detect_append_overlap_or_duplicate(
    *,
    new_title: str,
    new_content: str,
    existing_chapters: list[tuple[int, str, str]],
    min_overlap_chars: int = 120,
) -> dict[str, int | str] | None:
    normalized_new_title = _normalize_for_overlap(new_title)
    normalized_new_content = _normalize_for_overlap(new_content)
    if not normalized_new_content:
        return None

    for chapter_index, chapter_title, chapter_content in existing_chapters:
        normalized_existing_title = _normalize_for_overlap(chapter_title)
        normalized_existing_content = _normalize_for_overlap(chapter_content)
        if not normalized_existing_content:
            continue

        if normalized_new_content == normalized_existing_content:
            return {
                "kind": "exact_content_duplicate",
                "chapter_index": chapter_index,
                "chapter_title": chapter_title,
            }

        shorter = (
            normalized_new_content
            if len(normalized_new_content) <= len(normalized_existing_content)
            else normalized_existing_content
        )
        longer = (
            normalized_existing_content
            if len(normalized_new_content) <= len(normalized_existing_content)
            else normalized_new_content
        )

        if (
            len(shorter) >= min_overlap_chars
            and shorter in longer
            and normalized_new_title == normalized_existing_title
        ):
            return {
                "kind": "same_title_content_overlap",
                "chapter_index": chapter_index,
                "chapter_title": chapter_title,
            }

    return None


def calculate_delta_affected_range(
    *,
    changed_chapter_indices: list[int],
    total_chapter_count: int,
    context_lookback: int = 0,
) -> dict[str, int] | None:
    if not changed_chapter_indices or total_chapter_count <= 0:
        return None

    positive_indices = sorted({index for index in changed_chapter_indices if index > 0})
    if not positive_indices:
        return None

    raw_start = positive_indices[0] - max(context_lookback, 0)
    start_chapter_index = max(1, raw_start)
    end_chapter_index = min(total_chapter_count, positive_indices[-1])
    if start_chapter_index > end_chapter_index:
        return None

    return {
        "start_chapter_index": start_chapter_index,
        "end_chapter_index": end_chapter_index,
    }
