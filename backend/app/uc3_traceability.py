from __future__ import annotations

import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


@dataclass(frozen=True)
class UC3Step:
    step_id: str
    name: str
    endpoint: str


UC3_STEPS: list[UC3Step] = [
    UC3Step("UC3-STEP-01", "Create project", "POST /api/projects"),
    UC3Step("UC3-STEP-02", "Ingest draft novel TXT", "POST /api/projects/{project_id}/ingest/txt"),
    UC3Step("UC3-STEP-03", "Create author run", "POST /api/projects/{project_id}/runs"),
    UC3Step("UC3-STEP-04", "Read run detail", "GET /api/projects/{project_id}/runs/{run_id}"),
    UC3Step("UC3-STEP-05", "Fetch author export", "GET /api/projects/{project_id}/exports/{run_id}.json"),
    UC3Step("UC3-STEP-06", "Validate author diagnostic signal baseline", "GET /api/projects/{project_id}/exports/{run_id}.json"),
    UC3Step("UC3-STEP-07", "Re-run and verify deterministic author export", "POST /api/projects/{project_id}/runs"),
]


class UC3TraceabilityError(RuntimeError):
    pass


def _sample_draft_txt() -> str:
    return (
        "Chapter 1\n"
        '"We are falling behind," Mira said. The room felt cold and grim.\n\n'
        "Chapter 2\n"
        '"I will not quit," Aron said. Relief and hope returned with warm dawn light.'
    )


def _trace_record(step: UC3Step, response_status: int, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "step_id": step.step_id,
        "name": step.name,
        "endpoint": step.endpoint,
        "status_code": response_status,
        "passed": passed,
        "detail": detail,
    }


def _require_status(step: UC3Step, status_code: int, expected: int, detail: str) -> None:
    if status_code != expected:
        raise UC3TraceabilityError(
            f"{step.step_id} failed: expected status {expected}, got {status_code}. detail={detail}"
        )


def _validate_author_diagnostic_signal_baseline(segments: list[dict[str, Any]], step: UC3Step) -> dict[str, Any]:
    if not segments:
        raise UC3TraceabilityError(f"{step.step_id} failed: export must contain at least one segment.")

    required_segment_keys = {
        "chapter_id",
        "segment_id",
        "type",
        "speaker",
        "emotion_valence",
        "emotion_intensity",
        "confidence",
    }
    required_confidence_keys = {"speaker", "emotion"}

    observed_types: set[str] = set()
    non_zero_emotion_count = 0

    for idx, segment in enumerate(segments):
        missing_keys = required_segment_keys - set(segment.keys())
        if missing_keys:
            raise UC3TraceabilityError(
                f"{step.step_id} failed: segment index {idx} missing keys: {sorted(missing_keys)}"
            )

        confidence_obj = segment["confidence"]
        if not isinstance(confidence_obj, dict):
            raise UC3TraceabilityError(f"{step.step_id} failed: segment index {idx} confidence must be an object.")

        missing_confidence = required_confidence_keys - set(confidence_obj.keys())
        if missing_confidence:
            raise UC3TraceabilityError(
                f"{step.step_id} failed: segment index {idx} missing confidence keys: {sorted(missing_confidence)}"
            )

        observed_types.add(str(segment["type"]))
        if float(segment["emotion_intensity"]) > 0:
            non_zero_emotion_count += 1

    allowed_types = {"dialogue", "narration"}
    unsupported_types = observed_types - allowed_types
    if unsupported_types:
        raise UC3TraceabilityError(
            f"{step.step_id} failed: unsupported segment types observed: {sorted(unsupported_types)}."
        )

    if non_zero_emotion_count == 0:
        raise UC3TraceabilityError(f"{step.step_id} failed: expected at least one segment with non-zero emotion intensity.")

    return {
        "segment_count": len(segments),
        "observed_types": sorted(observed_types),
        "non_zero_emotion_count": non_zero_emotion_count,
    }


