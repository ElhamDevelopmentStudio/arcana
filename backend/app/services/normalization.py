import re
import unicodedata

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

HORIZONTAL_WHITESPACE_RE = re.compile(r"[ \t\f\v]+")
THREE_OR_MORE_LINE_BREAKS_RE = re.compile(r"\n{3,}")


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.translate(UNICODE_SPACE_TRANSLATION)
    lines = [HORIZONTAL_WHITESPACE_RE.sub(" ", line).strip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = THREE_OR_MORE_LINE_BREAKS_RE.sub("\n\n", text)
    return text.strip()


def normalize_quotes(text: str) -> str:
    return text.translate(QUOTE_TRANSLATION)


def normalize_unicode_variants(text: str) -> str:
    return unicodedata.normalize("NFKC", text)


def normalize_text(text: str) -> str:
    return normalize_whitespace(normalize_quotes(normalize_unicode_variants(text)))
