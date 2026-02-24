from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.audiobook_flow_validation import AudiobookFlowValidationError, validate_use_002_mapping  # noqa: E402


def main() -> int:
    mapping_path = ROOT / "docs" / "audiobook_ui_api_mapping.md"

    try:
        stats = validate_use_002_mapping(mapping_path)
    except AudiobookFlowValidationError as exc:
        print(f"Audiobook flow mapping validation failed: {exc}")
        return 1

    print(
        "Audiobook flow mapping validation succeeded with "
        f"{stats['steps']} UI/API steps and {stats['endpoints']} endpoint mappings."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
