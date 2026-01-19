from __future__ import annotations

from pathlib import Path
import re


MIGRATION_FILENAME_PATTERN = re.compile(r"^(?P<version>\d{3})_(?P<slug>[a-z0-9]+(?:_[a-z0-9]+)*)\.sql$")
EXPECTED_NAMING_PATTERN = "NNN_snake_case_description.sql"


class MigrationFrameworkValidationError(ValueError):
    pass


def discover_migration_filenames(migration_dir: Path) -> list[str]:
    if not migration_dir.exists() or not migration_dir.is_dir():
        raise MigrationFrameworkValidationError(
            f"Migration directory not found: {migration_dir}"
        )

    filenames = sorted(path.name for path in migration_dir.glob("*.sql"))
    if not filenames:
        raise MigrationFrameworkValidationError(
            f"No SQL migrations found in: {migration_dir}"
        )

    return filenames


def parse_migration_version(filename: str) -> int:
    match = MIGRATION_FILENAME_PATTERN.match(filename)
    if match is None:
        raise MigrationFrameworkValidationError(
            f"Invalid migration filename '{filename}'. Expected pattern: {EXPECTED_NAMING_PATTERN}"
        )
    return int(match.group("version"))


def validate_migration_framework(migration_dir: Path, runner_script_path: Path) -> dict[str, int | str]:
    if not runner_script_path.exists():
        raise MigrationFrameworkValidationError(
            f"Migration runner script not found: {runner_script_path}"
        )

    runner_script = runner_script_path.read_text(encoding="utf-8")
    if 'glob("*.sql")' not in runner_script:
        raise MigrationFrameworkValidationError(
            "Migration runner must discover SQL files via glob(\"*.sql\")."
        )
    if "sorted(" not in runner_script:
        raise MigrationFrameworkValidationError(
            "Migration runner must apply migrations in sorted order."
        )

    filenames = discover_migration_filenames(migration_dir)
    versions = [parse_migration_version(filename) for filename in filenames]
    expected_versions = list(range(1, len(versions) + 1))
    if versions != expected_versions:
        expected_sequence = ", ".join(f"{version:03d}" for version in expected_versions)
        actual_sequence = ", ".join(f"{version:03d}" for version in versions)
        raise MigrationFrameworkValidationError(
            "Migration versions must be contiguous from 001 with no gaps. "
            f"Expected sequence: [{expected_sequence}] Actual sequence: [{actual_sequence}]"
        )

    return {
        "migration_count": len(versions),
        "latest_version": versions[-1],
        "naming_pattern": EXPECTED_NAMING_PATTERN,
    }

