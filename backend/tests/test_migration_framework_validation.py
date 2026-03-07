import subprocess
import sys
from pathlib import Path

import pytest

from app.migration_framework_validation import (
    EXPECTED_NAMING_PATTERN,
    MigrationFrameworkValidationError,
    discover_migration_filenames,
    parse_migration_version,
    validate_migration_framework,
)

ROOT = Path(__file__).resolve().parents[2]
MIGRATION_DIR = ROOT / "backend" / "migrations"
RUNNER_SCRIPT_PATH = ROOT / "backend" / "scripts_run_migration.py"
VALIDATION_SCRIPT_PATH = ROOT / "backend" / "scripts_validate_migration_framework.py"


def test_unit_parse_migration_version_and_filename_rules() -> None:
    assert parse_migration_version("001_initial.sql") == 1
    assert parse_migration_version("013_add_run_status_lifecycle.sql") == 13

    with pytest.raises(MigrationFrameworkValidationError, match=EXPECTED_NAMING_PATTERN):
        parse_migration_version("13_add_run_status_lifecycle.sql")

    with pytest.raises(MigrationFrameworkValidationError, match=EXPECTED_NAMING_PATTERN):
        parse_migration_version("013-AddRunStatus.sql")


def test_integration_migration_framework_is_configured_with_contiguous_versions() -> None:
    stats = validate_migration_framework(MIGRATION_DIR, RUNNER_SCRIPT_PATH)
    assert stats["migration_count"] >= 1
    assert stats["latest_version"] == stats["migration_count"]
    assert stats["naming_pattern"] == EXPECTED_NAMING_PATTERN

    filenames = discover_migration_filenames(MIGRATION_DIR)
    assert filenames[0].startswith("001_")


def test_e2e_migration_framework_validation_cli_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATION_SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    assert "Migration framework validation succeeded" in result.stdout

