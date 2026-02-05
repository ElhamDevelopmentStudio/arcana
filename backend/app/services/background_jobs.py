from __future__ import annotations

from typing import Callable, Protocol, TypeVar

from app.services.structured_logging import emit_structured_log


T = TypeVar("T")


class BackgroundJobFrameworkError(ValueError):
    pass


class BackgroundJobExecutor(Protocol):
    name: str

    def submit(self, *, job_name: str, execute: Callable[[], T]) -> T:
        ...


class InlineBackgroundJobExecutor:
    name = "inline"

    def submit(self, *, job_name: str, execute: Callable[[], T]) -> T:
        if not job_name.strip():
            raise BackgroundJobFrameworkError("job_name must not be blank.")
        return execute()


_EXECUTOR_REGISTRY: dict[str, BackgroundJobExecutor] = {
    "inline": InlineBackgroundJobExecutor(),
}


def get_background_job_executor(executor_name: str | None = None) -> BackgroundJobExecutor:
    normalized_name = (executor_name or "inline").strip().lower()
    if not normalized_name:
        normalized_name = "inline"
    executor = _EXECUTOR_REGISTRY.get(normalized_name)
    if executor is None:
        supported = ", ".join(sorted(_EXECUTOR_REGISTRY.keys()))
        raise BackgroundJobFrameworkError(
            f"Unsupported background job executor '{normalized_name}'. Supported executors: {supported}."
        )
    return executor


def submit_background_job(
    *,
    job_name: str,
    execute: Callable[[], T],
    executor_name: str | None = None,
    correlation_id: str | None = None,
) -> T:
    normalized_job_name = job_name.strip()
    if not normalized_job_name:
        raise BackgroundJobFrameworkError("job_name must not be blank.")
    normalized_correlation_id = None
    if isinstance(correlation_id, str):
        candidate_correlation_id = correlation_id.strip()
        if candidate_correlation_id:
            normalized_correlation_id = candidate_correlation_id
    executor = get_background_job_executor(executor_name)
    emit_structured_log(
        service="background_jobs",
        event="background_job_submitted",
        message="Background job submitted",
        correlation_id=normalized_correlation_id,
        metadata={
            "job_name": normalized_job_name,
            "executor_name": executor.name,
        },
    )
    try:
        result = executor.submit(job_name=normalized_job_name, execute=execute)
    except Exception as exc:  # noqa: BLE001
        emit_structured_log(
            level="error",
            service="background_jobs",
            event="background_job_failed",
            message="Background job failed",
            correlation_id=normalized_correlation_id,
            metadata={
                "job_name": normalized_job_name,
                "executor_name": executor.name,
                "error_type": exc.__class__.__name__,
                "error_message": str(exc),
            },
        )
        raise
    emit_structured_log(
        service="background_jobs",
        event="background_job_completed",
        message="Background job completed",
        correlation_id=normalized_correlation_id,
        metadata={
            "job_name": normalized_job_name,
            "executor_name": executor.name,
        },
    )
    return result
