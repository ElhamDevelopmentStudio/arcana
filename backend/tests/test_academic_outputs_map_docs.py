import subprocess
import sys
from pathlib import Path

from app.academic_output_map_validation import (
    REQUIRED_FORMAT_COVERAGE,
    extract_use_003_section,
    parse_output_items,
    validate_use_003_mapping,
)

ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = ROOT / "docs" / "academic_outputs_export_mapping.md"
VALIDATION_SCRIPT_PATH = ROOT / "backend" / "scripts_validate_academic_outputs_map.py"

EXPECTED_OUTPUT_IDS = ["AO-001", "AO-002", "AO-003", "AO-004", "AO-005", "AO-006"]


def test_unit_extract_and_parse_outputs() -> None:
    sample = """
## USE-003 Academic Outputs and Export Formats Mapping
### Output 01: Item A
- output_id: AO-001
- source_flow_id: FLOW-ACADEMIC-001
- output_name: item_a
- purpose: Purpose A
- export_formats: json, csv
- expected_consumer: consumer_a
### Output 02: Item B
- output_id: AO-002
- source_flow_id: FLOW-ACADEMIC-001
- output_name: item_b
- purpose: Purpose B
- export_formats: graph_json
- expected_consumer: consumer_b
"""
    section = extract_use_003_section(sample)
    items = parse_output_items(section)
    assert len(items) == 2
    assert items[0]["number"] == 1
    assert items[1]["fields"]["output_id"] == "AO-002"


def test_integration_use_003_mapping_contains_required_formats_and_outputs() -> None:
    stats = validate_use_003_mapping(DOC_PATH)
    assert stats["outputs"] >= 6
    assert stats["format_coverage"] >= len(REQUIRED_FORMAT_COVERAGE)


def test_e2e_academic_outputs_mapping_validation_cli_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATION_SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    assert "Academic outputs mapping validation succeeded" in result.stdout


def test_regression_output_id_snapshot() -> None:
    markdown = DOC_PATH.read_text(encoding="utf-8")
    items = parse_output_items(extract_use_003_section(markdown))
    output_ids = [item["fields"]["output_id"] for item in items]
    assert output_ids == EXPECTED_OUTPUT_IDS
