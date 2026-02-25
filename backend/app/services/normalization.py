import re
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
    repaired, double_quote_events = _repair_straight_quote_type(text, '"')
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
    normalized = normalize_unicode_variants(text)
    normalized, repair_events = repair_quote_mismatch_with_metadata(normalized)
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

    normalized = normalize_quotes(normalized)
    normalized = normalize_ellipsis_variants(normalized)
    normalized = normalize_em_dash_dialogue_style(normalized)
    normalized = remove_copy_artifacts(normalized)
    return normalize_whitespace(normalized), warnings


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
