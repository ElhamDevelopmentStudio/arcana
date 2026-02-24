import subprocess
import sys
from pathlib import Path

from app.audiobook_flow_validation import (
    REQUIRED_ENDPOINTS,
    extract_use_002_section,
    parse_steps,
    validate_use_002_mapping,
)

ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = ROOT / "docs" / "audiobook_ui_api_mapping.md"
VALIDATION_SCRIPT_PATH = ROOT / "backend" / "scripts_validate_audiobook_flow_map.py"

EXPECTED_STEP_TITLES = [
    "Create Project",
    "Upload Novel TXT",
    "Import Character Map",
    "Configure Voices",
    "Start Audiobook Pipeline Run",
    "Monitor Run Status",
    "Download TTS-Ready Export",
]


def test_unit_extract_use_002_section_and_parse_steps() -> None:
    sample = """
## USE-002 Audiobook Flow Mapping
### Step 01: A
- ui_screen: Screen A
- user_action: Do A
- api_endpoint: POST /api/a
- expected_outcome: Done A
### Step 02: B
- ui_screen: Screen B
- user_action: Do B
- api_endpoint: GET /api/b
- expected_outcome: Done B
"""
    section = extract_use_002_section(sample)
    steps = parse_steps(section)
    assert len(steps) == 2
    assert steps[0]["number"] == 1
    assert steps[1]["number"] == 2
    assert steps[0]["fields"]["api_endpoint"] == "POST /api/a"


def test_integration_mapping_contains_expected_step_titles_and_endpoints() -> None:
    markdown = DOC_PATH.read_text(encoding="utf-8")
    steps = parse_steps(extract_use_002_section(markdown))
    titles = [step["title"] for step in steps]
    endpoints = [step["fields"]["api_endpoint"] for step in steps]

    assert titles == EXPECTED_STEP_TITLES
    assert endpoints == REQUIRED_ENDPOINTS


def test_e2e_audiobook_flow_mapping_validation_cli_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATION_SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    assert "Audiobook flow mapping validation succeeded" in result.stdout


def test_regression_use_002_mapping_snapshot() -> None:
    stats = validate_use_002_mapping(DOC_PATH)
    assert stats == {"steps": 7, "endpoints": 7}
