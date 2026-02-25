import re
import unicodedata

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


def normalize_ellipsis_variants(text: str) -> str:
    text = ELLIPSIS_UNICODE_RE.sub("...", text)
    text = ELLIPSIS_DOTTED_RE.sub("...", text)
    return text


def normalize_text(text: str) -> str:
    normalized = normalize_unicode_variants(text)
    normalized = normalize_quotes(normalized)
    normalized = normalize_ellipsis_variants(normalized)
    return normalize_whitespace(normalized)
