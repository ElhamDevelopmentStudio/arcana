from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.persona_flow_validation import PersonaFlowValidationError, validate_persona_flows  # noqa: E402


def main() -> int:
    srs_path = ROOT / "SRS.md"
    flow_doc_path = ROOT / "docs" / "persona_end_to_end_flows.md"

    try:
        stats = validate_persona_flows(srs_path, flow_doc_path)
    except PersonaFlowValidationError as exc:
        print(f"Persona flow validation failed: {exc}")
        return 1

    print(
        "Persona flow validation succeeded with "
        f"{stats['flows']} flows for {stats['personas']} personas and {stats['total_steps']} total steps."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
