from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.migration_framework_validation import (  # noqa: E402
    MigrationFrameworkValidationError,
    validate_migration_framework,
)


def main() -> int:
    migration_dir = ROOT / "backend" / "migrations"
    runner_script_path = ROOT / "backend" / "scripts_run_migration.py"

    try:
        stats = validate_migration_framework(migration_dir, runner_script_path)
    except MigrationFrameworkValidationError as exc:
        print(f"Migration framework validation failed: {exc}")
        return 1

    print(
        "Migration framework validation succeeded with "
        f"{stats['migration_count']} migration(s), latest version {int(stats['latest_version']):03d}, "
        f"naming pattern {stats['naming_pattern']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

