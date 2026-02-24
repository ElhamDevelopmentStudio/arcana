from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.success_criteria_validation import (  # noqa: E402
    load_doc_success_criteria,
    load_srs_success_criteria,
)


def main() -> int:
    srs_path = ROOT / "SRS.md"
    checklist_path = ROOT / "docs" / "shadow_slave_success_checklist.md"

    srs_items = load_srs_success_criteria(srs_path)
    doc_pairs, doc_checklist_ids = load_doc_success_criteria(checklist_path)

    doc_map_ids = [pair[0] for pair in doc_pairs]
    doc_map_items = [pair[1] for pair in doc_pairs]

    expected_ids = [f"SC-{index:03d}" for index in range(1, len(srs_items) + 1)]

    if doc_map_ids != expected_ids:
        print("Success checklist validation failed: SC IDs in criteria map are not sequential and complete.")
        print(f"Expected IDs: {expected_ids}")
        print(f"Actual IDs: {doc_map_ids}")
        return 1

    if doc_map_items != srs_items:
        print("Success checklist validation failed: checklist criteria map does not match SRS §1.3 criteria.")
        print(f"SRS criteria count: {len(srs_items)}")
        print(f"Checklist criteria count: {len(doc_map_items)}")
        return 1

    if doc_checklist_ids != expected_ids:
        print("Success checklist validation failed: per-run checklist IDs do not match criteria map IDs.")
        print(f"Expected checklist IDs: {expected_ids}")
        print(f"Actual checklist IDs: {doc_checklist_ids}")
        return 1

    print(f"Success checklist validation succeeded with {len(srs_items)} criteria and matching run checklist IDs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
