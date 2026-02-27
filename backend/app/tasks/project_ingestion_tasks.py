from __future__ import annotations

try:  # pragma: no cover - optional dependency in local/test envs
    from celery import shared_task
except Exception:  # noqa: BLE001
    def shared_task(*_args, **_kwargs):  # type: ignore[misc]
        def decorator(fn):
            return fn

        return decorator


@shared_task(name="project_ingestion.execute_job")
def execute_project_ingestion_job(job_id: str) -> None:
    from app.main import run_project_ingestion_job_by_id

    run_project_ingestion_job_by_id(str(job_id).strip())
