from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


CORE_PIPELINE_MODES: tuple[str, ...] = ("audiobook", "academic", "author", "custom")


def build_core_pipeline_source_text() -> str:
    return (
        "Chapter 1\n"
        "Sunny crossed the dark hall and paused near the broken gate. "
        "He listened for footsteps and whispered that dawn was still far away.\n\n"
        "Chapter 2\n"
        "Nephis held the lantern steady while the storm moved over the empty street."
    )


def load_performance_regression_thresholds(path: Path) -> dict[str, int]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        raise ValueError("Performance regression thresholds must be an object map.")

    thresholds: dict[str, int] = {}
    for mode in CORE_PIPELINE_MODES:
        raw_value = payload.get(mode)
        if not isinstance(raw_value, int):
            raise ValueError(f"Missing or invalid integer threshold for mode '{mode}'.")
        if raw_value <= 0:
            raise ValueError(f"Threshold for mode '{mode}' must be > 0.")
        thresholds[mode] = raw_value

    return thresholds


def collect_core_pipeline_performance_metrics(
    client: TestClient,
    *,
    source_text: str | None = None,
) -> dict[str, dict[str, int]]:
    sample_text = source_text or build_core_pipeline_source_text()

    metrics: dict[str, dict[str, int]] = {}
    for mode in CORE_PIPELINE_MODES:
        create_resp = client.post("/api/projects", json={"title": f"Performance Gate {mode}"})
        if create_resp.status_code != 201:
            raise ValueError(f"Project creation failed for mode {mode}: status={create_resp.status_code}")
        project_id = int(create_resp.json()["id"])

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": (
                    "performance-gate.txt",
                    io.BytesIO(sample_text.encode("utf-8")),
                    "text/plain",
                )
            },
        )
        if ingest_resp.status_code != 200:
            raise ValueError(f"TXT ingestion failed for mode {mode}: status={ingest_resp.status_code}")

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={
                "mode": mode,
                "llm_enabled": False,
                "allow_unfinalized_character_map": True,
            },
        )
        if run_resp.status_code != 200:
            raise ValueError(f"Run creation failed for mode {mode}: status={run_resp.status_code}")
        run_payload = run_resp.json()
        run_id = int(run_payload["run_id"])
        segment_count = int(run_payload["segment_count"])

        detail_resp = client.get(f"/api/projects/{project_id}/runs/{run_id}")
        if detail_resp.status_code != 200:
            raise ValueError(f"Run detail retrieval failed for mode {mode}: status={detail_resp.status_code}")
        detail_payload = detail_resp.json()
        telemetry = ((detail_payload.get("config") or {}).get("performance_telemetry") or {})

        total_duration_ms = telemetry.get("total_duration_ms")
        if not isinstance(total_duration_ms, int):
            raise ValueError(f"Missing performance_telemetry.total_duration_ms for mode {mode}")

        steps = telemetry.get("steps")
        if not isinstance(steps, list):
            raise ValueError(f"Missing performance_telemetry.steps list for mode {mode}")

        metrics[mode] = {
            "total_duration_ms": int(total_duration_ms),
            "segment_count": segment_count,
            "step_count": len(steps),
        }

    return metrics


def evaluate_performance_regression_gate(
    *,
    metrics: dict[str, dict[str, int]],
    thresholds: dict[str, int],
) -> dict[str, Any]:
    by_mode: dict[str, dict[str, int | bool]] = {}
    violations: list[str] = []

    for mode in CORE_PIPELINE_MODES:
        mode_metrics = metrics.get(mode)
        if not isinstance(mode_metrics, dict):
            violations.append(f"{mode}:missing_metrics")
            continue

        total_duration_ms = int(mode_metrics.get("total_duration_ms", -1))
        threshold_ms = int(thresholds[mode])
        within_threshold = total_duration_ms <= threshold_ms

        by_mode[mode] = {
            "total_duration_ms": total_duration_ms,
            "threshold_ms": threshold_ms,
            "within_threshold": within_threshold,
            "segment_count": int(mode_metrics.get("segment_count", 0)),
            "step_count": int(mode_metrics.get("step_count", 0)),
        }
        if not within_threshold:
            violations.append(f"{mode}:{total_duration_ms}>{threshold_ms}")

    return {
        "gate_passed": not violations,
        "violations": violations,
        "by_mode": by_mode,
    }
