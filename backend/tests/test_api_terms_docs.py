import subprocess
import sys
from pathlib import Path

from app.api_terms_validation import load_and_parse_api_terms, parse_term_definition, parse_term_json_example
from app.glossary_terms import GLOSSARY_BY_NAME

ROOT = Path(__file__).resolve().parents[2]
DOCS_API_TERMS_PATH = ROOT / "docs" / "api_domain_terms.md"
VALIDATION_SCRIPT_PATH = ROOT / "backend" / "scripts_validate_api_terms.py"

EXPECTED_API_TERMS_SNAPSHOT = {
    "Novel": {
        "definition": "A long-form narrative text (web novel, book, serialized fiction).",
        "example": {
            "novel": {
                "project_id": 1,
                "title": "Shadow Slave",
                "source_format": "txt",
                "language": "en",
            }
        },
    },
    "Corpus": {
        "definition": "Full text of a novel (all chapters).",
        "example": {
            "corpus": {
                "project_id": 1,
                "chapter_count": 95,
                "chapters": [
                    {
                        "chapter_index": 1,
                        "chapter_title": "Chapter 1",
                        "char_count": 7812,
                    },
                    {
                        "chapter_index": 2,
                        "chapter_title": "Chapter 2",
                        "char_count": 7540,
                    },
                ],
            }
        },
    },
    "Chapter Unit": {
        "definition": "A single chapter (index + title + content).",
        "example": {
            "chapter_unit": {
                "project_id": 1,
                "chapter_id": 12,
                "chapter_index": 12,
                "chapter_title": "Chapter 12",
                "raw_text": "Original chapter text...",
                "normalized_text": "Normalized chapter text...",
            }
        },
    },
    "Segment": {
        "definition": "A short, digestible chunk of text intended for analysis and TTS feeding (target: ≤ 255 characters for audiobook mode).",
        "example": {
            "segment": {
                "chapter_id": 12,
                "segment_id": "12-004",
                "original_text": "\"I should have bought a piece of real meat instead.\"",
                "phonetic_text": "\"I should have bought a piece of real meat instead.\"",
                "type": "dialogue",
                "speaker": "unknown",
                "gender": "unknown",
                "voice_id": "narrator_default",
                "emotion_valence": 0.0,
                "emotion_intensity": 0.0,
                "confidence": {
                    "speaker": 0.2,
                    "emotion": 0.4,
                },
            }
        },
    },
    "Sub-segment": {
        "definition": "A smaller unit inside a segment representing a detected shift (emotion shift, narration/dialogue shift, thought shift).",
        "example": {
            "sub_segment": {
                "sub_segment_id": "12-004-01",
                "sub_segment_index": 1,
                "parent_project_id": 1,
                "parent_run_id": 7,
                "parent_chapter_id": 12,
                "parent_segment_id": "12-004",
                "parent_pointers": {
                    "project": "projects.id=1",
                    "chapter": "chapters.id=12",
                    "segment": "segments.segment_id=12-004",
                },
                "span_start_char": 0,
                "span_end_char": 24,
                "text": "\"Ah! So bitter!\"",
                "shift_type": "emotion_shift",
                "tags": {
                    "type": "dialogue",
                    "speaker": "unknown",
                    "emotion_primary": "frustration",
                },
                "confidence": {
                    "speaker": 0.2,
                    "emotion": 0.6,
                },
            }
        },
    },
    "Character Map": {
        "definition": "User-editable table mapping `name -> verbalized form -> gender`, plus aliases and metadata.",
        "example": {
            "character_map": {
                "minimum": {
                    "name": "Sunny",
                    "verbalized_form": "SUN-nee",
                    "gender": "male",
                },
                "expanded": {
                    "name": "Nephis",
                    "verbalized_form": "NEH-fiss",
                    "gender": "female",
                    "aliases": ["Changing Star", "Lady Nephis"],
                    "notes": "Main cast character",
                    "source": "user_import_csv",
                    "confidence": 0.98,
                    "voice_id": "voice_female_main_01",
                },
            }
        },
    },
    "Voice Map": {
        "definition": "Mapping from character (or gender/default) to TTS voice profile identifiers.",
        "example": {
            "voice_map": {
                "narrator_voice": "voice_narrator_default",
                "defaults": {
                    "male": "voice_male_default",
                    "female": "voice_female_default",
                    "neutral": "voice_neutral_default",
                    "unknown": "voice_unknown_default",
                },
                "character_overrides": {
                    "Sunny": "voice_male_main_01",
                    "Nephis": "voice_female_main_01",
                },
                "fallback_behavior": {
                    "resolution_order": [
                        "character_override",
                        "narrator_if_narration",
                        "gender_default",
                        "unknown_default",
                    ],
                    "notes": "If speaker is unresolved or gender is unavailable, use unknown default.",
                },
            }
        },
    },
}


def test_unit_parse_definition_and_json_example() -> None:
    sample = """
## Novel
Definition: Example definition.
```json
{"novel": {"project_id": 1}}
```
"""
    assert parse_term_definition(sample) == "Example definition."
    assert parse_term_json_example(sample) == {"novel": {"project_id": 1}}


def test_integration_api_terms_definitions_match_glossary() -> None:
    parsed = load_and_parse_api_terms(DOCS_API_TERMS_PATH)
    assert parsed["Novel"]["definition"] == GLOSSARY_BY_NAME["Novel"]
    assert parsed["Corpus"]["definition"] == GLOSSARY_BY_NAME["Corpus"]
    assert parsed["Chapter Unit"]["definition"] == GLOSSARY_BY_NAME["Chapter Unit"]
    assert parsed["Segment"]["definition"] == GLOSSARY_BY_NAME["Segment"]
    assert parsed["Sub-segment"]["definition"] == GLOSSARY_BY_NAME["Sub-segment"]
    assert parsed["Character Map"]["definition"] == GLOSSARY_BY_NAME["Character Map"]
    assert parsed["Voice Map"]["definition"] == GLOSSARY_BY_NAME["Voice Map"]


def test_e2e_api_terms_validation_cli_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATION_SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    assert "API terms validation succeeded" in result.stdout


def test_regression_api_terms_snapshot() -> None:
    parsed = load_and_parse_api_terms(DOCS_API_TERMS_PATH)
    assert parsed == EXPECTED_API_TERMS_SNAPSHOT
