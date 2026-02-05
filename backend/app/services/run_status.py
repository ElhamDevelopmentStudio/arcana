from __future__ import annotations

from typing import Literal


RunStatus = Literal["queued", "running", "completed", "failed", "cancelled"]

RUN_STATUS_QUEUED: RunStatus = "queued"
RUN_STATUS_RUNNING: RunStatus = "running"
RUN_STATUS_COMPLETED: RunStatus = "completed"
RUN_STATUS_FAILED: RunStatus = "failed"
RUN_STATUS_CANCELLED: RunStatus = "cancelled"

RUN_STATUS_VALUES: tuple[RunStatus, ...] = (
    RUN_STATUS_QUEUED,
    RUN_STATUS_RUNNING,
    RUN_STATUS_COMPLETED,
    RUN_STATUS_FAILED,
    RUN_STATUS_CANCELLED,
)

RUN_TERMINAL_STATUSES = frozenset(
    {
        RUN_STATUS_COMPLETED,
        RUN_STATUS_FAILED,
        RUN_STATUS_CANCELLED,
    }
)


def is_valid_run_status(value: object) -> bool:
    return isinstance(value, str) and value in RUN_STATUS_VALUES

