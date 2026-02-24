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
