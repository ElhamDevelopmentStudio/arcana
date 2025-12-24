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
