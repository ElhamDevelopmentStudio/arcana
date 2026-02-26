import subprocess
import sys
from pathlib import Path

import scripts_run_local_smoke as smoke

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "backend" / "scripts_run_local_smoke.py"


def test_unit_build_backend_server_command_snapshot() -> None:
    command = smoke.build_backend_server_command(Path("/tmp/backend-python"), 8010)
    assert command == [
        "/tmp/backend-python",
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8010",
    ]


def test_unit_build_frontend_contract_command_includes_grep_snapshot() -> None:
    command = smoke.build_frontend_contract_command(
        "tests/e2e/backend-endpoint-contract.e2e.spec.ts",
        "endpoint contracts with success and validation failures are exercised against live backend",
    )
    assert command == [
        "npm",
        "run",
        "test:e2e",
        "--",
        "tests/e2e/backend-endpoint-contract.e2e.spec.ts",
        "--grep",
        "endpoint contracts with success and validation failures are exercised against live backend",
    ]


def test_integration_dry_run_outputs_one_command_plan() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--dry-run", "--backend-python", sys.executable],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    assert "Local smoke command plan:" in result.stdout
    assert "tests/test_api_smoke.py" in result.stdout
    assert "tests/e2e/backend-endpoint-contract.e2e.spec.ts" in result.stdout
    assert "--grep" in result.stdout


def test_e2e_local_smoke_script_can_boot_health_and_shutdown() -> None:
    backend_python = smoke.resolve_backend_python()
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--backend-python",
            str(backend_python),
            "--backend-port",
            "8011",
            "--skip-backend-pytest",
            "--skip-frontend-contract",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    assert "Local smoke completed successfully." in result.stdout


def test_regression_local_smoke_default_targets_snapshot() -> None:
    assert smoke.DEFAULT_BACKEND_PYTEST_TARGET == "tests/test_api_smoke.py"
    assert smoke.DEFAULT_FRONTEND_CONTRACT_TARGET == "tests/e2e/backend-endpoint-contract.e2e.spec.ts"
    assert (
        smoke.DEFAULT_FRONTEND_CONTRACT_GREP
        == "endpoint contracts with success and validation failures are exercised against live backend"
    )
    assert smoke.DEFAULT_BACKEND_PORT == 8010
