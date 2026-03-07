from __future__ import annotations

import argparse
import os
from pathlib import Path
import shlex
import subprocess
import time
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"

DEFAULT_BACKEND_PORT = 8010
DEFAULT_HEALTH_TIMEOUT_SECONDS = 30.0
DEFAULT_DATABASE_URL = "sqlite:///./test_nipe_local_smoke.db"
DEFAULT_BACKEND_PYTEST_TARGET = "tests/test_api_smoke.py"
DEFAULT_FRONTEND_CONTRACT_TARGET = "tests/e2e/backend-endpoint-contract.e2e.spec.ts"
DEFAULT_FRONTEND_CONTRACT_GREP = "endpoint contracts with success and validation failures are exercised against live backend"


def resolve_backend_python(explicit_backend_python: str | None = None) -> Path:
    if explicit_backend_python:
        explicit_path = Path(explicit_backend_python).expanduser()
        if explicit_path.is_file():
            return explicit_path
        raise FileNotFoundError(f"Configured backend python not found: {explicit_path}")

    candidate_paths = [
        BACKEND_DIR / "venv" / "bin" / "python",
        BACKEND_DIR / ".venv" / "bin" / "python",
        BACKEND_DIR / ".venv311" / "bin" / "python",
    ]
    for candidate in candidate_paths:
        if candidate.is_file():
            return candidate

    raise FileNotFoundError(
        "Could not find a backend python interpreter. "
        "Expected one of: backend/venv/bin/python, backend/.venv/bin/python, backend/.venv311/bin/python."
    )


def build_backend_server_command(backend_python: Path, backend_port: int) -> list[str]:
    return [
        str(backend_python),
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(backend_port),
    ]


def build_backend_pytest_command(backend_python: Path, pytest_target: str) -> list[str]:
    return [str(backend_python), "-m", "pytest", pytest_target]


def build_frontend_contract_command(contract_target: str, contract_grep: str | None = None) -> list[str]:
    command = ["npm", "run", "test:e2e", "--", contract_target]
    if contract_grep and contract_grep.strip():
        command.extend(["--grep", contract_grep.strip()])
    return command


def wait_for_backend_health(base_url: str, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    health_url = f"{base_url}/health"

    while time.monotonic() < deadline:
        try:
            with urlopen(health_url, timeout=2.0) as response:
                if response.status == 200:
                    return
        except URLError:
            pass
        time.sleep(0.25)

    raise TimeoutError(f"Backend did not become healthy within {timeout_seconds:.1f}s at {health_url}")


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return

    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _shell_preview(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def _run_command(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    print(f"Running in {cwd}: {_shell_preview(command)}")
    subprocess.run(command, cwd=str(cwd), env=env, check=True)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run local backend/frontend smoke checks in one command.",
    )
    parser.add_argument("--backend-python", default=None, help="Optional explicit backend Python interpreter path.")
    parser.add_argument("--backend-port", type=int, default=DEFAULT_BACKEND_PORT)
    parser.add_argument("--database-url", default=DEFAULT_DATABASE_URL)
    parser.add_argument("--health-timeout-seconds", type=float, default=DEFAULT_HEALTH_TIMEOUT_SECONDS)
    parser.add_argument("--backend-pytest-target", default=DEFAULT_BACKEND_PYTEST_TARGET)
    parser.add_argument("--frontend-contract-target", default=DEFAULT_FRONTEND_CONTRACT_TARGET)
    parser.add_argument("--frontend-contract-grep", default=DEFAULT_FRONTEND_CONTRACT_GREP)
    parser.add_argument("--skip-backend-pytest", action="store_true")
    parser.add_argument("--skip-frontend-contract", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        backend_python = resolve_backend_python(args.backend_python)
    except FileNotFoundError as exc:
        print(f"Local smoke failed: {exc}")
        return 1

    backend_base_url = f"http://127.0.0.1:{args.backend_port}"
    backend_server_command = build_backend_server_command(backend_python, args.backend_port)
    backend_pytest_command = build_backend_pytest_command(backend_python, args.backend_pytest_target)
    frontend_contract_command = build_frontend_contract_command(
        args.frontend_contract_target,
        args.frontend_contract_grep,
    )

    print("Local smoke command plan:")
    print(f"- Backend server: {_shell_preview(backend_server_command)}")
    if not args.skip_backend_pytest:
        print(f"- Backend pytest: {_shell_preview(backend_pytest_command)}")
    if not args.skip_frontend_contract:
        print(f"- Frontend contract: {_shell_preview(frontend_contract_command)}")

    if args.dry_run:
        return 0

    backend_env = os.environ.copy()
    backend_env["DATABASE_URL"] = args.database_url
    backend_log_path = BACKEND_DIR / ".local_smoke_backend.log"

    process: subprocess.Popen[bytes] | None = None
    with backend_log_path.open("w", encoding="utf-8") as backend_log:
        try:
            process = subprocess.Popen(
                backend_server_command,
                cwd=str(BACKEND_DIR),
                env=backend_env,
                stdout=backend_log,
                stderr=subprocess.STDOUT,
            )

            wait_for_backend_health(backend_base_url, args.health_timeout_seconds)

            if not args.skip_backend_pytest:
                _run_command(backend_pytest_command, cwd=BACKEND_DIR, env=os.environ.copy())

            if not args.skip_frontend_contract:
                frontend_env = os.environ.copy()
                frontend_env["BACKEND_BASE_URL"] = backend_base_url
                _run_command(frontend_contract_command, cwd=FRONTEND_DIR, env=frontend_env)

        except (TimeoutError, subprocess.CalledProcessError) as exc:
            print(f"Local smoke failed: {exc}")
            print(f"Backend startup log: {backend_log_path}")
            return 1
        finally:
            if process is not None:
                _stop_process(process)

    print("Local smoke completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
