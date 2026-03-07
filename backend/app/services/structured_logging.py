from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Mapping


STRUCTURED_LOGGER_NAME = "arcana.structured"
STRUCTURED_LOG_SCHEMA_VERSION = "1.0"

_LOG_LEVELS: dict[str, int] = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}


def _normalize_required_field(*, value: str, field_name: str) -> str:
    normalized_value = value.strip()
    if not normalized_value:
        raise ValueError(f"{field_name} must not be blank.")
    return normalized_value


def _normalize_level(level: str) -> str:
    normalized_level = level.strip().lower()
    if normalized_level not in _LOG_LEVELS:
        allowed_levels = ", ".join(sorted(_LOG_LEVELS.keys()))
        raise ValueError(f"Unsupported log level '{normalized_level}'. Allowed values: {allowed_levels}.")
    return normalized_level


def build_structured_log_record(
    *,
    service: str,
    event: str,
    message: str,
    level: str = "info",
    metadata: Mapping[str, Any] | None = None,
    project_id: int | None = None,
    run_id: int | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    normalized_service = _normalize_required_field(value=service, field_name="service")
    normalized_event = _normalize_required_field(value=event, field_name="event")
    normalized_message = _normalize_required_field(value=message, field_name="message")
    normalized_level = _normalize_level(level)
    record: dict[str, Any] = {
        "schema_version": STRUCTURED_LOG_SCHEMA_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "level": normalized_level,
        "service": normalized_service,
        "event": normalized_event,
        "message": normalized_message,
        "metadata": dict(metadata or {}),
    }
    if project_id is not None:
        record["project_id"] = int(project_id)
    if run_id is not None:
        record["run_id"] = int(run_id)
    if correlation_id is not None:
        normalized_correlation_id = correlation_id.strip()
        if normalized_correlation_id:
            record["correlation_id"] = normalized_correlation_id
    return record


def emit_structured_log(
    *,
    service: str,
    event: str,
    message: str,
    level: str = "info",
    metadata: Mapping[str, Any] | None = None,
    project_id: int | None = None,
    run_id: int | None = None,
    correlation_id: str | None = None,
    logger: logging.Logger | None = None,
) -> dict[str, Any]:
    record = build_structured_log_record(
        service=service,
        event=event,
        message=message,
        level=level,
        metadata=metadata,
        project_id=project_id,
        run_id=run_id,
        correlation_id=correlation_id,
    )
    target_logger = logger or logging.getLogger(STRUCTURED_LOGGER_NAME)
    target_logger.log(_LOG_LEVELS[record["level"]], json.dumps(record, sort_keys=True, default=str))
    return record
