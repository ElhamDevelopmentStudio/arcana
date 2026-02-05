from __future__ import annotations

import json
from pathlib import Path

from scripts_validate_unit_coverage_thresholds import run_validation


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_unit_coverage_threshold_validator_passes_for_aggregated_modules(tmp_path: Path) -> None:
    coverage_path = tmp_path / "coverage.json"
    thresholds_path = tmp_path / "thresholds.json"

    _write_json(
        coverage_path,
        {
            "files": {
                "app/main.py": {"summary": {"covered_lines": 30, "num_statements": 50}},
                "app/services/export.py": {"summary": {"covered_lines": 40, "num_statements": 50}},
                "app/services/pipeline.py": {"summary": {"covered_lines": 45, "num_statements": 50}},
            }
        },
    )
    _write_json(
        thresholds_path,
        {
            "modules": {
                "app/main.py": 50,
                "app/services/": 80,
            }
        },
    )

    results = run_validation(
        coverage_json_path=coverage_path,
        thresholds_path=thresholds_path,
    )

    by_module = {str(result["module"]): result for result in results}
    assert by_module["app/main.py"]["passed"] is True
    assert by_module["app/main.py"]["coverage_percent"] == 60.0
    assert by_module["app/services/"]["passed"] is True
    assert by_module["app/services/"]["coverage_percent"] == 85.0
    assert len(by_module["app/services/"]["matched_files"]) == 2


def test_unit_coverage_threshold_validator_fails_for_missing_or_low_modules(tmp_path: Path) -> None:
    coverage_path = tmp_path / "coverage.json"
    thresholds_path = tmp_path / "thresholds.json"

    _write_json(
        coverage_path,
        {
            "files": {
                "/tmp/work/backend/app/services/export.py": {"summary": {"covered_lines": 22, "num_statements": 50}},
                "/tmp/work/backend/app/schemas.py": {"summary": {"covered_lines": 70, "num_statements": 100}},
            }
        },
    )
    _write_json(
        thresholds_path,
        {
            "modules": {
                "app/services/": 50,
                "app/nonexistent/": 10,
            }
        },
    )

    results = run_validation(
        coverage_json_path=coverage_path,
        thresholds_path=thresholds_path,
    )
    by_module = {str(result["module"]): result for result in results}

    assert by_module["app/services/"]["passed"] is False
    assert by_module["app/services/"]["reason"] == "below_threshold"
    assert by_module["app/services/"]["coverage_percent"] == 44.0

    assert by_module["app/nonexistent/"]["passed"] is False
    assert by_module["app/nonexistent/"]["reason"] == "no_matching_files"
    assert by_module["app/nonexistent/"]["total_lines"] == 0
