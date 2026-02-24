import subprocess
import sys
from pathlib import Path

from app.glossary_key_lint import docs_glossary_keys, missing_glossary_keys, required_glossary_keys

ROOT = Path(__file__).resolve().parents[2]
DOCS_GLOSSARY_PATH = ROOT / "docs" / "glossary.md"
LINT_SCRIPT_PATH = ROOT / "backend" / "scripts_lint_glossary_keys.py"

EXPECTED_GLOSSARY_KEYS = [
    "Chapter Unit",
    "Character Map",
    "Confidence",
    "Corpus",
    "Evidence Trace",
    "Mode",
    "Novel",
    "Segment",
    "Sub-segment",
    "Tagging",
    "Verbalized Form",
    "Voice Map",
]


def test_unit_missing_glossary_keys_detects_difference() -> None:
    required = {"Novel", "Corpus", "Mode"}
    present = {"Novel", "Corpus"}
    assert missing_glossary_keys(required, present) == ["Mode"]


def test_integration_docs_glossary_contains_all_required_keys() -> None:
    required = required_glossary_keys()
    present = docs_glossary_keys(DOCS_GLOSSARY_PATH)
    assert missing_glossary_keys(required, present) == []


def test_e2e_glossary_key_lint_cli_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, str(LINT_SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    assert "Glossary key lint succeeded" in result.stdout


def test_regression_glossary_required_key_snapshot() -> None:
    assert sorted(required_glossary_keys()) == EXPECTED_GLOSSARY_KEYS
