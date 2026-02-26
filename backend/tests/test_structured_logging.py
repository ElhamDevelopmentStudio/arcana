from __future__ import annotations

import json
import logging
from datetime import datetime

import pytest

from app.services.background_jobs import BackgroundJobFrameworkError, submit_background_job
from app.services.structured_logging import (
    STRUCTURED_LOGGER_NAME,
    STRUCTURED_LOG_SCHEMA_VERSION,
    build_structured_log_record,
    emit_structured_log,
)


def _parse_structured_records(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for record in caplog.records:
        if record.name != STRUCTURED_LOGGER_NAME:
            continue
        records.append(json.loads(record.getMessage()))
    return records


def test_build_structured_log_record_normalizes_and_keeps_schema() -> None:
    record = build_structured_log_record(
        service=" run_orchestration ",
        event=" run_execution_dispatched ",
        message="Run execution dispatched",
        level=" INFO ",
        metadata={"mode": "AO-001"},
        project_id=10,
        run_id=22,
        correlation_id=" corr-123 ",
    )

    assert record["schema_version"] == STRUCTURED_LOG_SCHEMA_VERSION
    assert record["level"] == "info"
    assert record["service"] == "run_orchestration"
    assert record["event"] == "run_execution_dispatched"
    assert record["message"] == "Run execution dispatched"
    assert record["metadata"] == {"mode": "AO-001"}
    assert record["project_id"] == 10
    assert record["run_id"] == 22
    assert record["correlation_id"] == "corr-123"
    assert datetime.fromisoformat(str(record["timestamp"]).replace("Z", "+00:00")).tzinfo is not None


def test_build_structured_log_record_rejects_blank_required_fields() -> None:
    with pytest.raises(ValueError, match="service must not be blank"):
        build_structured_log_record(
            service=" ",
            event="run_execution_dispatched",
            message="Run execution dispatched",
        )


def test_emit_structured_log_writes_json_payload(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger=STRUCTURED_LOGGER_NAME)

    emit_structured_log(
        service="pipeline_execution",
        event="pipeline_execution_completed",
        message="Pipeline execution completed",
        metadata={"segment_count": 7},
    )

    records = _parse_structured_records(caplog)
    assert records
    latest_record = records[-1]
    assert latest_record["event"] == "pipeline_execution_completed"
    assert latest_record["metadata"] == {"segment_count": 7}
    assert latest_record["schema_version"] == STRUCTURED_LOG_SCHEMA_VERSION


def test_submit_background_job_emits_submit_and_complete_logs(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger=STRUCTURED_LOGGER_NAME)

    result = submit_background_job(job_name="pipeline_execute_run", execute=lambda: 42)

    assert result == 42
    records = _parse_structured_records(caplog)
    events = [str(record["event"]) for record in records]
    assert events.count("background_job_submitted") == 1
    assert events.count("background_job_completed") == 1
    assert "background_job_failed" not in events


def test_submit_background_job_emits_failure_log_and_reraises(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger=STRUCTURED_LOGGER_NAME)

    def _failing_job() -> int:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        submit_background_job(job_name="pipeline_execute_run", execute=_failing_job)

    records = _parse_structured_records(caplog)
    events = [str(record["event"]) for record in records]
    assert events.count("background_job_submitted") == 1
    assert events.count("background_job_failed") == 1
    assert "background_job_completed" not in events


def test_submit_background_job_rejects_blank_name() -> None:
    with pytest.raises(BackgroundJobFrameworkError, match="job_name must not be blank"):
        submit_background_job(job_name=" ", execute=lambda: 1)
