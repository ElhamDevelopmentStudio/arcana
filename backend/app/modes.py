from __future__ import annotations

from enum import StrEnum


class ProjectMode(StrEnum):
    AUDIOBOOK = "audiobook"
    ACADEMIC = "academic"
    AUTHOR = "author"
    CUSTOM = "custom"


MODE_VALUES: tuple[str, ...] = tuple(mode.value for mode in ProjectMode)
DEFAULT_MODE: str = ProjectMode.AUDIOBOOK.value

# Current PoC persistence location for selected mode.
MODE_PERSISTENCE_PATHS: tuple[str, ...] = ("runs.config_json.mode",)


def is_valid_mode(value: str) -> bool:
    return value in MODE_VALUES
