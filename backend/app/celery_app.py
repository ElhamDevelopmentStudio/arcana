from __future__ import annotations

from typing import Any

from app.config import get_settings

try:  # pragma: no cover - optional dependency in local/test envs
    from celery import Celery
except Exception:  # noqa: BLE001
    Celery = None  # type: ignore[assignment]


def _create_celery_app() -> Any | None:
    if Celery is None:
        return None

    settings = get_settings()
    broker_url = str(settings.celery_broker_url or "").strip()
    if not broker_url:
        return None

    result_backend = str(settings.celery_result_backend or "").strip() or broker_url
    app = Celery(
        "nipe",
        broker=broker_url,
        backend=result_backend,
        include=(
            "app.tasks.character_extraction_tasks",
            "app.tasks.project_ingestion_tasks",
            "app.tasks.pipeline_tasks",
        ),
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_ignore_result=False,
    )
    return app


celery_app = _create_celery_app()


def is_celery_available() -> bool:
    return celery_app is not None
