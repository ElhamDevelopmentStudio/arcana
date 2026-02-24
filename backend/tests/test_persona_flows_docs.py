import subprocess
import sys
from pathlib import Path

from app.persona_flow_validation import (
    extract_srs_persona_section,
    parse_doc_fields,
    parse_doc_persona_sections,
    parse_doc_steps,
    parse_srs_persona_names,
    validate_persona_flows,
)

ROOT = Path(__file__).resolve().parents[2]
SRS_PATH = ROOT / "SRS.md"
DOC_PATH = ROOT / "docs" / "persona_end_to_end_flows.md"
VALIDATION_SCRIPT_PATH = ROOT / "backend" / "scripts_validate_persona_flows.py"

EXPECTED_PERSONAS = [
    "Audiobook Creator (TTS)",
    "Academic Researcher",
    "Fiction Author",
    "Community Reader",
]

EXPECTED_FLOW_IDS = [
    "FLOW-AUDIOBOOK-001",
    "FLOW-ACADEMIC-001",
    "FLOW-AUTHOR-001",
    "FLOW-COMMUNITY-001",
]


def test_unit_parse_srs_persona_names_extracts_expected_list() -> None:
    sample = """
### 2.1 Personas
1. **Audiobook Creator (TTS)**
2. **Academic Researcher**
3. **Fiction Author**
4. **Community Reader**
### 2.2 Primary Use Cases
"""
    names = parse_srs_persona_names(extract_srs_persona_section(sample))
    assert names == EXPECTED_PERSONAS


def test_unit_parse_doc_section_fields_and_steps() -> None:
    sample = """
## Persona A End-to-End Flow
- flow_id: FLOW-A-001
- objective: Test objective.
- expected_outcome: Test outcome.
1. Step one.
2. Step two.
"""
    sections = parse_doc_persona_sections(sample)
    section_text = sections["Persona A"]
    fields = parse_doc_fields(section_text)
    steps = parse_doc_steps(section_text)

    assert fields["flow_id"] == "FLOW-A-001"
    assert fields["objective"] == "Test objective."
    assert fields["expected_outcome"] == "Test outcome."
    assert steps == ["Step one.", "Step two."]


def test_integration_persona_flow_doc_matches_srs_personas() -> None:
    stats = validate_persona_flows(SRS_PATH, DOC_PATH)
    assert stats["personas"] == 4
    assert stats["flows"] == 4
    assert stats["total_steps"] >= 24


def test_e2e_persona_flow_validation_cli_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATION_SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    assert "Persona flow validation succeeded" in result.stdout


def test_regression_persona_names_and_flow_ids_snapshot() -> None:
    srs_markdown = SRS_PATH.read_text(encoding="utf-8")
    doc_markdown = DOC_PATH.read_text(encoding="utf-8")

    persona_names = parse_srs_persona_names(extract_srs_persona_section(srs_markdown))
    sections = parse_doc_persona_sections(doc_markdown)
    flow_ids = [parse_doc_fields(sections[name])["flow_id"] for name in persona_names]

    assert persona_names == EXPECTED_PERSONAS
    assert flow_ids == EXPECTED_FLOW_IDS
