PROJECT_LIFECYCLE_DRAFT = "draft"
PROJECT_LIFECYCLE_INGESTED = "ingested"
PROJECT_LIFECYCLE_CONFIGURED = "configured"
PROJECT_LIFECYCLE_RUNNING = "running"
PROJECT_LIFECYCLE_COMPLETED = "completed"
PROJECT_LIFECYCLE_FAILED = "failed"
PROJECT_LIFECYCLE_ARCHIVED = "archived"

PROJECT_LIFECYCLE_STATES = frozenset(
    {
        PROJECT_LIFECYCLE_DRAFT,
        PROJECT_LIFECYCLE_INGESTED,
        PROJECT_LIFECYCLE_CONFIGURED,
        PROJECT_LIFECYCLE_RUNNING,
        PROJECT_LIFECYCLE_COMPLETED,
        PROJECT_LIFECYCLE_FAILED,
        PROJECT_LIFECYCLE_ARCHIVED,
    }
)

PROJECT_LIFECYCLE_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    PROJECT_LIFECYCLE_DRAFT: {
        PROJECT_LIFECYCLE_DRAFT,
        PROJECT_LIFECYCLE_INGESTED,
        PROJECT_LIFECYCLE_CONFIGURED,
        PROJECT_LIFECYCLE_RUNNING,
        PROJECT_LIFECYCLE_ARCHIVED,
    },
    PROJECT_LIFECYCLE_INGESTED: {
        PROJECT_LIFECYCLE_INGESTED,
        PROJECT_LIFECYCLE_CONFIGURED,
        PROJECT_LIFECYCLE_RUNNING,
        PROJECT_LIFECYCLE_ARCHIVED,
    },
    PROJECT_LIFECYCLE_CONFIGURED: {
        PROJECT_LIFECYCLE_CONFIGURED,
        PROJECT_LIFECYCLE_INGESTED,
        PROJECT_LIFECYCLE_RUNNING,
        PROJECT_LIFECYCLE_ARCHIVED,
    },
    PROJECT_LIFECYCLE_RUNNING: {
        PROJECT_LIFECYCLE_RUNNING,
        PROJECT_LIFECYCLE_COMPLETED,
        PROJECT_LIFECYCLE_FAILED,
        PROJECT_LIFECYCLE_CONFIGURED,
    },
    PROJECT_LIFECYCLE_COMPLETED: {
        PROJECT_LIFECYCLE_COMPLETED,
        PROJECT_LIFECYCLE_CONFIGURED,
        PROJECT_LIFECYCLE_INGESTED,
        PROJECT_LIFECYCLE_RUNNING,
        PROJECT_LIFECYCLE_ARCHIVED,
    },
    PROJECT_LIFECYCLE_FAILED: {
        PROJECT_LIFECYCLE_FAILED,
        PROJECT_LIFECYCLE_CONFIGURED,
        PROJECT_LIFECYCLE_INGESTED,
        PROJECT_LIFECYCLE_RUNNING,
        PROJECT_LIFECYCLE_ARCHIVED,
    },
    PROJECT_LIFECYCLE_ARCHIVED: {
        PROJECT_LIFECYCLE_ARCHIVED,
    },
}


class ProjectLifecycleTransitionError(ValueError):
    """Raised when a project lifecycle transition is not allowed."""


def normalize_project_lifecycle_state(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in PROJECT_LIFECYCLE_STATES:
        raise ProjectLifecycleTransitionError(
            "lifecycle_state must be one of: draft, ingested, configured, running, completed, failed, archived"
        )
    return normalized


def transition_project_lifecycle_state(*, current_state: str | None, next_state: str | None) -> str:
    normalized_current = normalize_project_lifecycle_state(current_state)
    normalized_next = normalize_project_lifecycle_state(next_state)
    allowed_targets = PROJECT_LIFECYCLE_ALLOWED_TRANSITIONS[normalized_current]
    if normalized_next not in allowed_targets:
        raise ProjectLifecycleTransitionError(
            f"{normalized_current} -> {normalized_next} is not allowed"
        )
    return normalized_next
