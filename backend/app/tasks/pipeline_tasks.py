from __future__ import annotations

try:  # pragma: no cover - optional dependency in local/test envs
    from celery import shared_task
except Exception:  # noqa: BLE001
    def shared_task(*_args, **_kwargs):  # type: ignore[misc]
        def decorator(fn):
            return fn

        return decorator


@shared_task(name="pipeline.execute_run")
def execute_pipeline_run(
    run_id: int,
    principal_type: str | None = None,
    principal_id: str | None = None,
) -> None:
    from app.main import run_pipeline_run_by_id

    run_pipeline_run_by_id(
        int(run_id),
        principal_type=str(principal_type).strip() or None if principal_type is not None else None,
        principal_id=str(principal_id).strip() or None if principal_id is not None else None,
    )
