import re
from difflib import SequenceMatcher
import unicodedata
from functools import lru_cache

from app.config import get_settings

QUOTE_TRANSLATION = str.maketrans({
    "“": '"',
    "”": '"',
    "„": '"',
    "‟": '"',
    "’": "'",
    "‘": "'",
    "‚": "'",
    "‛": "'",
})

UNICODE_SPACE_TRANSLATION = str.maketrans({
    "\u00A0": " ",  # non-breaking space
    "\u2007": " ",  # figure space
    "\u202F": " ",  # narrow no-break space
})
UNICODE_LINE_BREAK_TRANSLATION = str.maketrans({
    "\u2028": "\n",  # line separator
    "\u2029": "\n",  # paragraph separator
    "\u0085": "\n",  # next line
})

HORIZONTAL_WHITESPACE_RE = re.compile(r"[ \t\f\v]+")
THREE_OR_MORE_LINE_BREAKS_RE = re.compile(r"\n{3,}")
ELLIPSIS_UNICODE_RE = re.compile(r"…+")
ELLIPSIS_DOTTED_RE = re.compile(r"\.\s*\.\s*\.(?:\s*\.)*")
PARAGRAPH_SEPARATOR_LINE_RE = re.compile(r"\n\s*(?:\*{3,}|-{3,}|_{3,}|={3,}|~{3,})\s*\n")
EM_DASH_DIALOGUE_LEADER_RE = re.compile(r"(?m)(^|\n)\s*[—–]\s*")

DEFAULT_COPY_ARTIFACT_PATTERN_SET = (
    r"^\s*Page\s+\d+\s*$||^\s*<<<[^>]+>>>\s*$||^\s*\[?Advertisement\]?\s*$"
)
QUOTE_REPAIR_LOW_CONFIDENCE_THRESHOLD = 0.7
_LOW_CONFIDENCE_QUOTE_REPAIR_CONFIDENCE = 0.45
_HIGH_CONFIDENCE_QUOTE_REPAIR_CONFIDENCE = 0.9


def build_original_to_normalized_offset_map(
    original_text: str, normalized_text: str
) -> list[dict[str, int | str]]:
    matcher = SequenceMatcher(None, original_text, normalized_text, autojunk=False)
    return [
        {
            "original_start": original_start,
            "original_end": original_end,
            "normalized_start": normalized_start,
            "normalized_end": normalized_end,
            "type": op,
        }
        for op, original_start, original_end, normalized_start, normalized_end in matcher.get_opcodes()
    ]


_LOSSY_TRANSFORM_FLAG_KEYS = (
    "unicode_normalization",
    "quote_repair_applied",
    "quote_style_normalization",
    "ellipsis_normalization",
    "em_dash_dialogue_style_normalization",
    "copy_artifact_removal",
    "whitespace_normalization",
)


def build_normalization_report(
    source: str,
    *,
    chapter_count: int,
    chapter_reports: list[dict[str, object]],
    suspected_duplicate_title_count: int,
    encoding_issue_count: int,
) -> dict[str, object]:
    lossy_transform_flags: dict[str, bool] = {
        key: False for key in _LOSSY_TRANSFORM_FLAG_KEYS
    }
    total_quote_repair_count = 0
    total_copy_artifact_removed_lines = 0

    for chapter_report in chapter_reports:
        report_counts = chapter_report.get("counts", {})
        if isinstance(report_counts, dict):
            total_quote_repair_count += int(report_counts.get("quote_repair_count", 0))
            total_copy_artifact_removed_lines += int(report_counts.get("copy_artifact_removed_lines", 0))

        report_flags = chapter_report.get("lossy_transform_flags", {})
        if isinstance(report_flags, dict):
            for flag, default_value in lossy_transform_flags.items():
                lossy_transform_flags[flag] = default_value or bool(report_flags.get(flag, False))

    return {
        "source": source,
        "counts": {
            "chapters_detected": chapter_count,
            "suspected_duplicates": suspected_duplicate_title_count,
            "quote_repair_count": total_quote_repair_count,
            "encoding_issues": encoding_issue_count,
            "copy_artifact_removed_lines": total_copy_artifact_removed_lines,
        },
        "lossy_transform_flags": lossy_transform_flags,
    }


