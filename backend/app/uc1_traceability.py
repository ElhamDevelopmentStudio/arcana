from __future__ import annotations

import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


@dataclass(frozen=True)
class UC1Step:
    step_id: str
    name: str
    endpoint: str


UC1_STEPS: list[UC1Step] = [
    UC1Step("UC1-STEP-01", "Create project", "POST /api/projects"),
    UC1Step("UC1-STEP-02", "Ingest Shadow Slave TXT", "POST /api/projects/{project_id}/ingest/txt"),
    UC1Step("UC1-STEP-03", "Import character map", "POST /api/projects/{project_id}/characters/import"),
    UC1Step("UC1-STEP-04", "Configure voices", "PUT /api/projects/{project_id}/voices"),
    UC1Step("UC1-STEP-05", "Create audiobook run", "POST /api/projects/{project_id}/runs"),
    UC1Step("UC1-STEP-06", "Read run detail", "GET /api/projects/{project_id}/runs/{run_id}"),
    UC1Step("UC1-STEP-07", "Fetch audiobook export", "GET /api/projects/{project_id}/exports/{run_id}.json"),
]


class UC1TraceabilityError(RuntimeError):
    pass


def _sample_shadow_slave_txt() -> str:
    return (
        "Chapter 1\n"
        '"Sunny looked around," Sunny said. The cold wind cut through the dark street.\n\n'
        "Chapter 2\n"
        "Nephis smiled. Hope rose with the warm light."
    )


def _sample_character_map_json() -> bytes:
    payload = {
        "Sunny": {"verbalized_form": "Sunny", "gender": "male"},
        "Nephis": {"verbalized_form": "Ne-fis", "gender": "female"},
    }
    return json.dumps(payload).encode("utf-8")


def _trace_record(step: UC1Step, response_status: int, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "step_id": step.step_id,
        "name": step.name,
        "endpoint": step.endpoint,
        "status_code": response_status,
        "passed": passed,
        "detail": detail,
    }


def _require_status(step: UC1Step, status_code: int, expected: int, detail: str) -> None:
    if status_code != expected:
        raise UC1TraceabilityError(
            f"{step.step_id} failed: expected status {expected}, got {status_code}. detail={detail}"
        )


def run_uc1_traceability(client: TestClient) -> dict[str, Any]:
    report: dict[str, Any] = {
        "use_case": "UC-1",
        "name": "Shadow Slave -> Audiobook export",
        "status": "failed",
        "steps": [],
    }

    # Step 01: create project
    step = UC1_STEPS[0]
    project_resp = client.post("/api/projects", json={"title": "Shadow Slave UC1 Traceability"})
    _require_status(step, project_resp.status_code, 201, project_resp.text)
    project_id = project_resp.json()["id"]
    report["steps"].append(_trace_record(step, project_resp.status_code, True, f"project_id={project_id}"))

    # Step 02: ingest text
    step = UC1_STEPS[1]
    ingest_resp = client.post(
        f"/api/projects/{project_id}/ingest/txt",
        files={"file": ("shadow_slave_sample.txt", io.BytesIO(_sample_shadow_slave_txt().encode("utf-8")), "text/plain")},
    )
    _require_status(step, ingest_resp.status_code, 200, ingest_resp.text)
    chapter_count = ingest_resp.json()["chapter_count"]
    if chapter_count < 1:
        raise UC1TraceabilityError(f"{step.step_id} failed: chapter_count must be >= 1.")
    report["steps"].append(_trace_record(step, ingest_resp.status_code, True, f"chapter_count={chapter_count}"))

    # Step 03: import character map
    step = UC1_STEPS[2]
    char_resp = client.post(
        f"/api/projects/{project_id}/characters/import",
        files={"file": ("characters.json", io.BytesIO(_sample_character_map_json()), "application/json")},
    )
    _require_status(step, char_resp.status_code, 200, char_resp.text)
    imported_count = char_resp.json()["imported_count"]
    if imported_count < 1:
        raise UC1TraceabilityError(f"{step.step_id} failed: imported_count must be >= 1.")
    report["steps"].append(_trace_record(step, char_resp.status_code, True, f"imported_count={imported_count}"))

    # Step 04: configure voices
    step = UC1_STEPS[3]
    voice_resp = client.put(
        f"/api/projects/{project_id}/voices",
        json={
            "narrator_voice": "narrator_default",
            "male_default_voice": "male_default",
            "female_default_voice": "female_default",
        },
    )
    _require_status(step, voice_resp.status_code, 200, voice_resp.text)
    report["steps"].append(_trace_record(step, voice_resp.status_code, True, "voice config applied"))

    # Step 05: run pipeline
    step = UC1_STEPS[4]
    run_payload = {
        "max_segment_chars": 120,
        "llm_enabled": False,
        "provider_name": "openrouter",
        "max_calls_per_day": 2,
    }
    run_resp = client.post(f"/api/projects/{project_id}/runs", json=run_payload)
    _require_status(step, run_resp.status_code, 200, run_resp.text)
    run_body = run_resp.json()
    run_id = run_body["run_id"]
    report["steps"].append(_trace_record(step, run_resp.status_code, True, f"run_id={run_id}"))

    # Step 06: run detail
    step = UC1_STEPS[5]
    detail_resp = client.get(f"/api/projects/{project_id}/runs/{run_id}")
    _require_status(step, detail_resp.status_code, 200, detail_resp.text)
    detail_body = detail_resp.json()
    if detail_body["status"] != "completed":
        raise UC1TraceabilityError(f"{step.step_id} failed: run status must be completed.")
    if detail_body["config"]["mode"] != "audiobook":
        raise UC1TraceabilityError(f"{step.step_id} failed: run mode must be audiobook.")
    report["steps"].append(_trace_record(step, detail_resp.status_code, True, "run status completed"))

    # Step 07: export
    step = UC1_STEPS[6]
    export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
    _require_status(step, export_resp.status_code, 200, export_resp.text)
    export_body = export_resp.json()
    segments = export_body.get("segments", [])
    if not segments:
        raise UC1TraceabilityError(f"{step.step_id} failed: export must contain at least one segment.")
    report["steps"].append(_trace_record(step, export_resp.status_code, True, f"segments={len(segments)}"))

    report["project_id"] = project_id
    report["run_id"] = run_id
    report["segment_count"] = len(segments)
    report["status"] = "passed"
    return report


def write_uc1_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
