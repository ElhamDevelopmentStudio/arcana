import json
import os
from pathlib import Path
import subprocess
import sys

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_uc2_traceability.db"

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.main import app
from app.uc2_traceability import UC2_STEPS, run_uc2_traceability, write_uc2_report

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "backend" / "scripts_run_uc2_traceability.py"
REPORT_PATH = ROOT / "backend" / "reports" / "test_uc2_traceability_report.json"

EXPECTED_STEP_SNAPSHOT = [
    ("UC2-STEP-01", "POST /api/projects"),
    ("UC2-STEP-02", "POST /api/projects/{project_id}/ingest/txt"),
    ("UC2-STEP-03", "POST /api/projects/{project_id}/runs"),
    ("UC2-STEP-04", "GET /api/projects/{project_id}/runs/{run_id}"),
    ("UC2-STEP-05", "GET /api/projects/{project_id}/exports/{run_id}.json"),
    ("UC2-STEP-06", "POST /api/projects/{project_id}/runs"),
]


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_uc2_traceability.db")
    if db_file.exists():
        db_file.unlink()

    if REPORT_PATH.exists():
        REPORT_PATH.unlink()


def test_unit_write_uc2_report_creates_json_file() -> None:
    report = {
        "use_case": "UC-2",
        "status": "passed",
        "project_id": 21,
        "run_id": 5,
        "rerun_id": 6,
        "segment_count": 4,
        "steps": [],
    }
    write_uc2_report(REPORT_PATH, report)
    assert REPORT_PATH.exists()

    payload = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    assert payload["use_case"] == "UC-2"
    assert payload["status"] == "passed"
    assert payload["project_id"] == 21


def test_integration_uc2_traceability_flow_returns_passed_report() -> None:
    with TestClient(app) as client:
        report = run_uc2_traceability(client)

    assert report["use_case"] == "UC-2"
    assert report["status"] == "passed"
    assert report["segment_count"] >= 1
    assert report["deterministic"] is True
    assert len(report["steps"]) == 6
    assert all(step["passed"] for step in report["steps"])


def test_e2e_uc2_traceability_cli_succeeds_and_writes_report() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--output", str(REPORT_PATH)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
        env={**os.environ, "DATABASE_URL": "sqlite:///./test_nipe_uc2_traceability.db"},
    )
    assert result.returncode == 0
    assert "UC-2 traceability succeeded" in result.stdout
    assert REPORT_PATH.exists()

    payload = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert payload["use_case"] == "UC-2"
    assert payload["deterministic"] is True
    assert len(payload["steps"]) == 6


def test_regression_uc2_step_sequence_snapshot() -> None:
    snapshot = [(step.step_id, step.endpoint) for step in UC2_STEPS]
    assert snapshot == EXPECTED_STEP_SNAPSHOT
