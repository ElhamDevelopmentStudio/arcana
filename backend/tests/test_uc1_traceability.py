import json
import os
from pathlib import Path
import subprocess
import sys

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_uc1_traceability.db"

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.main import app
from app.uc1_traceability import UC1_STEPS, run_uc1_traceability, write_uc1_report

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "backend" / "scripts_run_uc1_traceability.py"
REPORT_PATH = ROOT / "backend" / "reports" / "test_uc1_traceability_report.json"

EXPECTED_STEP_SNAPSHOT = [
    ("UC1-STEP-01", "POST /api/projects"),
    ("UC1-STEP-02", "POST /api/projects/{project_id}/ingest/txt"),
    ("UC1-STEP-03", "POST /api/projects/{project_id}/characters/import"),
    ("UC1-STEP-04", "PUT /api/projects/{project_id}/voices"),
    ("UC1-STEP-05", "POST /api/projects/{project_id}/runs"),
    ("UC1-STEP-06", "GET /api/projects/{project_id}/runs/{run_id}"),
    ("UC1-STEP-07", "GET /api/projects/{project_id}/exports/{run_id}.json"),
]


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_uc1_traceability.db")
    if db_file.exists():
        db_file.unlink()

    if REPORT_PATH.exists():
        REPORT_PATH.unlink()


def test_unit_write_uc1_report_creates_json_file() -> None:
    report = {
        "use_case": "UC-1",
        "status": "passed",
        "project_id": 11,
        "run_id": 7,
        "segment_count": 3,
        "steps": [],
    }
    write_uc1_report(REPORT_PATH, report)
    assert REPORT_PATH.exists()

    payload = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    assert payload["use_case"] == "UC-1"
    assert payload["status"] == "passed"
    assert payload["project_id"] == 11


def test_integration_uc1_traceability_flow_returns_passed_report() -> None:
    with TestClient(app) as client:
        report = run_uc1_traceability(client)

    assert report["use_case"] == "UC-1"
    assert report["status"] == "passed"
    assert report["segment_count"] >= 1
    assert len(report["steps"]) == 7
    assert all(step["passed"] for step in report["steps"])


def test_e2e_uc1_traceability_cli_succeeds_and_writes_report() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--output", str(REPORT_PATH)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
        env={**os.environ, "DATABASE_URL": "sqlite:///./test_nipe_uc1_traceability.db"},
    )
    assert result.returncode == 0
    assert "UC-1 traceability succeeded" in result.stdout
    assert REPORT_PATH.exists()

    payload = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert payload["use_case"] == "UC-1"
    assert len(payload["steps"]) == 7


def test_regression_uc1_step_sequence_snapshot() -> None:
    snapshot = [(step.step_id, step.endpoint) for step in UC1_STEPS]
    assert snapshot == EXPECTED_STEP_SNAPSHOT
