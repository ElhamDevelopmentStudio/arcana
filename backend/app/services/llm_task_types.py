from enum import Enum


class LLMTaskType(str, Enum):
    """Canonical task-type vocabulary for LLM routing and logging."""

    SENTIMENT_PROBE = "sentiment_probe"
    EMOTION_REFINEMENT = "emotion_refinement"
    SPEAKER_RESOLUTION = "speaker_resolution"
    CHARACTER_EXTRACTION = "character_extraction"
    EDGE_CASE_STRUCTURAL_INTERPRETATION = "edge_case_structural_interpretation"
    SCENE_CLASSIFICATION = "scene_classification"


SUPPORTED_LLM_TASK_TYPES = tuple(task_type.value for task_type in LLMTaskType)


class LLMTaskTypeError(ValueError):
    """Raised for unsupported LLM task types."""

    def __init__(self, task_type: str):
        super().__init__(
            f"unsupported llm task_type: '{task_type}'. Supported task types: "
            f"{', '.join(SUPPORTED_LLM_TASK_TYPES)}"
        )


def normalize_task_type(task_type: str) -> str:
    """Normalize and validate a raw LLM task type value."""
    normalized = str(task_type).strip().lower()
    if normalized not in SUPPORTED_LLM_TASK_TYPES:
        raise LLMTaskTypeError(task_type=str(task_type))
    return normalized


def is_supported_task_type(task_type: str) -> bool:
    """Return whether a task type is part of the enumerated LLM task set."""
    return str(task_type).strip().lower() in SUPPORTED_LLM_TASK_TYPES
