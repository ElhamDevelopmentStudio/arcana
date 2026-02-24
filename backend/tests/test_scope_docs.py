import subprocess
import sys
from pathlib import Path

from app.scope_validation import extract_scope_section, load_and_parse_scope, parse_scope_lists

ROOT = Path(__file__).resolve().parents[2]
SRS_PATH = ROOT / "SRS.md"
DOCS_SCOPE_PATH = ROOT / "docs" / "scope.md"
VALIDATION_SCRIPT_PATH = ROOT / "backend" / "scripts_validate_scope.py"

EXPECTED_SCOPE = {
    "shall": [
        "ingest large novels (3,500+ chapters)",
        "normalize text and structure",
        "extract characters and build a character map",
        "support user review and overrides",
        "produce segmented text suitable for TTS (audiobook mode)",
        "generate multi-layer tags (speaker, type, emotion, tension, dominance contribution)",
        "output structured exports (JSON/CSV/time series)",
        "provide dashboards/visualizations (where enabled)",
    ],
    "shall_not": [
        "rewrite or generate new story text",
        "produce final audio output directly (optional integration later, but not required in v1)",
        "claim emotional labels are ground-truth",
        "require manual per-chapter labeling",
    ],
}


def test_unit_parse_scope_lists_extracts_shall_and_shall_not() -> None:
    sample = """
### 1.2 Scope
NIPE SHALL:
- do A
- do B
NIPE SHALL NOT:
- do C
"""
    parsed = parse_scope_lists(sample)
    assert parsed == {"shall": ["do A", "do B"], "shall_not": ["do C"]}


def test_unit_extract_scope_section_stops_at_next_h3() -> None:
    sample = """
# Title
### 1.2 Scope
NIPE SHALL:
- item
NIPE SHALL NOT:
- item2
### 1.3 Success Criteria (Product-Level)
Body text.
"""
    section = extract_scope_section(sample)
    assert "### 1.2 Scope" in section
    assert "### 1.3 Success Criteria" not in section


def test_integration_docs_scope_matches_srs_scope_lists() -> None:
    srs_scope = load_and_parse_scope(SRS_PATH, already_scope_section=False)
    docs_scope = load_and_parse_scope(DOCS_SCOPE_PATH, already_scope_section=True)
    assert docs_scope == srs_scope


def test_e2e_scope_validation_cli_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATION_SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    assert "Scope validation succeeded" in result.stdout


def test_regression_scope_snapshot() -> None:
    docs_scope = load_and_parse_scope(DOCS_SCOPE_PATH, already_scope_section=True)
    assert docs_scope == EXPECTED_SCOPE
