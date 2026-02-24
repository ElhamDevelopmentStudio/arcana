from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.glossary_validation import load_and_parse_glossary  # noqa: E402
from app.glossary_terms import glossary_term_pairs  # noqa: E402


def main() -> int:
    srs_path = ROOT / "SRS.md"
    glossary_path = ROOT / "docs" / "glossary.md"

    srs_terms = load_and_parse_glossary(srs_path)
    docs_terms = load_and_parse_glossary(glossary_path)
    constant_terms = glossary_term_pairs()

    if srs_terms != docs_terms:
        print("Glossary validation failed: docs/glossary.md does not exactly match SRS.md glossary section.")
        print(f"SRS terms: {len(srs_terms)}")
        print(f"Docs terms: {len(docs_terms)}")
        return 1
    if srs_terms != constant_terms:
        print("Glossary validation failed: app/glossary_terms.py does not exactly match SRS.md glossary section.")
        print(f"SRS terms: {len(srs_terms)}")
        print(f"Constant terms: {len(constant_terms)}")
        return 1

    print(f"Glossary validation succeeded with {len(docs_terms)} terms across SRS/docs/constants.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
