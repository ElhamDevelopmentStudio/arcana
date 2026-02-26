import subprocess
import sys
from pathlib import Path

from app.llm_provider_adapter_contributor_doc_validation import (
    REQUIRED_STEP_TITLES,
    extract_llm_provider_adapter_section,
    parse_step_items,
    validate_llm_provider_adapter_guide,
)

ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = ROOT / "docs" / "contributor_add_llm_provider_adapter.md"
VALIDATION_SCRIPT_PATH = ROOT / "backend" / "scripts_validate_llm_provider_adapter_contributor_doc.py"

EXPECTED_STEP_TITLES = [
    "Register provider metadata and adapter hooks",
    "Extend settings and environment configuration",
    "Wire run-level config propagation and API contracts",
    "Cover quota, failover, toggles, and audit behavior",
    "Add backend + frontend regression coverage",
    "Update contributor docs and run local smoke",
]


def test_unit_extract_and_parse_llm_provider_adapter_steps() -> None:
    sample = """
## Contributor Guide: How to add a new LLM provider adapter
### Step 1: Register provider metadata and adapter hooks
- objective: Register metadata.
- files: backend/app/services/llm_router.py
- checks: registration tests
### Step 2: Extend settings and environment configuration
- objective: Add env settings.
- files: backend/app/config.py
- checks: settings parsing tests
"""
    section = extract_llm_provider_adapter_section(sample)
    items = parse_step_items(section)
    assert len(items) == 2
    assert items[0]["number"] == 1
    assert items[1]["title"] == "Extend settings and environment configuration"


def test_integration_llm_provider_adapter_doc_has_required_steps() -> None:
    stats = validate_llm_provider_adapter_guide(DOC_PATH)
    assert stats["steps"] >= len(REQUIRED_STEP_TITLES)
    assert stats["required_fields"] == 3


def test_e2e_llm_provider_adapter_doc_validation_cli_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATION_SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    assert "Contributor LLM provider adapter guide validation succeeded" in result.stdout


def test_regression_llm_provider_adapter_step_titles_snapshot() -> None:
    markdown = DOC_PATH.read_text(encoding="utf-8")
    items = parse_step_items(extract_llm_provider_adapter_section(markdown))
    titles = [str(item["title"]) for item in items]
    assert titles == EXPECTED_STEP_TITLES
