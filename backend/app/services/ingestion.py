import re
from difflib import SequenceMatcher
from typing import Any

TEXTUAL_CHAPTER_NUMBER_PATTERN = (
    "one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|"
    "fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty"
)
CHAPTER_HEADER_RE = re.compile(
    rf"^\s*((?:(?:chapter|ch\.)\s+(?:[0-9]+|[ivxlcdm]+|(?:{TEXTUAL_CHAPTER_NUMBER_PATTERN}))[^\n]*)|"
    r"(?:prologue|epilogue|interlude(?:\s+[0-9ivxlcdm]+)?))\s*$",
    re.IGNORECASE | re.MULTILINE,
)
CHAPTER_FILENAME_SPLIT_RE = re.compile(r"(\d+)")
MARKDOWN_FENCE_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
MARKDOWN_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
AMBIGUOUS_CHAPTER_BREAK_RE = re.compile(r"\n\s*(?:\*{3,}|-{3,}|_{3,}|={3,}|~{3,})\s*\n")
MAX_TITLE_CANDIDATE_LENGTH = 120
DEFAULT_INGESTION_TITLE = "Untitled Novel"
SUSPECTED_DUPLICATE_CONTENT_THRESHOLD = 0.95
SUSPECTED_DUPLICATE_CONTENT_MIN_LENGTH = 220
SUSPECTED_DUPLICATE_CONTENT_MIN_SUBSTRING_RATIO = 0.85

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
    chapters, _ = detect_chapters_with_metadata(raw_text)
    return chapters


def detect_chapters_with_metadata(
    raw_text: str,
) -> tuple[list[tuple[str, str]], bool]:
    matches = list(CHAPTER_HEADER_RE.finditer(raw_text))
    if not matches:
        fallback_chapters = detect_fallback_chapters_for_ambiguous_text(raw_text)
        if fallback_chapters:
            return fallback_chapters, True
        return [("Chapter 1", raw_text.strip())], False

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
        fallback_chapters = detect_fallback_chapters_for_ambiguous_text(raw_text)
        if fallback_chapters:
            return fallback_chapters, True
        return [("Chapter 1", raw_text.strip())], False
    return chapters, False


def contains_explicit_chapter_header(raw_text: str) -> bool:
    return CHAPTER_HEADER_RE.search(raw_text) is not None


def detect_fallback_chapters_for_ambiguous_text(
    raw_text: str,
    *,
    min_section_chars: int = 140,
) -> list[tuple[str, str]]:
    normalized = raw_text.replace("\r\n", "\n")
    sections = [part.strip() for part in AMBIGUOUS_CHAPTER_BREAK_RE.split(normalized) if part.strip()]
    if len(sections) <= 1:
        return []
    if any(len(section) < min_section_chars for section in sections):
        return []
    return [(f"Chapter {index}", section) for index, section in enumerate(sections, start=1)]


def _normalize_for_duplicate_detection(value: str) -> str:
    return " ".join(value.split()).strip().lower()


def _content_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


def detect_suspected_duplicate_content(
    chapters: list[tuple[str, str]],
    *,
    similarity_threshold: float = SUSPECTED_DUPLICATE_CONTENT_THRESHOLD,
    minimum_chars: int = SUSPECTED_DUPLICATE_CONTENT_MIN_LENGTH,
) -> list[dict[str, Any]]:
    normalized_chapters: list[tuple[int, str, str]] = []
    for index, (title, content) in enumerate(chapters, start=1):
        normalized_content = _normalize_for_duplicate_detection(content)
        if len(normalized_content) < minimum_chars:
            continue
        normalized_chapters.append((index, title, normalized_content))

    suspected_duplicates: list[dict[str, Any]] = []
    for left_pos in range(len(normalized_chapters)):
        left_index, left_title, left_content = normalized_chapters[left_pos]
        for right_pos in range(left_pos + 1, len(normalized_chapters)):
            right_index, right_title, right_content = normalized_chapters[right_pos]

            if not left_content or not right_content:
                continue

            shorter = left_content if len(left_content) <= len(right_content) else right_content
            longer = right_content if len(left_content) <= len(right_content) else left_content
            if shorter in longer:
                ratio = float(len(shorter)) / float(len(longer))
                if ratio >= SUSPECTED_DUPLICATE_CONTENT_MIN_SUBSTRING_RATIO:
                    suspected_duplicates.append(
                        {
                            "chapter_index_a": left_index,
                            "chapter_index_b": right_index,
                            "chapter_title_a": left_title,
                            "chapter_title_b": right_title,
                            "similarity": round(ratio, 4),
                        }
                    )
                    continue

            similarity = _content_similarity(left_content, right_content)
            if similarity >= similarity_threshold:
                suspected_duplicates.append(
                    {
                        "chapter_index_a": left_index,
                        "chapter_index_b": right_index,
                        "chapter_title_a": left_title,
                        "chapter_title_b": right_title,
                        "similarity": round(similarity, 4),
                    }
                )

    return suspected_duplicates


