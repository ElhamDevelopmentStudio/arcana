#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


DEFAULT_GPU_SAFETY = {
    "enabled": True,
    "power_limit_mode": "percent",
    "power_limit_percent": 85,
    "power_limit_watts": None,
    "min_power_watts": 80,
    "max_temp_c": 82,
    "util_target_min": 70,
    "util_target_max": 85,
    "max_slowdown_ratio": 2.0,
    "autotune": True,
    "autotune_step_watts": 5,
    "update_interval_sec": 20,
    "log_path": "data/processed/audio_logs/gpu_safety.jsonl",
}


@dataclass(frozen=True)
class GPUStats:
    power_limit_w: float | None
    power_max_w: float | None
    temperature_c: float | None
    utilization_pct: float | None


def _nvidia_smi_path() -> str | None:
    return shutil.which("nvidia-smi")


def _run_nvidia_smi(args: list[str]) -> str | None:
    if not _nvidia_smi_path():
        return None
    try:
        result = subprocess.run(
            ["nvidia-smi", *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except Exception:
        return None
    return result.stdout.strip()


def _query_gpu_values(fields: list[str]) -> dict[str, float | None]:
    raw = _run_nvidia_smi(
        [f"--query-gpu={','.join(fields)}", "--format=csv,noheader,nounits"]
    )
    if not raw:
        return {field: None for field in fields}
    first = raw.splitlines()[0]
    parts = [p.strip() for p in first.split(",")]
    values: dict[str, float | None] = {}
    for field, part in zip(fields, parts):
        try:
            values[field] = float(part)
        except Exception:
            values[field] = None
    for field in fields:
        values.setdefault(field, None)
    return values


def query_gpu_stats() -> GPUStats:
    fields = [
        "power.limit",
        "power.max_limit",
        "temperature.gpu",
        "utilization.gpu",
    ]
    values = _query_gpu_values(fields)
    return GPUStats(
        power_limit_w=values.get("power.limit"),
        power_max_w=values.get("power.max_limit"),
        temperature_c=values.get("temperature.gpu"),
        utilization_pct=values.get("utilization.gpu"),
    )


def set_power_limit(watts: float) -> bool:
    if not _nvidia_smi_path():
        return False
    try:
        subprocess.run(
            ["nvidia-smi", "-pl", str(int(round(watts)))],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return True
    except Exception:
        return False


def load_gpu_safety(path: Path | None) -> dict:
    config = dict(DEFAULT_GPU_SAFETY)
    if path and path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                config.update({k: data[k] for k in data.keys()})
        except Exception:
            pass
    return config


class GPUSafetyController:
    def __init__(
        self,
        config: dict,
        baseline_throughput: float | None = None,
        mode: str = "generation",
    ) -> None:
        self.config = config
        self.baseline_throughput = baseline_throughput
        self.mode = mode
        self.enabled = bool(config.get("enabled", True))
        self.autotune = bool(config.get("autotune", True))
        self.step_watts = float(config.get("autotune_step_watts", 5))
        self.min_power = float(config.get("min_power_watts", 0))
        self.max_slowdown = float(config.get("max_slowdown_ratio", 2.0))
        self.util_min = float(config.get("util_target_min", 70))
        self.util_max = float(config.get("util_target_max", 85))
        self.max_temp = float(config.get("max_temp_c", 82))
        self.update_interval = float(config.get("update_interval_sec", 20))
        self.log_path = Path(str(config.get("log_path", ""))) if config.get("log_path") else None
        self.last_update = 0.0
        self.current_limit = None
        self.power_max = None

    def apply_initial_limit(self) -> None:
        if not self.enabled or not _nvidia_smi_path():
            return
        stats = query_gpu_stats()
        self.power_max = stats.power_max_w
        if stats.power_max_w is None:
            return
        mode = str(self.config.get("power_limit_mode", "percent")).lower()
        if mode == "watts":
            target = float(self.config.get("power_limit_watts", stats.power_max_w))
        else:
            percent = float(self.config.get("power_limit_percent", 85))
            target = stats.power_max_w * (percent / 100.0)
        target = max(self.min_power, min(target, stats.power_max_w))
        if set_power_limit(target):
            self.current_limit = target
            self._log_event("apply_initial", stats, target, None)

    def update(self, throughput: float | None = None) -> None:
        if not self.enabled or not self.autotune or not _nvidia_smi_path():
            return
        now = time.time()
        if now - self.last_update < self.update_interval:
            return
        self.last_update = now
        stats = query_gpu_stats()
        if stats.power_max_w is not None:
            self.power_max = stats.power_max_w
        if self.power_max is None:
            return
        if self.current_limit is None and stats.power_limit_w is not None:
            self.current_limit = stats.power_limit_w
        if self.current_limit is None:
            self.current_limit = self.power_max

        desired = self.current_limit
        reason = None
        if stats.temperature_c is not None and stats.temperature_c >= self.max_temp:
            desired = self.current_limit - self.step_watts
            reason = "temp_high"
        elif self.baseline_throughput and throughput is not None:
            floor = self.baseline_throughput / max(self.max_slowdown, 1e-6)
            if throughput < floor:
                desired = self.current_limit + self.step_watts
                reason = "throughput_low"
        if reason is None and stats.utilization_pct is not None:
            if stats.utilization_pct < self.util_min:
                desired = self.current_limit + self.step_watts
                reason = "util_low"
            elif stats.utilization_pct > self.util_max and stats.temperature_c is not None:
                if stats.temperature_c >= self.max_temp - 1:
                    desired = self.current_limit - self.step_watts
                    reason = "util_high_temp"

        desired = max(self.min_power, min(desired, self.power_max))
        if abs(desired - self.current_limit) >= 1:
            if set_power_limit(desired):
                self.current_limit = desired
                self._log_event("adjust", stats, desired, reason)

    def _log_event(
        self,
        action: str,
        stats: GPUStats,
        limit_w: float | None,
        reason: str | None,
    ) -> None:
        if not self.log_path:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": round(time.time(), 3),
            "action": action,
            "mode": self.mode,
            "reason": reason,
            "limit_w": round(limit_w, 2) if limit_w is not None else None,
            "power_max_w": stats.power_max_w,
            "temp_c": stats.temperature_c,
            "util_pct": stats.utilization_pct,
        }
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
