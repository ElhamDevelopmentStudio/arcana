from __future__ import annotations

from typing import Callable, Protocol, TypeVar


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
) -> T:
    executor = get_background_job_executor(executor_name)
    return executor.submit(job_name=job_name, execute=execute)