def run_uc3_traceability(client: TestClient) -> dict[str, Any]:
    report: dict[str, Any] = {
        "use_case": "UC-3",
        "name": "Draft novel -> Author diagnostics",
        "status": "failed",
        "steps": [],
    }

    # Step 01: create project
    step = UC3_STEPS[0]
    project_resp = client.post("/api/projects", json={"title": "Author UC3 Traceability"})
    _require_status(step, project_resp.status_code, 201, project_resp.text)
    project_id = project_resp.json()["id"]
    report["steps"].append(_trace_record(step, project_resp.status_code, True, f"project_id={project_id}"))

    # Step 02: ingest text
    step = UC3_STEPS[1]
    ingest_resp = client.post(
        f"/api/projects/{project_id}/ingest/txt",
        files={"file": ("draft_sample.txt", io.BytesIO(_sample_draft_txt().encode("utf-8")), "text/plain")},
    )
    _require_status(step, ingest_resp.status_code, 200, ingest_resp.text)
    chapter_count = ingest_resp.json()["chapter_count"]
    if chapter_count < 1:
        raise UC3TraceabilityError(f"{step.step_id} failed: chapter_count must be >= 1.")
    report["steps"].append(_trace_record(step, ingest_resp.status_code, True, f"chapter_count={chapter_count}"))

    run_payload = {
        "mode": "author",
        "max_segment_chars": 120,
        "llm_enabled": False,
        "provider_name": "openrouter",
        "max_calls_per_day": 2,
    }

    # Step 03: run author mode
    step = UC3_STEPS[2]
    run_resp = client.post(f"/api/projects/{project_id}/runs", json=run_payload)
    _require_status(step, run_resp.status_code, 200, run_resp.text)
    run_id = run_resp.json()["run_id"]
    report["steps"].append(_trace_record(step, run_resp.status_code, True, f"run_id={run_id}"))

    # Step 04: run detail
    step = UC3_STEPS[3]
    detail_resp = client.get(f"/api/projects/{project_id}/runs/{run_id}")
    _require_status(step, detail_resp.status_code, 200, detail_resp.text)
    detail_body = detail_resp.json()
    if detail_body["status"] != "completed":
        raise UC3TraceabilityError(f"{step.step_id} failed: run status must be completed.")
    if detail_body["config"]["mode"] != "author":
        raise UC3TraceabilityError(f"{step.step_id} failed: run mode must be author.")
    report["steps"].append(_trace_record(step, detail_resp.status_code, True, "run status completed"))

    # Step 05: export
    step = UC3_STEPS[4]
    export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
    _require_status(step, export_resp.status_code, 200, export_resp.text)
    export_body = export_resp.json()
    segments = export_body.get("segments", [])
    if not segments:
        raise UC3TraceabilityError(f"{step.step_id} failed: export must contain at least one segment.")
    report["steps"].append(_trace_record(step, export_resp.status_code, True, f"segments={len(segments)}"))

    # Step 06: signal baseline
    step = UC3_STEPS[5]
    signal_stats = _validate_author_diagnostic_signal_baseline(segments, step)
    report["steps"].append(
        _trace_record(
            step,
            export_resp.status_code,
            True,
            (
                f"types={signal_stats['observed_types']}; "
                f"non_zero_emotion_count={signal_stats['non_zero_emotion_count']}"
            ),
        )
    )

    # Step 07: reproducibility re-run
    step = UC3_STEPS[6]
    rerun_resp = client.post(f"/api/projects/{project_id}/runs", json=run_payload)
    _require_status(step, rerun_resp.status_code, 200, rerun_resp.text)
    rerun_id = rerun_resp.json()["run_id"]

    rerun_export_resp = client.get(f"/api/projects/{project_id}/exports/{rerun_id}.json")
    _require_status(step, rerun_export_resp.status_code, 200, rerun_export_resp.text)
    rerun_export_body = rerun_export_resp.json()
    rerun_segments = rerun_export_body.get("segments", [])

    deterministic = segments == rerun_segments
    if not deterministic:
        raise UC3TraceabilityError(
            f"{step.step_id} failed: export segments differ across equivalent author re-runs ({run_id} vs {rerun_id})."
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


def write_uc3_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
