from __future__ import annotations

from copy import deepcopy

from app.modes import DEFAULT_MODE, MODE_DEFAULT_PROFILES, MODE_VALUES, ModeDefaultProfile, is_valid_mode


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
