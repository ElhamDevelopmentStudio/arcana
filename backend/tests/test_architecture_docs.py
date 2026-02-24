import subprocess
import sys
from pathlib import Path
import re

from app.architecture_validation import (
    extract_h2_section,
    load_architecture_sections,
    parse_bullets,
    validate_architecture_determinism,
)

ROOT = Path(__file__).resolve().parents[2]
SRS_PATH = ROOT / "SRS.md"
ARCHITECTURE_DOC_PATH = ROOT / "docs" / "architecture.md"
VALIDATION_SCRIPT_PATH = ROOT / "backend" / "scripts_validate_architecture.py"

EXPECTED_OBJECTIVE = "The system is deterministic enough to reproduce results with pinned configuration."

EXPECTED_GUARDRAILS = [
    "Run configuration must be persisted in a reusable snapshot.",
    "Processing order must be stable for the same input and configuration.",
    "Export identity and ordering must remain stable across equivalent reruns.",
]


def test_unit_extract_h2_section_stops_at_next_h2() -> None:
    sample = """
## Architecture Objectives
- a
## Determinism Baseline Guardrails
- b
"""
    section = extract_h2_section(sample, heading_pattern=re.compile(r"(?m)^##\s+Architecture Objectives\s*$"))
    assert "- a" in section
    assert "- b" not in section


def test_unit_parse_bullets_extracts_lines() -> None:
    sample = """
- one
- two
"""
    bullets = parse_bullets(sample)
    assert bullets == ["one", "two"]


def test_integration_architecture_contains_determinism_objective_and_guardrails() -> None:
    stats = validate_architecture_determinism(SRS_PATH, ARCHITECTURE_DOC_PATH)
    objectives, guardrails = load_architecture_sections(ARCHITECTURE_DOC_PATH)
    assert EXPECTED_OBJECTIVE in objectives
    assert guardrails == EXPECTED_GUARDRAILS
    assert stats["guardrails"] >= 3


def test_e2e_architecture_validation_cli_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATION_SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    assert "Architecture validation succeeded" in result.stdout


def test_regression_architecture_guardrails_snapshot() -> None:
    _, guardrails = load_architecture_sections(ARCHITECTURE_DOC_PATH)
    assert guardrails == EXPECTED_GUARDRAILS
