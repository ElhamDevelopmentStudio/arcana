from __future__ import annotations

from pathlib import Path
import re


MVP_TASK_PATTERN = re.compile(r"(?m)^\s*-\s+\[([ xX])\]\s+\[(MVP-(\d{3}))\]\s+(.+?)\s*$")
EXCLUDED_BACKLOG_PATTERN = re.compile(
    r"(?m)^\s*-\s+`?\[BACKLOG\]\[MVP-EXCLUDED\]\[NICE-TO-HAVE\]`?\s+(.+?)\s*$"
)
MVP_INCLUDE_MAX_ID = 11


class MVPReleaseGateValidationError(ValueError):
    pass


def evaluate_mvp_release_gate(markdown: str) -> dict[str, object]:
    include_tasks: list[dict[str, object]] = []
    for checked_marker, task_id, raw_id, _title in MVP_TASK_PATTERN.findall(markdown):
        numeric_id = int(raw_id)
        if numeric_id > MVP_INCLUDE_MAX_ID:
            continue
        include_tasks.append({"task_id": task_id, "checked": checked_marker.lower() == "x"})

    if not include_tasks:
        raise MVPReleaseGateValidationError("Could not find MVP include checklist tasks (MVP-001..MVP-011).")

    excluded_backlog_items = [item.strip() for item in EXCLUDED_BACKLOG_PATTERN.findall(markdown)]
    if not excluded_backlog_items:
        raise MVPReleaseGateValidationError(
            "Checklist is missing `[BACKLOG][MVP-EXCLUDED][NICE-TO-HAVE]` labels for MVP excluded features."
        )

    blocking_tasks = [str(task["task_id"]) for task in include_tasks if not bool(task["checked"])]

    return {
        "is_ready": len(blocking_tasks) == 0,
        "blocking_tasks": blocking_tasks,
        "included_task_count": len(include_tasks),
        "excluded_backlog_items": excluded_backlog_items,
        "excluded_backlog_count": len(excluded_backlog_items),
    }


def validate_mvp_release_gate(path: Path) -> dict[str, object]:
    markdown = path.read_text(encoding="utf-8")
    result = evaluate_mvp_release_gate(markdown)

    blocking_tasks = result.get("blocking_tasks", [])
    if isinstance(blocking_tasks, list) and blocking_tasks:
        raise MVPReleaseGateValidationError(
            "MVP sign-off blocked by incomplete MVP include tasks: " + ", ".join(str(task_id) for task_id in blocking_tasks)
        )

    return result

