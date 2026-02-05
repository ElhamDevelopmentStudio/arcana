from __future__ import annotations

from pathlib import Path
import re


REQUIRED_PARALLEL_RULE = "Implement backend and frontend in parallel for each feature slice"
REQUIRED_ACCEPTANCE_NOTES_RULE = "Every feature slice must include backend + frontend acceptance notes"
REQUIRED_DEFERRED_FE_TASK_RULE = "When backend work ships without UI in the same slice, a deferred FE task ID is mandatory"
REQUIRED_DONE_RULE = "For user-visible behavior, API + frontend UX + integration evidence are all present"
REQUIRED_FRONTEND_SECTION_PATTERN = re.compile(r"(?m)^##\s+13\.\s+Frontend Parallel Delivery Track\s+")
REQUIRED_PLAYWRIGHT_SUBSECTION_PATTERN = re.compile(r"(?m)^###\s+13\.10\s+Playwright Visual and E2E Suite")

TASK_PATTERN = re.compile(r"(?m)^\s*-\s+\[[ x]\]\s+\[(FE|PW)-(\d{3})\]")
MIN_FE_TASKS = 80
MIN_PW_TASKS = 15


class ChecklistFrontendCoverageValidationError(ValueError):
    pass


def extract_frontend_task_ids(markdown: str, prefix: str) -> list[int]:
    ids: list[int] = []
    for task_prefix, raw_id in TASK_PATTERN.findall(markdown):
        if task_prefix == prefix:
            ids.append(int(raw_id))
    return ids


def validate_checklist_frontend_coverage(path: Path) -> dict[str, int]:
    markdown = path.read_text(encoding="utf-8")

    if REQUIRED_PARALLEL_RULE not in markdown:
        raise ChecklistFrontendCoverageValidationError("Checklist is missing required backend/frontend parallel delivery rule.")

    if REQUIRED_ACCEPTANCE_NOTES_RULE not in markdown:
        raise ChecklistFrontendCoverageValidationError(
            "Checklist is missing required backend+frontend acceptance-notes policy."
        )

    if REQUIRED_DEFERRED_FE_TASK_RULE not in markdown:
        raise ChecklistFrontendCoverageValidationError(
            "Checklist is missing required deferred FE task ID policy."
        )

    if REQUIRED_DONE_RULE not in markdown:
        raise ChecklistFrontendCoverageValidationError("Checklist is missing required user-visible API+frontend DoD rule.")

    if REQUIRED_FRONTEND_SECTION_PATTERN.search(markdown) is None:
        raise ChecklistFrontendCoverageValidationError("Checklist is missing the frontend parallel delivery track section.")

    if REQUIRED_PLAYWRIGHT_SUBSECTION_PATTERN.search(markdown) is None:
        raise ChecklistFrontendCoverageValidationError("Checklist is missing the Playwright visual/e2e subsection.")

    fe_ids = extract_frontend_task_ids(markdown, "FE")
    pw_ids = extract_frontend_task_ids(markdown, "PW")

    if len(fe_ids) < MIN_FE_TASKS:
        raise ChecklistFrontendCoverageValidationError(
            f"Checklist must include at least {MIN_FE_TASKS} FE tasks; found {len(fe_ids)}."
        )

    if len(pw_ids) < MIN_PW_TASKS:
        raise ChecklistFrontendCoverageValidationError(
            f"Checklist must include at least {MIN_PW_TASKS} PW tasks; found {len(pw_ids)}."
        )

    if len(set(fe_ids)) != len(fe_ids):
        raise ChecklistFrontendCoverageValidationError("Duplicate FE task IDs detected.")

    if len(set(pw_ids)) != len(pw_ids):
        raise ChecklistFrontendCoverageValidationError("Duplicate PW task IDs detected.")

    return {
        "fe_tasks": len(fe_ids),
        "pw_tasks": len(pw_ids),
    }
