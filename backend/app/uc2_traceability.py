from __future__ import annotations

import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


@dataclass(frozen=True)
class UC2Step:
    step_id: str
    name: str
    endpoint: str


UC2_STEPS: list[UC2Step] = [
    UC2Step("UC2-STEP-01", "Create project", "POST /api/projects"),
    UC2Step("UC2-STEP-02", "Ingest generic novel TXT", "POST /api/projects/{project_id}/ingest/txt"),
    UC2Step("UC2-STEP-03", "Create academic run", "POST /api/projects/{project_id}/runs"),
    UC2Step("UC2-STEP-04", "Read run detail", "GET /api/projects/{project_id}/runs/{run_id}"),
    UC2Step("UC2-STEP-05", "Fetch academic export", "GET /api/projects/{project_id}/exports/{run_id}.json"),
    UC2Step("UC2-STEP-06", "Re-run and verify deterministic export", "POST /api/projects/{project_id}/runs"),
]


class UC2TraceabilityError(RuntimeError):
    pass


def _sample_novel_txt() -> str:
    return (
        "Chapter 1\n"
        "The scholar opened the old journal. The room stayed silent while he read.\n\n"
        "Chapter 2\n"
        "Rain fell through the city lights. The investigator noted each witness account."
    )


def _trace_record(step: UC2Step, response_status: int, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "step_id": step.step_id,
        "name": step.name,
        "endpoint": step.endpoint,
        "status_code": response_status,
        "passed": passed,
        "detail": detail,
    }


def _require_status(step: UC2Step, status_code: int, expected: int, detail: str) -> None:
    if status_code != expected:
        raise UC2TraceabilityError(
            f"{step.step_id} failed: expected status {expected}, got {status_code}. detail={detail}"
        )


def run_uc2_traceability(client: TestClient) -> dict[str, Any]:
    report: dict[str, Any] = {
        "use_case": "UC-2",
        "name": "Any novel -> Academic export",
        "status": "failed",
        "steps": [],
    }

    # Step 01: create project
    step = UC2_STEPS[0]
    project_resp = client.post("/api/projects", json={"title": "Academic UC2 Traceability"})
    _require_status(step, project_resp.status_code, 201, project_resp.text)
    project_id = project_resp.json()["id"]
    report["steps"].append(_trace_record(step, project_resp.status_code, True, f"project_id={project_id}"))

    # Step 02: ingest text
    step = UC2_STEPS[1]
    ingest_resp = client.post(
        f"/api/projects/{project_id}/ingest/txt",
        files={"file": ("academic_sample.txt", io.BytesIO(_sample_novel_txt().encode("utf-8")), "text/plain")},
    )
    _require_status(step, ingest_resp.status_code, 200, ingest_resp.text)
    chapter_count = ingest_resp.json()["chapter_count"]
    if chapter_count < 1:
        raise UC2TraceabilityError(f"{step.step_id} failed: chapter_count must be >= 1.")
    report["steps"].append(_trace_record(step, ingest_resp.status_code, True, f"chapter_count={chapter_count}"))

    run_payload = {
        "mode": "academic",
        "max_segment_chars": 120,
        "llm_enabled": False,
        "provider_name": "openrouter",
        "max_calls_per_day": 2,
    }

    # Step 03: run academic mode
    step = UC2_STEPS[2]
    run_resp = client.post(f"/api/projects/{project_id}/runs", json=run_payload)
    _require_status(step, run_resp.status_code, 200, run_resp.text)
    run_id = run_resp.json()["run_id"]
    report["steps"].append(_trace_record(step, run_resp.status_code, True, f"run_id={run_id}"))

    # Step 04: run detail
    step = UC2_STEPS[3]
    detail_resp = client.get(f"/api/projects/{project_id}/runs/{run_id}")
    _require_status(step, detail_resp.status_code, 200, detail_resp.text)
    detail_body = detail_resp.json()
    if detail_body["status"] != "completed":
        raise UC2TraceabilityError(f"{step.step_id} failed: run status must be completed.")
    if detail_body["config"]["mode"] != "academic":
        raise UC2TraceabilityError(f"{step.step_id} failed: run mode must be academic.")
    report["steps"].append(_trace_record(step, detail_resp.status_code, True, "run status completed"))

    # Step 05: export
    step = UC2_STEPS[4]
    export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
    _require_status(step, export_resp.status_code, 200, export_resp.text)
    export_body = export_resp.json()
    segments = export_body.get("segments", [])
    if not segments:
        raise UC2TraceabilityError(f"{step.step_id} failed: export must contain at least one segment.")

    required_segment_keys = {
        "chapter_id",
        "segment_id",
        "type",
        "speaker",
        "emotion_valence",
        "emotion_intensity",
        "confidence",
    }
    first_segment = segments[0]
    missing_keys = required_segment_keys - set(first_segment.keys())
    if missing_keys:
        raise UC2TraceabilityError(
            f"{step.step_id} failed: first segment missing required keys: {sorted(missing_keys)}"
        )
    report["steps"].append(_trace_record(step, export_resp.status_code, True, f"segments={len(segments)}"))

    # Step 06: reproducibility re-run
    step = UC2_STEPS[5]
    rerun_resp = client.post(f"/api/projects/{project_id}/runs", json=run_payload)
    _require_status(step, rerun_resp.status_code, 200, rerun_resp.text)
    rerun_id = rerun_resp.json()["run_id"]

    rerun_export_resp = client.get(f"/api/projects/{project_id}/exports/{rerun_id}.json")
    _require_status(step, rerun_export_resp.status_code, 200, rerun_export_resp.text)
    rerun_export_body = rerun_export_resp.json()
    rerun_segments = rerun_export_body.get("segments", [])

    deterministic = segments == rerun_segments
    if not deterministic:
        raise UC2TraceabilityError(
            f"{step.step_id} failed: export segments differ across equivalent academic re-runs ({run_id} vs {rerun_id})."
        )

    report["steps"].append(
        _trace_record(step, rerun_resp.status_code, True, f"rerun_id={rerun_id}; deterministic={deterministic}")
    )

    report["project_id"] = project_id
    report["run_id"] = run_id
    report["rerun_id"] = rerun_id
    report["segment_count"] = len(segments)
    report["deterministic"] = deterministic
    report["status"] = "passed"
    return report


def write_uc2_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
