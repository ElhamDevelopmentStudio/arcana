import json
import os
from pathlib import Path
import subprocess
import sys

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_uc3_traceability.db"

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.main import app
from app.uc3_traceability import UC3_STEPS, run_uc3_traceability, write_uc3_report

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "backend" / "scripts_run_uc3_traceability.py"
REPORT_PATH = ROOT / "backend" / "reports" / "test_uc3_traceability_report.json"

EXPECTED_STEP_SNAPSHOT = [
    ("UC3-STEP-01", "POST /api/projects"),
    ("UC3-STEP-02", "POST /api/projects/{project_id}/ingest/txt"),
    ("UC3-STEP-03", "POST /api/projects/{project_id}/runs"),
    ("UC3-STEP-04", "GET /api/projects/{project_id}/runs/{run_id}"),
    ("UC3-STEP-05", "GET /api/projects/{project_id}/exports/{run_id}.json"),
    ("UC3-STEP-06", "GET /api/projects/{project_id}/exports/{run_id}.json"),
    ("UC3-STEP-07", "POST /api/projects/{project_id}/runs"),
]


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_uc3_traceability.db")
    if db_file.exists():
        db_file.unlink()

    if REPORT_PATH.exists():
        REPORT_PATH.unlink()


def test_unit_write_uc3_report_creates_json_file() -> None:
    report = {
        "use_case": "UC-3",
        "status": "passed",
        "project_id": 31,
        "run_id": 8,
        "rerun_id": 9,
        "segment_count": 4,
        "steps": [],
    }
    write_uc3_report(REPORT_PATH, report)
    assert REPORT_PATH.exists()

    payload = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    assert payload["use_case"] == "UC-3"
    assert payload["status"] == "passed"
    assert payload["project_id"] == 31


def test_integration_uc3_traceability_flow_returns_passed_report() -> None:
    with TestClient(app) as client:
        report = run_uc3_traceability(client)

    assert report["use_case"] == "UC-3"
    assert report["status"] == "passed"
    assert report["segment_count"] >= 1
    assert report["deterministic"] is True
    assert len(report["steps"]) == 7
    assert all(step["passed"] for step in report["steps"])


def test_e2e_uc3_traceability_cli_succeeds_and_writes_report() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--output", str(REPORT_PATH)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
        env={**os.environ, "DATABASE_URL": "sqlite:///./test_nipe_uc3_traceability.db"},
    )
    assert result.returncode == 0
    assert "UC-3 traceability succeeded" in result.stdout
    assert REPORT_PATH.exists()

    payload = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert payload["use_case"] == "UC-3"
    assert payload["deterministic"] is True
    assert len(payload["steps"]) == 7


def test_regression_uc3_step_sequence_snapshot() -> None:
    snapshot = [(step.step_id, step.endpoint) for step in UC3_STEPS]
    assert snapshot == EXPECTED_STEP_SNAPSHOT
