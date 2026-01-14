from __future__ import annotations

from enum import Enum
from app.services.tagging import (
    TAG_HIGH_AMBIGUITY_DIALOGUE_FLAG_THRESHOLD,
    TAG_LOW_CONFIDENCE_THRESHOLD,
    TAG_UNSTABLE_RAPID_EMOTION_SHIFT_DENSITY,
    TAG_UNSTABLE_RAPID_EMOTION_SHIFT_THRESHOLD,
)
try:
    from enum import StrEnum
except ImportError:  # pragma: no cover
    class StrEnum(str, Enum):
        """Fallback for Python versions without enum.StrEnum."""

        def __str__(self) -> str:
            return self.value

        def __format__(self, format_spec: str) -> str:
            return str.__format__(self.value, format_spec)

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
    llm_confidence_threshold: float
    speaker_confidence_threshold: float
    high_ambiguity_dialogue_flag_threshold: int
    unstable_emotion_shift_transition_threshold: int
    unstable_emotion_shift_density_threshold: float
    deep_semantic_refinement: bool
    deterministic_mode: bool
    web_scraping_enabled: bool
    profile_intent: str


MODE_DEFAULT_PROFILES: dict[str, ModeDefaultProfile] = {
    ProjectMode.AUDIOBOOK.value: {
        "max_segment_chars": 120,
        "llm_enabled": False,
        "provider_name": "openrouter",
        "max_calls_per_day": 25,
        "llm_confidence_threshold": 0.6,
        "speaker_confidence_threshold": TAG_LOW_CONFIDENCE_THRESHOLD,
        "high_ambiguity_dialogue_flag_threshold": TAG_HIGH_AMBIGUITY_DIALOGUE_FLAG_THRESHOLD,
        "unstable_emotion_shift_transition_threshold": TAG_UNSTABLE_RAPID_EMOTION_SHIFT_THRESHOLD,
        "unstable_emotion_shift_density_threshold": TAG_UNSTABLE_RAPID_EMOTION_SHIFT_DENSITY,
        "deep_semantic_refinement": False,
        "deterministic_mode": False,
        "web_scraping_enabled": False,
        "profile_intent": "tts-ready segmentation and stable narration defaults",
    },
    ProjectMode.ACADEMIC.value: {
        "max_segment_chars": 220,
        "llm_enabled": False,
        "provider_name": "openrouter",
        "max_calls_per_day": 25,
        "llm_confidence_threshold": 0.6,
        "speaker_confidence_threshold": TAG_LOW_CONFIDENCE_THRESHOLD,
        "high_ambiguity_dialogue_flag_threshold": TAG_HIGH_AMBIGUITY_DIALOGUE_FLAG_THRESHOLD,
        "unstable_emotion_shift_transition_threshold": TAG_UNSTABLE_RAPID_EMOTION_SHIFT_THRESHOLD,
        "unstable_emotion_shift_density_threshold": TAG_UNSTABLE_RAPID_EMOTION_SHIFT_DENSITY,
        "deep_semantic_refinement": False,
        "deterministic_mode": False,
        "web_scraping_enabled": False,
        "profile_intent": "longer analytical segments for metric-friendly aggregation",
    },
    ProjectMode.AUTHOR.value: {
        "max_segment_chars": 160,
        "llm_enabled": False,
        "provider_name": "openrouter",
        "max_calls_per_day": 25,
        "llm_confidence_threshold": 0.6,
        "speaker_confidence_threshold": TAG_LOW_CONFIDENCE_THRESHOLD,
        "high_ambiguity_dialogue_flag_threshold": TAG_HIGH_AMBIGUITY_DIALOGUE_FLAG_THRESHOLD,
        "unstable_emotion_shift_transition_threshold": TAG_UNSTABLE_RAPID_EMOTION_SHIFT_THRESHOLD,
        "unstable_emotion_shift_density_threshold": TAG_UNSTABLE_RAPID_EMOTION_SHIFT_DENSITY,
        "deep_semantic_refinement": False,
        "deterministic_mode": False,
        "web_scraping_enabled": False,
        "profile_intent": "balanced segmentation for narrative-health diagnostics",
    },
    ProjectMode.CUSTOM.value: {
        "max_segment_chars": 255,
        "llm_enabled": False,
        "provider_name": "openrouter",
        "max_calls_per_day": 25,
        "llm_confidence_threshold": 0.6,
        "speaker_confidence_threshold": TAG_LOW_CONFIDENCE_THRESHOLD,
        "high_ambiguity_dialogue_flag_threshold": TAG_HIGH_AMBIGUITY_DIALOGUE_FLAG_THRESHOLD,
        "unstable_emotion_shift_transition_threshold": TAG_UNSTABLE_RAPID_EMOTION_SHIFT_THRESHOLD,
        "unstable_emotion_shift_density_threshold": TAG_UNSTABLE_RAPID_EMOTION_SHIFT_DENSITY,
        "deep_semantic_refinement": False,
        "deterministic_mode": False,
        "web_scraping_enabled": False,
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
