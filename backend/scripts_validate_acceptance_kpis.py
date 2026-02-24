from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.acceptance_kpi_validation import (  # noqa: E402
    AcceptanceKPIValidationError,
    validate_kpi_001_against_srs,
    validate_kpi_002_against_srs,
)


def main() -> int:
    srs_path = ROOT / "SRS.md"
    kpi_doc_path = ROOT / "docs" / "acceptance_kpis.md"

    try:
        kpi_001 = validate_kpi_001_against_srs(srs_path, kpi_doc_path)
        kpi_002 = validate_kpi_002_against_srs(srs_path, kpi_doc_path)
    except AcceptanceKPIValidationError as exc:
        print(f"Acceptance KPI validation failed: {exc}")
        return 1

    print(
        "Acceptance KPI validation succeeded for "
        f"{kpi_001['linked_success_criterion']} and {kpi_002['linked_success_criterion']} "
        f"with {len(kpi_001)} and {len(kpi_002)} required fields."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
