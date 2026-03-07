from __future__ import annotations

from pathlib import Path
import re


REQUIRED_PATTERN_MAP: dict[str, re.Pattern[str]] = {
    "backend_api_change_declaration": re.compile(
        r"(?m)^-\s+\[\s\]\s+This PR changes backend/API contracts or payloads\.\s*$"
    ),
    "frontend_impact_review_checkbox": re.compile(
        r"(?m)^-\s+\[\s\]\s+I reviewed downstream frontend impact for any backend/API changes\.\s*$"
    ),
    "paired_frontend_impact_heading": re.compile(
        r"(?m)^##\s+Paired frontend impact \(required for backend/API changes\)\s*$"
    ),
    "frontend_impact_summary_field": re.compile(r"(?m)^-\s+Frontend impact summary:\s*$"),
    "related_fe_task_ids_field": re.compile(r"(?m)^-\s+Related FE task ID\(s\):\s*$"),
    "deferred_fe_task_id_field": re.compile(
        r"(?m)^-\s+Deferred FE task ID \(if backend ships without UI\):\s*$"
    ),
}


class PRTemplateFrontendImpactValidationError(ValueError):
    pass


def validate_pr_template_frontend_impact(path: Path) -> dict[str, int]:
    markdown = path.read_text(encoding="utf-8")

    missing = [
        key
        for key, pattern in REQUIRED_PATTERN_MAP.items()
        if pattern.search(markdown) is None
    ]
    if missing:
        raise PRTemplateFrontendImpactValidationError(
            "PR template is missing required frontend-impact entries: " + ", ".join(sorted(missing))
        )

    return {
        "required_entries": len(REQUIRED_PATTERN_MAP),
    }