def build_segment_level_offset_map(
    chapter_offset_map: list[dict[str, int | str]],
    normalized_segment_start: int,
    normalized_segment_text: str,
) -> list[dict[str, int]]:
    normalized_segment_end = normalized_segment_start + len(normalized_segment_text)
    segment_offset_map: list[dict[str, int]] = []

    for entry in chapter_offset_map:
        normalized_start = int(entry["normalized_start"])
        normalized_end = int(entry["normalized_end"])
        original_start = int(entry["original_start"])
        original_end = int(entry["original_end"])
        op_type = str(entry["type"])

        overlap_start = max(normalized_start, normalized_segment_start)
        overlap_end = min(normalized_end, normalized_segment_end)
        if overlap_start >= overlap_end:
            continue

        local_start = overlap_start - normalized_segment_start
        local_end = overlap_end - normalized_segment_start
        overlap_length = overlap_end - overlap_start
        if op_type == "equal":
            mapped_start = original_start + (overlap_start - normalized_start)
            mapped_end = mapped_start + overlap_length
        elif op_type == "replace":
            orig_len = max(original_end - original_start, 1)
            norm_len = max(normalized_end - normalized_start, 1)
            mapped_start = original_start + int((overlap_start - normalized_start) * orig_len / norm_len)
            mapped_end = original_start + int((overlap_end - normalized_start) * orig_len / norm_len)
        elif op_type == "insert":
            mapped_start = -1
            mapped_end = -1
        else:
            continue

        segment_offset_map.append(
            {
                "original_start": mapped_start,
                "original_end": mapped_end,
                "normalized_start": local_start,
                "normalized_end": local_end,
                "type": op_type,
            }
        )

    return segment_offset_map