def build_suspected_duplicate_content_warnings(
    source: str,
    suspected_pairs: list[dict[str, Any]],
) -> list[dict[str, str | float | int | list[int]]]:
    warnings: list[dict[str, str | float | int | list[int]]] = []
    for pair in suspected_pairs:
        warnings.append(
            {
                "source": source,
                "level": "warning",
                "type": "suspected_duplicate_content",
                "chapter_indices": [pair["chapter_index_a"], pair["chapter_index_b"]],
                "similarity": pair["similarity"],
                "message": (
                    f"Suspected duplicated content between chapters {pair['chapter_index_a']} and "
                    f"{pair['chapter_index_b']} with similarity {pair['similarity']}"
                ),
            }
        )
    return warnings


def build_ambiguous_chapter_boundary_warning(
    source: str,
    section_count: int,
) -> dict[str, str | int]:
    return {
        "source": source,
        "level": "warning",
        "type": "ambiguous_chapter_boundaries",
        "section_count": section_count,
        "message": (
            f"Detected ambiguous chapter boundary markers for {source}; "
            f"fallback split produced {section_count} chapter(s)."
        ),
    }


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


def detect_chapters_from_file_boundaries(file_boundaries: list[tuple[str, str]]) -> list[tuple[str, str]]:
    chapters: list[tuple[str, str]] = []
    for filename, file_content in file_boundaries:
        content = file_content.strip()
        if not content:
            continue
        chapter_index = len(chapters) + 1
        title = chapter_title_from_filename(filename, chapter_index=chapter_index)
        chapters.append((title, content))
    return chapters


def build_internal_chapter_id(chapter_index: int) -> str:
    return f"ch-{chapter_index:04d}"


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


def is_likely_unsupported_encoding(
    decoded_text: str,
    *,
    replacement_threshold: float = 0.02,
    null_byte_threshold: float = 0.10,
    minimum_length: int = 40,
) -> bool:
    if not decoded_text:
        return False

    length = len(decoded_text)
    if length < minimum_length:
        return False

    replacement_ratio = decoded_text.count("\ufffd") / length
    null_ratio = decoded_text.count("\x00") / length
    return replacement_ratio >= replacement_threshold or null_ratio >= null_byte_threshold


def detect_duplicate_chapter_titles(chapters: list[tuple[str, str]]) -> list[dict[str, object]]:
    seen: dict[str, dict[str, object]] = {}
    for index, (title, _content) in enumerate(chapters, start=1):
        normalized = _normalize_for_overlap(title)
        if not normalized:
            continue
        if normalized not in seen:
            seen[normalized] = {"title": title.strip(), "occurrences": [index]}
            continue
        seen[normalized]["occurrences"].append(index)

    duplicates: list[dict[str, object]] = []
    for entry in seen.values():
        occurrences = entry["occurrences"]
        if isinstance(occurrences, list) and len(occurrences) > 1:
            duplicates.append(
                {
                    "title": entry["title"],
                    "occurrences": occurrences,
                    "count": len(occurrences),
                }
            )
    return duplicates


def build_duplicate_title_warnings(source: str, chapters: list[tuple[str, str]]) -> list[dict[str, object]]:
    warnings: list[dict[str, object]] = []
    for duplicate in detect_duplicate_chapter_titles(chapters):
        title = str(duplicate["title"])
        warnings.append(
            {
                "source": source,
                "level": "warning",
                "type": "duplicate_chapter_title",
                "title": title,
                "occurrences": duplicate["occurrences"],
                "message": f"Detected duplicate chapter title '{title}'",
            }
        )
    return warnings


def build_duplicate_title_dedup_actions(source: str, chapters: list[tuple[str, str]]) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    for duplicate in detect_duplicate_chapter_titles(chapters):
        title = str(duplicate["title"])
        occurrences = list(duplicate["occurrences"]) if isinstance(duplicate["occurrences"], list) else []
        if not occurrences:
            continue
        normalized_title = _normalize_for_overlap(title) or "untitled"
        dedup_keys = [f"{normalized_title}__{position:02d}" for position in range(1, len(occurrences) + 1)]
        actions.append(
            {
                "source": source,
                "type": "chapter_title_dedup_action",
                "title": title,
                "normalized_title": normalized_title,
                "canonical_occurrence": occurrences[0],
                "duplicate_occurrences": occurrences[1:],
                "dedup_keys": dedup_keys,
                "message": f"Prepared dedup keys for duplicate chapter title '{title}'",
            }
        )
    return actions
