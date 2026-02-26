from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from app.modes import DEFAULT_MODE, MODE_DEFAULT_PROFILES, MODE_VALUES, ModeDefaultProfile, is_valid_mode

PROFILE_CONFIG_KEYS: tuple[str, ...] = (
    "max_segment_chars",
    "llm_enabled",
    "provider_name",
    "max_calls_per_day",
    "llm_confidence_threshold",
    "deep_semantic_refinement",
    "deterministic_mode",
)


def normalize_mode_value(mode: str | None) -> str:
    if mode is None:
        return DEFAULT_MODE

    normalized = str(mode).strip().lower()
    if not normalized:
        return DEFAULT_MODE
    if not is_valid_mode(normalized):
        raise ValueError(f"Unknown mode: {mode}")
    return normalized


def load_mode_profile(mode: str | None) -> ModeDefaultProfile:
    normalized_mode = normalize_mode_value(mode)
    return deepcopy(MODE_DEFAULT_PROFILES[normalized_mode])


def load_mode_profile_catalog() -> dict[str, ModeDefaultProfile]:
    return {mode: load_mode_profile(mode) for mode in MODE_VALUES}


def build_run_config_snapshot(mode: str | None, overrides: Mapping[str, Any] | None = None) -> dict[str, Any]:
    normalized_mode = normalize_mode_value(mode)
    profile_snapshot = load_mode_profile(normalized_mode)

    resolved_profile_config: dict[str, Any] = {
        key: profile_snapshot[key]
        for key in PROFILE_CONFIG_KEYS
    }
    if overrides:
        for key in PROFILE_CONFIG_KEYS:
            if key in overrides and overrides[key] is not None:
                resolved_profile_config[key] = overrides[key]

    return {
        "mode": normalized_mode,
        **resolved_profile_config,
        "mode_profile_snapshot": profile_snapshot,
    }
