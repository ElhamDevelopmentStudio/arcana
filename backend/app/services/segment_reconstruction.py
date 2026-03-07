from __future__ import annotations

from typing import Any


def _coerce_non_negative_index(value: object) -> int | None:
    if not isinstance(value, (int, bool, str)):
        return None
    try:
        as_int = int(value)
    except (TypeError, ValueError):
        return None
    if as_int < 0:
        return None
    return as_int


def _extract_segment_text(segment: dict[str, Any]) -> str:
    if not isinstance(segment, dict):
        return ""

    normalized_text = segment.get("normalized_text")
    if isinstance(normalized_text, str):
        return normalized_text

    original_text = segment.get("original_text")
    if isinstance(original_text, str):
        return original_text

    return str(original_text) if original_text is not None else ""


def reconstruct_chapter_text_from_segments(chapter_text: str, segment_payloads: list[dict[str, Any]]) -> str:
    normalized_chapter_text = chapter_text or ""

    prepared_segments = []
    for position, segment in enumerate(segment_payloads):
        if not isinstance(segment, dict):
            continue

        original_pointer = segment.get("original_span_pointer") if isinstance(segment, dict) else None
        if not isinstance(original_pointer, dict):
            original_pointer = None

        start = _coerce_non_negative_index(original_pointer.get("normalized_start_char") if original_pointer else None)
        end = _coerce_non_negative_index(original_pointer.get("normalized_end_char") if original_pointer else None)
        segment_text = _extract_segment_text(segment)
        segment_index = _coerce_non_negative_index(segment.get("segment_index")) or position
        prepared_segments.append((start, end, segment_index, position, segment_text))

    if not prepared_segments:
        return ""

    if all(start is not None and end is not None for start, end, _, _, _ in prepared_segments):
        ordered = sorted(
            prepared_segments,
            key=lambda entry: (entry[0], entry[3]),
        )

        reconstructed: list[str] = []
        cursor = 0
        for start, end, _, _, _ in ordered:
            start_int = int(start) if start is not None else 0
            end_int = int(end) if end is not None else 0
            if end_int < start_int:
                continue
            if end_int > len(normalized_chapter_text):
                end_int = len(normalized_chapter_text)
            if start_int > len(normalized_chapter_text):
                start_int = len(normalized_chapter_text)

            if start_int > cursor:
                reconstructed.append(normalized_chapter_text[cursor:start_int])
            reconstructed.append(normalized_chapter_text[start_int:end_int])
            cursor = end_int

        if cursor < len(normalized_chapter_text):
            reconstructed.append(normalized_chapter_text[cursor:])

        return "".join(reconstructed)

    ordered = sorted(prepared_segments, key=lambda entry: (entry[2], entry[3]))
    return "".join(segment_text for _, __, ___, ____, segment_text in ordered)


def _extract_chapter_text(chapter_artifact: dict[str, Any]) -> str:
    if not isinstance(chapter_artifact, dict):
        return ""

    for key in ("normalized_text", "chapter_text", "text", "original_text", "raw_text"):
        value = chapter_artifact.get(key)
        if isinstance(value, str):
            return value
    return ""


def reconstruct_corpus_from_chapter_artifacts(chapter_artifacts: list[dict[str, Any]]) -> str:
    prepared_chapters: list[tuple[int, int, str]] = []

    for index, artifact in enumerate(chapter_artifacts):
        if not isinstance(artifact, dict):
            continue

        chapter_index = _coerce_non_negative_index(artifact.get("chapter_index"))
        if chapter_index is None:
            chapter_index = _coerce_non_negative_index(artifact.get("chapter_id"))
        if chapter_index is None:
            chapter_index = index

        chapter_text = _extract_chapter_text(artifact)
        segment_payloads = artifact.get("segment_payloads")

        if isinstance(segment_payloads, list) and chapter_text is not None:
            reconstructed_text = reconstruct_chapter_text_from_segments(chapter_text, segment_payloads)
        else:
            reconstructed_text = chapter_text or ""

        prepared_chapters.append((chapter_index, index, reconstructed_text))

    if not prepared_chapters:
        return ""

    ordered_chapters = sorted(prepared_chapters, key=lambda entry: (entry[0], entry[1]))
    return "\n\n".join(chapter_text for _, __, chapter_text in ordered_chapters)
