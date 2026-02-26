from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def _normalize_module_key(module_key: str) -> str:
    normalized = module_key.strip().replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _normalize_coverage_file_path(file_path: str) -> str:
    normalized = file_path.strip().replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    app_marker = "/app/"
    app_marker_index = normalized.rfind(app_marker)
    if app_marker_index >= 0:
        return normalized[app_marker_index + 1 :]
    return normalized


def load_module_thresholds(path: Path) -> dict[str, float]:
    raw_payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw_payload, Mapping):
        raise ValueError("Threshold payload must be a JSON object.")

    raw_modules = raw_payload.get("modules")
    if not isinstance(raw_modules, Mapping):
        raise ValueError("Threshold payload must define a 'modules' object.")

    normalized_thresholds: dict[str, float] = {}
    for raw_module_key, raw_threshold in raw_modules.items():
        if not isinstance(raw_module_key, str):
            raise ValueError("Module keys must be strings.")
        module_key = _normalize_module_key(raw_module_key)
        if not module_key:
            raise ValueError("Module keys must not be blank.")
        if not isinstance(raw_threshold, (int, float)):
            raise ValueError(f"Threshold for '{module_key}' must be numeric.")
        threshold = float(raw_threshold)
        if threshold < 0 or threshold > 100:
            raise ValueError(f"Threshold for '{module_key}' must be between 0 and 100.")
        normalized_thresholds[module_key] = threshold

    if not normalized_thresholds:
        raise ValueError("At least one module threshold is required.")
    return normalized_thresholds


def load_file_line_summaries(path: Path) -> dict[str, tuple[int, int]]:
    raw_payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw_payload, Mapping):
        raise ValueError("Coverage payload must be a JSON object.")

    raw_files = raw_payload.get("files")
    if not isinstance(raw_files, Mapping):
        raise ValueError("Coverage payload must define a 'files' object.")

    summaries: dict[str, tuple[int, int]] = {}
    for raw_file_path, raw_file_payload in raw_files.items():
        if not isinstance(raw_file_path, str) or not isinstance(raw_file_payload, Mapping):
            continue
        summary_payload = raw_file_payload.get("summary")
        if not isinstance(summary_payload, Mapping):
            continue

        try:
            covered_lines = int(summary_payload.get("covered_lines", 0))
            total_lines = int(summary_payload.get("num_statements", 0))
        except (TypeError, ValueError):
            continue

        if covered_lines < 0 or total_lines < 0:
            continue
        normalized_path = _normalize_coverage_file_path(raw_file_path)
        if not normalized_path:
            continue
        summaries[normalized_path] = (covered_lines, total_lines)

    if not summaries:
        raise ValueError("Coverage payload did not contain any usable file summaries.")
    return summaries


def _is_exact_file_match(module_key: str) -> bool:
    return module_key.endswith(".py")


def _matches_module(file_path: str, module_key: str) -> bool:
    if _is_exact_file_match(module_key):
        return file_path == module_key

    module_prefix = module_key if module_key.endswith("/") else f"{module_key}/"
    return file_path.startswith(module_prefix)


def evaluate_module_thresholds(
    file_line_summaries: Mapping[str, tuple[int, int]],
    module_thresholds: Mapping[str, float],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for module_key, threshold in module_thresholds.items():
        matching_paths = [path for path in file_line_summaries if _matches_module(path, module_key)]
        covered_lines = sum(file_line_summaries[path][0] for path in matching_paths)
        total_lines = sum(file_line_summaries[path][1] for path in matching_paths)
        if total_lines <= 0:
            coverage_percent = 0.0
            passed = False
            reason = "no_matching_files"
        else:
            coverage_percent = (covered_lines / total_lines) * 100.0
            passed = coverage_percent >= threshold
            reason = "ok" if passed else "below_threshold"

        results.append(
            {
                "module": module_key,
                "threshold": float(threshold),
                "coverage_percent": round(coverage_percent, 2),
                "covered_lines": covered_lines,
                "total_lines": total_lines,
                "matched_files": matching_paths,
                "passed": passed,
                "reason": reason,
            }
        )
    return results


def run_validation(*, coverage_json_path: Path, thresholds_path: Path) -> list[dict[str, Any]]:
    module_thresholds = load_module_thresholds(thresholds_path)
    file_line_summaries = load_file_line_summaries(coverage_json_path)
    return evaluate_module_thresholds(file_line_summaries, module_thresholds)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate backend module coverage thresholds from coverage.py JSON output.",
    )
    parser.add_argument(
        "--coverage-json",
        default="coverage.unit.json",
        help="Path to coverage.py JSON report (default: coverage.unit.json).",
    )
    parser.add_argument(
        "--thresholds",
        default="unit_coverage_thresholds.json",
        help="Path to module thresholds JSON file (default: unit_coverage_thresholds.json).",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    coverage_json_path = Path(args.coverage_json).resolve()
    thresholds_path = Path(args.thresholds).resolve()

    results = run_validation(
        coverage_json_path=coverage_json_path,
        thresholds_path=thresholds_path,
    )
    failures = [result for result in results if not bool(result["passed"])]
    for result in results:
        status = "PASS" if result["passed"] else "FAIL"
        print(
            f"[{status}] {result['module']}: {result['coverage_percent']:.2f}% "
            f"(threshold {result['threshold']:.2f}%, lines {result['covered_lines']}/{result['total_lines']})"
        )

    if failures:
        print("Unit coverage threshold validation failed.")
        return 1

    print("Unit coverage threshold validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
