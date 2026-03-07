import json
import os
from pathlib import Path
import subprocess
import sys

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_performance_regression_gate_unit.db"

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.main import app
from app.performance_regression_gate import (
    CORE_PIPELINE_MODES,
    collect_core_pipeline_performance_metrics,
    evaluate_performance_regression_gate,
    load_performance_regression_thresholds,
)

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "backend" / "scripts_run_performance_regression_gate.py"
THRESHOLDS_PATH = ROOT / "backend" / "performance_regression_thresholds.json"


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_performance_regression_gate_unit.db")
    if db_file.exists():
        db_file.unlink()


def test_unit_evaluate_gate_flags_threshold_violations() -> None:
    metrics = {
        "audiobook": {"total_duration_ms": 10, "segment_count": 2, "step_count": 11},
        "academic": {"total_duration_ms": 250, "segment_count": 2, "step_count": 11},
        "author": {"total_duration_ms": 20, "segment_count": 2, "step_count": 11},
        "custom": {"total_duration_ms": 30, "segment_count": 2, "step_count": 11},
    }
    thresholds = {"audiobook": 100, "academic": 200, "author": 100, "custom": 100}

    result = evaluate_performance_regression_gate(metrics=metrics, thresholds=thresholds)

    assert result["gate_passed"] is False
    assert "academic:250>200" in result["violations"]
    assert result["by_mode"]["audiobook"]["within_threshold"] is True
    assert result["by_mode"]["academic"]["within_threshold"] is False


def test_integration_collects_core_pipeline_performance_metrics_for_all_modes() -> None:
    with TestClient(app) as client:
        metrics = collect_core_pipeline_performance_metrics(client)

    assert tuple(metrics.keys()) == CORE_PIPELINE_MODES
    for mode in CORE_PIPELINE_MODES:
        payload = metrics[mode]
        assert payload["segment_count"] > 0
        assert payload["step_count"] > 0
        assert payload["total_duration_ms"] >= 0


def test_e2e_performance_regression_gate_script_succeeds_and_writes_report(tmp_path: Path) -> None:
    report_path = tmp_path / "performance_regression_gate_report.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--thresholds",
            str(THRESHOLDS_PATH),
            "--output",
            str(report_path),
            "--database-url",
            "sqlite:///./test_nipe_performance_regression_gate_e2e.db",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    assert "Performance regression gate passed." in result.stdout
    assert report_path.exists()

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["gate_result"]["gate_passed"] is True
    assert set(report["metrics"].keys()) == set(CORE_PIPELINE_MODES)


def test_regression_threshold_snapshot_matches_core_modes() -> None:
    thresholds = load_performance_regression_thresholds(THRESHOLDS_PATH)
    assert tuple(thresholds.keys()) == CORE_PIPELINE_MODES
    assert thresholds == {
        "audiobook": 3000,
        "academic": 3000,
        "author": 3000,
        "custom": 3000,
    }
