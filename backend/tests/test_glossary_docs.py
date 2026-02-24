import subprocess
import sys
from pathlib import Path

from app.glossary_terms import GLOSSARY_BY_NAME, GLOSSARY_TERMS, GlossaryTermKey, glossary_term_pairs
from app.glossary_validation import extract_glossary_section, load_and_parse_glossary, parse_glossary_terms

ROOT = Path(__file__).resolve().parents[2]
SRS_PATH = ROOT / "SRS.md"
DOCS_GLOSSARY_PATH = ROOT / "docs" / "glossary.md"
VALIDATION_SCRIPT_PATH = ROOT / "backend" / "scripts_validate_glossary.py"

EXPECTED_GLOSSARY_TERMS = [
    (
        "Novel",
        "A long-form narrative text (web novel, book, serialized fiction).",
    ),
    ("Corpus", "Full text of a novel (all chapters)."),
    ("Chapter Unit", "A single chapter (index + title + content)."),
    (
        "Segment",
        "A short, digestible chunk of text intended for analysis and TTS feeding (target: ≤ 255 characters for audiobook mode).",
    ),
    (
        "Sub-segment",
        "A smaller unit inside a segment representing a detected shift (emotion shift, narration/dialogue shift, thought shift).",
    ),
    (
        "Character Map",
        "User-editable table mapping `name -> verbalized form -> gender`, plus aliases and metadata.",
    ),
    (
        "Verbalized Form",
        "Pronunciation-oriented representation for TTS (e.g., “Aegis” → “EE-jis”).",
    ),
    (
        "Voice Map",
        "Mapping from character (or gender/default) to TTS voice profile identifiers.",
    ),
    (
        "Tagging",
        "Assigning labels and scores to segments/sub-segments (emotion, speaker, type, tension contribution).",
    ),
    ("Confidence", "A numeric score representing reliability of a label (0.0–1.0)."),
    (
        "Evidence Trace",
        "Stored pointers to text spans and feature signals that justified a label.",
    ),
    (
        "Mode",
        "One of the product workflows (Audiobook / Academic / Author / Other).",
    ),
]


def test_unit_parse_glossary_terms_extracts_entries() -> None:
    sample_section = """
## 0. Glossary
- **Novel**: A long-form narrative text.
- **Corpus**: Full text.
"""
    parsed = parse_glossary_terms(sample_section)
    assert parsed == [
        ("Novel", "A long-form narrative text."),
        ("Corpus", "Full text."),
    ]


def test_unit_extract_glossary_section_stops_at_next_h2() -> None:
    sample_doc = """
# Title
## 0. Glossary
- **Novel**: Example.

## 1. Introduction
Body text.
"""
    section = extract_glossary_section(sample_doc)
    assert "## 0. Glossary" in section
    assert "## 1. Introduction" not in section


def test_unit_glossary_constants_are_well_formed() -> None:
    assert len(GLOSSARY_TERMS) == len(GlossaryTermKey)
    assert len(GLOSSARY_BY_NAME) == len(GlossaryTermKey)
    for term in GLOSSARY_TERMS:
        assert isinstance(term.key, GlossaryTermKey)
        assert term.key.value in GLOSSARY_BY_NAME
        assert GLOSSARY_BY_NAME[term.key.value] == term.definition


def test_integration_docs_glossary_matches_srs_glossary_terms() -> None:
    srs_terms = load_and_parse_glossary(SRS_PATH)
    docs_terms = load_and_parse_glossary(DOCS_GLOSSARY_PATH)
    assert docs_terms == srs_terms


def test_integration_shared_constants_match_docs_glossary_terms() -> None:
    docs_terms = load_and_parse_glossary(DOCS_GLOSSARY_PATH)
    assert glossary_term_pairs() == docs_terms


def test_e2e_glossary_validation_cli_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATION_SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    assert "Glossary validation succeeded" in result.stdout


def test_regression_glossary_term_snapshot() -> None:
    docs_terms = load_and_parse_glossary(DOCS_GLOSSARY_PATH)
    assert docs_terms == EXPECTED_GLOSSARY_TERMS


def test_regression_shared_glossary_constant_snapshot() -> None:
    assert glossary_term_pairs() == EXPECTED_GLOSSARY_TERMS
