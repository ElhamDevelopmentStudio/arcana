import subprocess
import sys
from pathlib import Path

from app.mode_enum_validation import (
    extract_mode_001_section,
    parse_mode_contract,
    validate_mode_001_contract,
)
from app.modes import MODE_VALUES
from app.schemas import RunCreateRequest

ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = ROOT / "docs" / "system_modes.md"
VALIDATION_SCRIPT_PATH = ROOT / "backend" / "scripts_validate_mode_enum.py"

EXPECTED_MODE_VALUES = ["audiobook", "academic", "author", "custom"]


def test_unit_extract_and_parse_mode_contract() -> None:
    sample = """
## MODE-001 System Mode Enum Contract
- allowed_modes: audiobook, academic, author, custom
- default_mode: audiobook
- run_config_path: runs.config_json.mode
"""
    section = extract_mode_001_section(sample)
    fields = parse_mode_contract(section)
    assert fields["default_mode"] == "audiobook"
    assert fields["run_config_path"] == "runs.config_json.mode"


def test_integration_mode_contract_and_schema_modes_align() -> None:
    stats = validate_mode_001_contract(DOC_PATH)
    assert stats["mode_count"] == len(MODE_VALUES)

    for mode in MODE_VALUES:
        payload = RunCreateRequest(
            mode=f" {mode.upper()} ",
            max_segment_chars=120,
            llm_enabled=False,
            provider_name="openrouter",
            max_calls_per_day=5,
        )
        assert payload.mode == mode


def test_e2e_mode_enum_validation_cli_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATION_SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    assert "Mode enum validation succeeded" in result.stdout


def test_regression_mode_enum_snapshot() -> None:
    assert list(MODE_VALUES) == EXPECTED_MODE_VALUES
