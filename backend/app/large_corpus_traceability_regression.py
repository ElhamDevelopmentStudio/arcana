from __future__ import annotations

import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

LARGE_CORPUS_MODES: list[str] = ["audiobook", "academic", "author"]


class LargeCorpusTraceabilityError(RuntimeError):
    pass


def _require_status(step: str, status_code: int, expected: int, detail: str) -> None:
    if status_code != expected:
        raise LargeCorpusTraceabilityError(
            f"{step} failed: expected status {expected}, got {status_code}. detail={detail}"
        )


def _sample_character_map_json() -> bytes:
    payload = {
        "Sunny": {"verbalized_form": "Sunny", "gender": "male"},
        "Nephis": {"verbalized_form": "Ne-fis", "gender": "female"},
        "Cassie": {"verbalized_form": "Cassie", "gender": "female"},
    }
    return json.dumps(payload).encode("utf-8")


def _load_corpus_or_raise(novel_path: Path) -> tuple[bytes, str]:
    if not novel_path.exists():
        raise LargeCorpusTraceabilityError(f"Novel fixture does not exist: {novel_path}")
    if not novel_path.is_file():
        raise LargeCorpusTraceabilityError(f"Novel fixture is not a file: {novel_path}")

    payload = novel_path.read_bytes()
    if not payload:
        raise LargeCorpusTraceabilityError(f"Novel fixture is empty: {novel_path}")

    digest = hashlib.sha256(payload).hexdigest()
    return payload, digest


def _run_mode_twice(client: TestClient, project_id: int, mode: str) -> dict[str, Any]:
    run_payload = {
        "mode": mode,
        "max_segment_chars": 120,
        "llm_enabled": False,
        "provider_name": "openrouter",
        "max_calls_per_day": 3,
    }

    first_run_resp = client.post(f"/api/projects/{project_id}/runs", json=run_payload)
    _require_status(f"{mode}/run-1", first_run_resp.status_code, 200, first_run_resp.text)
    first_run_id = first_run_resp.json()["run_id"]

    first_detail_resp = client.get(f"/api/projects/{project_id}/runs/{first_run_id}")
    _require_status(f"{mode}/detail-1", first_detail_resp.status_code, 200, first_detail_resp.text)
    first_detail = first_detail_resp.json()
    if first_detail["status"] != "completed":
        raise LargeCorpusTraceabilityError(f"{mode}/detail-1 failed: run status must be completed.")
    if first_detail["config"]["mode"] != mode:
        raise LargeCorpusTraceabilityError(f"{mode}/detail-1 failed: run mode must be {mode}.")

    first_export_resp = client.get(f"/api/projects/{project_id}/exports/{first_run_id}.json")
    _require_status(f"{mode}/export-1", first_export_resp.status_code, 200, first_export_resp.text)
    first_export = first_export_resp.json()
    first_segments = first_export.get("segments", [])
    if not first_segments:
        raise LargeCorpusTraceabilityError(f"{mode}/export-1 failed: export must contain at least one segment.")

    second_run_resp = client.post(f"/api/projects/{project_id}/runs", json=run_payload)
    _require_status(f"{mode}/run-2", second_run_resp.status_code, 200, second_run_resp.text)
    second_run_id = second_run_resp.json()["run_id"]

    second_export_resp = client.get(f"/api/projects/{project_id}/exports/{second_run_id}.json")
    _require_status(f"{mode}/export-2", second_export_resp.status_code, 200, second_export_resp.text)
    second_export = second_export_resp.json()
    second_segments = second_export.get("segments", [])

    deterministic = first_segments == second_segments
    if not deterministic:
        raise LargeCorpusTraceabilityError(
            f"{mode}/determinism failed: rerun exports differ ({first_run_id} vs {second_run_id})."
        )

    return {
        "mode": mode,
        "run_id": first_run_id,
        "rerun_id": second_run_id,
        "segment_count": len(first_segments),
        "deterministic": deterministic,
    }


def run_large_corpus_traceability(client: TestClient, novel_path: Path) -> dict[str, Any]:
    report: dict[str, Any] = {
        "use_case": "USE-009",
        "name": "Large-corpus UC1/UC2/UC3 traceability regression",
        "status": "failed",
        "modes": [],
    }

    corpus_bytes, corpus_sha256 = _load_corpus_or_raise(novel_path)
    report["corpus_path"] = str(novel_path)
    report["corpus_sha256"] = corpus_sha256

    create_project_resp = client.post("/api/projects", json={"title": "Large Corpus Traceability Regression"})
    _require_status("project/create", create_project_resp.status_code, 201, create_project_resp.text)
    project_id = create_project_resp.json()["id"]
    report["project_id"] = project_id

    ingest_resp = client.post(
        f"/api/projects/{project_id}/ingest/txt",
        files={"file": (novel_path.name, io.BytesIO(corpus_bytes), "text/plain")},
    )
    _require_status("project/ingest", ingest_resp.status_code, 200, ingest_resp.text)
    chapter_count = ingest_resp.json()["chapter_count"]
    if chapter_count < 1:
        raise LargeCorpusTraceabilityError("project/ingest failed: chapter_count must be >= 1.")
    report["chapter_count"] = chapter_count

    # Keep UC-1 style prerequisites covered for the same corpus.
    import_resp = client.post(
        f"/api/projects/{project_id}/characters/import",
        files={"file": ("characters.json", io.BytesIO(_sample_character_map_json()), "application/json")},
    )
    _require_status("project/characters-import", import_resp.status_code, 200, import_resp.text)

    voice_resp = client.put(
        f"/api/projects/{project_id}/voices",
        json={
            "narrator_voice": "narrator_default",
            "male_default_voice": "male_default",
            "female_default_voice": "female_default",
        },
    )
    _require_status("project/voice-config", voice_resp.status_code, 200, voice_resp.text)

    for mode in LARGE_CORPUS_MODES:
        report["modes"].append(_run_mode_twice(client, project_id, mode))

    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    report["status"] = "passed"
    return report


def write_large_corpus_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
