import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_large_corpus_traceability.db"

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.large_corpus_traceability_regression import (
    LARGE_CORPUS_MODES,
    LargeCorpusTraceabilityError,
    run_large_corpus_traceability,
    write_large_corpus_report,
)
from app.main import app

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "backend" / "scripts_run_large_corpus_traceability.py"
NOVEL_PATH = ROOT / "novels_extra_chapter_0_to_22.txt"
REPORT_PATH = ROOT / "backend" / "reports" / "test_large_corpus_traceability_report.json"
RUN_SLOW = os.getenv("RUN_SLOW_TRACEABILITY") == "1"


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_large_corpus_traceability.db")
    if db_file.exists():
        db_file.unlink()

    if REPORT_PATH.exists():
        REPORT_PATH.unlink()


def test_unit_write_large_corpus_report_creates_json_file() -> None:
    report = {
        "use_case": "USE-009",
        "status": "passed",
        "project_id": 88,
        "chapter_count": 23,
        "modes": [],
    }
    write_large_corpus_report(REPORT_PATH, report)
    assert REPORT_PATH.exists()

    payload = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    assert payload["use_case"] == "USE-009"
    assert payload["status"] == "passed"
    assert payload["project_id"] == 88


def test_unit_run_large_corpus_traceability_raises_for_missing_fixture() -> None:
    with TestClient(app) as client:
        with pytest.raises(LargeCorpusTraceabilityError):
            run_large_corpus_traceability(client, ROOT / "missing_novel_fixture.txt")


@pytest.mark.slow
def test_integration_large_corpus_traceability_flow_returns_passed_report() -> None:
    if not RUN_SLOW:
        pytest.skip("Set RUN_SLOW_TRACEABILITY=1 to execute USE-009 slow integration suite.")
    assert NOVEL_PATH.exists(), "novels_extra_chapter_0_to_22.txt is required for USE-009"

    with TestClient(app) as client:
        report = run_large_corpus_traceability(client, NOVEL_PATH)

    assert report["use_case"] == "USE-009"
    assert report["status"] == "passed"
    assert report["chapter_count"] >= 1
    assert [entry["mode"] for entry in report["modes"]] == LARGE_CORPUS_MODES
    assert all(entry["deterministic"] is True for entry in report["modes"])


@pytest.mark.slow
def test_e2e_large_corpus_traceability_cli_succeeds_and_writes_report() -> None:
    if not RUN_SLOW:
        pytest.skip("Set RUN_SLOW_TRACEABILITY=1 to execute USE-009 slow CLI suite.")
    assert NOVEL_PATH.exists(), "novels_extra_chapter_0_to_22.txt is required for USE-009"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--allow-slow",
            "--novel-path",
            str(NOVEL_PATH),
            "--output",
            str(REPORT_PATH),
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
        env={**os.environ, "DATABASE_URL": "sqlite:///./test_nipe_large_corpus_traceability.db"},
    )
    assert result.returncode == 0
    assert "USE-009 large-corpus traceability succeeded" in result.stdout
    assert REPORT_PATH.exists()

    payload = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert payload["use_case"] == "USE-009"
    assert [entry["mode"] for entry in payload["modes"]] == LARGE_CORPUS_MODES


def test_regression_large_corpus_mode_sequence_snapshot() -> None:
    assert LARGE_CORPUS_MODES == ["audiobook", "academic", "author"]
