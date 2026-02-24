from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.architecture_validation import ArchitectureValidationError, validate_architecture_determinism  # noqa: E402


def main() -> int:
    srs_path = ROOT / "SRS.md"
    architecture_path = ROOT / "docs" / "architecture.md"

    try:
        stats = validate_architecture_determinism(srs_path, architecture_path)
    except ArchitectureValidationError as exc:
        print(f"Architecture validation failed: {exc}")
        return 1

    print(
        "Architecture validation succeeded with "
        f"{stats['objectives']} objective bullets and {stats['guardrails']} determinism guardrails."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
