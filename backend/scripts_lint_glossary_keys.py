from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.glossary_key_lint import docs_glossary_keys, missing_glossary_keys, required_glossary_keys  # noqa: E402


def main() -> int:
    glossary_path = ROOT / "docs" / "glossary.md"

    required = required_glossary_keys()
    present = docs_glossary_keys(glossary_path)
    missing = missing_glossary_keys(required, present)

    if missing:
        print("Glossary key lint failed: docs/glossary.md is missing required glossary keys.")
        print("Missing keys:")
        for key in missing:
            print(f"- {key}")
        return 1

    print(f"Glossary key lint succeeded with {len(present)} keys present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
