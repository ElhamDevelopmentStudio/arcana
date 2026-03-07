from __future__ import annotations

import html
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import requests
from requests.exceptions import RequestException, Timeout

from app.services.character_extraction import CandidateEvidence, extract_character_candidates_from_texts


MAX_TEXT_LENGTH = 200_000
_DEFAULT_TIMEOUT_SECONDS = 8


@dataclass(frozen=True)
class ScrapeConfig:
    timeout_seconds: int = _DEFAULT_TIMEOUT_SECONDS
    allowed_schemes: tuple[str, ...] = ("http", "https")


_SCRIPT_STYLE_RE = re.compile(r"(?is)<(script|style)\b.*?</\1>", re.IGNORECASE)
_TAG_RE = re.compile(r"(?s)<[^>]+>")


def validate_scrape_url(raw_url: str) -> str:
    parsed = urlparse(raw_url.strip())
    if not parsed.scheme or parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError("source_url must use http or https scheme.")
    if not parsed.netloc:
        raise ValueError("source_url must include a valid hostname.")
    return raw_url.strip()


def _sanitize_html_to_text(html_payload: str) -> str:
    without_scripts = _SCRIPT_STYLE_RE.sub(" ", html_payload)
    without_tags = _TAG_RE.sub(" ", without_scripts)
    normalized = html.unescape(without_tags)
    return re.sub(r"\s+", " ", normalized).strip()


def fetch_scrape_text(url: str, config: ScrapeConfig | None = None) -> str:
    normalized_config = config or ScrapeConfig()
    try:
        response = requests.get(url, timeout=normalized_config.timeout_seconds, headers={"User-Agent": "NIPE-Scraper/1.0"})
    except Timeout as exc:
        raise ValueError("Timed out while trying to fetch source URL.") from exc
    except RequestException as exc:
        raise ValueError(f"Failed to fetch source URL: {exc}") from exc

    if response.status_code >= 400:
        raise ValueError(f"Source URL returned HTTP {response.status_code}.")

    text = response.text or ""
    if not text.strip():
        raise ValueError("Source URL returned empty response body.")

    return _sanitize_html_to_text(text)[:MAX_TEXT_LENGTH]


def extract_character_candidates_from_scrape_url(
    url: str, known_names: set[str] | None = None
) -> list[CandidateEvidence]:
    if not url.strip():
        raise ValueError("source_url must not be empty.")

    validated_url = validate_scrape_url(url)
    text = fetch_scrape_text(validated_url)
    candidates = extract_character_candidates_from_texts([text], known_names=known_names)
    return candidates
