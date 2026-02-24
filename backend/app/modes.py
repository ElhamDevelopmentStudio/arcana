from __future__ import annotations

from enum import StrEnum


class ProjectMode(StrEnum):
    AUDIOBOOK = "audiobook"
    ACADEMIC = "academic"
    AUTHOR = "author"
    CUSTOM = "custom"


MODE_VALUES: tuple[str, ...] = tuple(mode.value for mode in ProjectMode)
DEFAULT_MODE: str = ProjectMode.AUDIOBOOK.value

# Current persistence locations for selected mode.
MODE_PERSISTENCE_PATHS: tuple[str, ...] = ("projects.selected_mode", "runs.config_json.mode")


def is_valid_mode(value: str) -> bool:
    return value in MODE_VALUES


def get_mode_catalog() -> dict[str, object]:
    return {
        "modes": list(MODE_VALUES),
        "default_mode": DEFAULT_MODE,
        "persisted_in": list(MODE_PERSISTENCE_PATHS),
    }
