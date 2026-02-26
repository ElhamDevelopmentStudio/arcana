from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.llm_provider_adapter_contributor_doc_validation import (  # noqa: E402
    LLMProviderAdapterContributorDocValidationError,
    validate_llm_provider_adapter_guide,
)


def main() -> int:
    doc_path = ROOT / "docs" / "contributor_add_llm_provider_adapter.md"

    try:
        stats = validate_llm_provider_adapter_guide(doc_path)
    except LLMProviderAdapterContributorDocValidationError as exc:
        print(f"Contributor LLM provider adapter guide validation failed: {exc}")
        return 1

    print(
        "Contributor LLM provider adapter guide validation succeeded with "
        f"{stats['steps']} steps and {stats['required_fields']} required fields per step."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
