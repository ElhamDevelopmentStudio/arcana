from __future__ import annotations

from enum import StrEnum
from typing import TypedDict


class ProjectMode(StrEnum):
    AUDIOBOOK = "audiobook"
    ACADEMIC = "academic"
    AUTHOR = "author"
    CUSTOM = "custom"


MODE_VALUES: tuple[str, ...] = tuple(mode.value for mode in ProjectMode)
DEFAULT_MODE: str = ProjectMode.AUDIOBOOK.value

# Current persistence locations for selected mode.
MODE_PERSISTENCE_PATHS: tuple[str, ...] = ("projects.selected_mode", "runs.config_json.mode")


class ModeDefaultProfile(TypedDict):
    max_segment_chars: int
    llm_enabled: bool
    provider_name: str
    max_calls_per_day: int
    profile_intent: str


MODE_DEFAULT_PROFILES: dict[str, ModeDefaultProfile] = {
    ProjectMode.AUDIOBOOK.value: {
        "max_segment_chars": 120,
        "llm_enabled": False,
        "provider_name": "openrouter",
        "max_calls_per_day": 25,
        "profile_intent": "tts-ready segmentation and stable narration defaults",
    },
    ProjectMode.ACADEMIC.value: {
        "max_segment_chars": 220,
        "llm_enabled": False,
        "provider_name": "openrouter",
        "max_calls_per_day": 25,
        "profile_intent": "longer analytical segments for metric-friendly aggregation",
    },
    ProjectMode.AUTHOR.value: {
        "max_segment_chars": 160,
        "llm_enabled": False,
        "provider_name": "openrouter",
        "max_calls_per_day": 25,
        "profile_intent": "balanced segmentation for narrative-health diagnostics",
    },
    ProjectMode.CUSTOM.value: {
        "max_segment_chars": 255,
        "llm_enabled": False,
        "provider_name": "openrouter",
        "max_calls_per_day": 25,
        "profile_intent": "user-tuned baseline with conservative defaults",
    },
}


def is_valid_mode(value: str) -> bool:
    return value in MODE_VALUES


def get_mode_catalog() -> dict[str, object]:
    from app.services.mode_profiles import load_mode_profile_catalog

    return {
        "modes": list(MODE_VALUES),
        "default_mode": DEFAULT_MODE,
        "persisted_in": list(MODE_PERSISTENCE_PATHS),
        "mode_profiles": load_mode_profile_catalog(),
    }