def normalize_line_breaks_and_paragraph_separators(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.translate(UNICODE_LINE_BREAK_TRANSLATION)
    return PARAGRAPH_SEPARATOR_LINE_RE.sub("\n\n", text)


def normalize_whitespace(text: str) -> str:
    text = normalize_line_breaks_and_paragraph_separators(text)
    text = text.translate(UNICODE_SPACE_TRANSLATION)
    lines = [HORIZONTAL_WHITESPACE_RE.sub(" ", line).strip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = THREE_OR_MORE_LINE_BREAKS_RE.sub("\n\n", text)
    return text.strip()


def _straighten_quotes(text: str) -> str:
    return text.translate(QUOTE_TRANSLATION)


def _to_curly_quotes(text: str) -> str:
    straightened = _straighten_quotes(text)
    result: list[str] = []
    next_double_open = True
    next_single_open = True

    for index, char in enumerate(straightened):
        if char == '"':
            result.append("“" if next_double_open else "”")
            next_double_open = not next_double_open
            continue

        if char == "'":
            prev_char = straightened[index - 1] if index > 0 else ""
            next_char = straightened[index + 1] if index + 1 < len(straightened) else ""
            if prev_char.isalnum() and next_char.isalnum():
                result.append("’")
            else:
                result.append("‘" if next_single_open else "’")
                next_single_open = not next_single_open
            continue

        result.append(char)

    return "".join(result)


def normalize_quotes(text: str, quote_style: str | None = None) -> str:
    resolved_style = quote_style or get_settings().normalize_quote_style
    if resolved_style == "curly":
        return _to_curly_quotes(text)
    return _straighten_quotes(text)


def normalize_unicode_variants(text: str) -> str:
    return unicodedata.normalize("NFKC", text)


def _is_straight_apostrophe(text: str, index: int) -> bool:
    prev_char = text[index - 1] if index > 0 else ""
    next_char = text[index + 1] if index + 1 < len(text) else ""
    return bool(prev_char.isalnum() and next_char.isalnum())


def _is_likely_closing_quote(text: str, index: int, quote_char: str) -> bool:
    next_char = text[index + 1] if index + 1 < len(text) else ""
    prev_char = text[index - 1] if index > 0 else ""

    if next_char == "":
        return True

    if quote_char == "'" and _is_straight_apostrophe(text, index):
        return False

    if next_char.isspace():
        return bool(prev_char)

    if next_char in '.,!?;:)]}”’"]\'':
        return True

    if prev_char.isalnum() and not next_char.isalnum():
        return True

    return False


def _repair_straight_quote_type(
    text: str,
    quote_char: str,
) -> tuple[str, list[dict[str, object]]]:
    lines = text.splitlines()
    repaired_lines: list[str] = []
    repair_events: list[dict[str, object]] = []

    for line in lines:
        candidate_indexes = [
            index
            for index, character in enumerate(line)
            if character == quote_char
            and not (quote_char == "'" and _is_straight_apostrophe(line, index))
        ]

        if len(candidate_indexes) % 2 != 0:
            first_index = candidate_indexes[0] if candidate_indexes else -1
            if first_index >= 0 and _is_likely_closing_quote(line, first_index, quote_char):
                repaired_lines.append(f"{quote_char}{line}")
                repair_events.append(
                    {
                        "quote_char": quote_char,
                        "line": line,
                        "action": "prepend_opening_quote",
                        "confidence": _HIGH_CONFIDENCE_QUOTE_REPAIR_CONFIDENCE,
                    }
                )
            else:
                repaired_lines.append(f"{line}{quote_char}")
                repair_events.append(
                    {
                        "quote_char": quote_char,
                        "line": line,
                        "action": "append_closing_quote",
                        "confidence": _LOW_CONFIDENCE_QUOTE_REPAIR_CONFIDENCE,
                    }
                )
        else:
            repaired_lines.append(line)

    return "\n".join(repaired_lines), repair_events


def repair_quote_mismatch_with_metadata(
    text: str,
) -> tuple[str, list[dict[str, object]]]:
    normalized = _straighten_quotes(text)
    repaired, double_quote_events = _repair_straight_quote_type(normalized, '"')
    repaired, single_quote_events = _repair_straight_quote_type(repaired, "'")
    return repaired, double_quote_events + single_quote_events


def repair_quote_mismatch(text: str) -> str:
    repaired, _ = repair_quote_mismatch_with_metadata(text)
    return repaired


def build_low_confidence_quote_repair_warning(
    source: str,
    low_confidence_repairs: list[dict[str, object]],
    total_repairs: int,
) -> dict[str, str | object]:
    min_confidence = min(
        float(repair_event["confidence"])
        for repair_event in low_confidence_repairs
        if "confidence" in repair_event
    )
    return {
        "source": source,
        "level": "warning",
        "type": "quote_repair_confidence_low",
        "action_count": len(low_confidence_repairs),
        "repair_events_count": total_repairs,
        "min_confidence": round(min_confidence, 4),
        "message": (
            f"Quote repair matched by heuristic with low confidence for {len(low_confidence_repairs)} "
            f"of {total_repairs} quote repair event(s)."
        ),
    }


def normalize_text_with_warnings(
    text: str,
    source: str = "text",
) -> tuple[str, list[dict[str, object]]]:
    normalized, warnings, _ = normalize_text_with_report(text, source=source)
    return normalized, warnings


def normalize_text_with_report(
    text: str,
    source: str = "text",
) -> tuple[str, list[dict[str, object]], dict[str, object]]:
    normalized_unicode = normalize_unicode_variants(text)
    repaired, repair_events = repair_quote_mismatch_with_metadata(normalized_unicode)
    warnings: list[dict[str, object]] = []

    low_confidence_repairs = [
        repair_event
        for repair_event in repair_events
        if float(repair_event["confidence"]) < QUOTE_REPAIR_LOW_CONFIDENCE_THRESHOLD
    ]
    if low_confidence_repairs:
        warnings.append(
            build_low_confidence_quote_repair_warning(
                source=source,
                low_confidence_repairs=low_confidence_repairs,
                total_repairs=len(repair_events),
            )
        )

    normalized_quotes = normalize_quotes(repaired)
    normalized_ellipsis = normalize_ellipsis_variants(normalized_quotes)
    normalized_dash = normalize_em_dash_dialogue_style(normalized_ellipsis)
    copy_artifact_removed = remove_copy_artifacts(normalized_dash)
    final = normalize_whitespace(copy_artifact_removed)

    lossy_transform_flags = {
        "unicode_normalization": normalized_unicode != text,
        "quote_repair_applied": bool(repair_events),
        "quote_style_normalization": normalized_quotes != repaired,
        "ellipsis_normalization": normalized_ellipsis != normalized_quotes,
        "em_dash_dialogue_style_normalization": normalized_dash != normalized_ellipsis,
        "copy_artifact_removal": copy_artifact_removed != normalized_dash,
        "whitespace_normalization": final != copy_artifact_removed,
    }

    normalized_line_count = len(normalized_dash.splitlines())
    cleaned_line_count = len(copy_artifact_removed.splitlines())
    return final, warnings, {
        "lossy_transform_flags": lossy_transform_flags,
        "counts": {
            "quote_repair_count": len(repair_events),
            "copy_artifact_removed_lines": max(normalized_line_count - cleaned_line_count, 0),
        },
    }


def normalize_ellipsis_variants(text: str) -> str:
    text = ELLIPSIS_UNICODE_RE.sub("...", text)
    text = ELLIPSIS_DOTTED_RE.sub("...", text)
    return text


def normalize_em_dash_dialogue_style(text: str) -> str:
    return EM_DASH_DIALOGUE_LEADER_RE.sub(r"\1- ", text)


def _parse_pattern_set(pattern_set: str) -> tuple[str, ...]:
    return tuple(segment.strip() for segment in pattern_set.split("||") if segment.strip())


@lru_cache(maxsize=16)
def _compile_copy_artifact_patterns(pattern_set: str) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(pattern, re.IGNORECASE) for pattern in _parse_pattern_set(pattern_set))


def remove_copy_artifacts(text: str, pattern_set: str | None = None) -> str:
    resolved_pattern_set = pattern_set if pattern_set is not None else get_settings().copy_artifact_patterns
    if not resolved_pattern_set.strip():
        return text

    compiled_patterns = _compile_copy_artifact_patterns(resolved_pattern_set)
    lines = text.split("\n")
    filtered_lines: list[str] = []
    for line in lines:
        if any(pattern.match(line) for pattern in compiled_patterns):
            continue
        filtered_lines.append(line)
    return "\n".join(filtered_lines)


def normalize_text(text: str) -> str:
    return normalize_text_with_warnings(text)[0]
