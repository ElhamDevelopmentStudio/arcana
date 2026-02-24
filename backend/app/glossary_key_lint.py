from __future__ import annotations

from pathlib import Path

from app.glossary_terms import GLOSSARY_BY_NAME
from app.glossary_validation import load_and_parse_glossary


def required_glossary_keys() -> set[str]:
    return set(GLOSSARY_BY_NAME.keys())


def docs_glossary_keys(path: Path) -> set[str]:
    return {term for term, _definition in load_and_parse_glossary(path)}


def missing_glossary_keys(required: set[str], present: set[str]) -> list[str]:
    return sorted(required - present)
