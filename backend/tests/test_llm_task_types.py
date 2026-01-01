from app.services.llm_router import LLMRequest, LLMRouter
from app.services.llm_task_types import (
    SUPPORTED_LLM_TASK_TYPES,
    is_supported_task_type,
    normalize_task_type,
    LLMTaskTypeError,
    LLMTaskType,
)


def test_supported_llm_task_types_include_expected_members() -> None:
    assert LLMTaskType.SENTIMENT_PROBE.value in SUPPORTED_LLM_TASK_TYPES
    assert LLMTaskType.EMOTION_REFINEMENT.value in SUPPORTED_LLM_TASK_TYPES
    assert LLMTaskType.SPEAKER_RESOLUTION.value in SUPPORTED_LLM_TASK_TYPES
    assert LLMTaskType.EDGE_CASE_STRUCTURAL_INTERPRETATION.value in SUPPORTED_LLM_TASK_TYPES
    assert LLMTaskType.SCENE_CLASSIFICATION.value in SUPPORTED_LLM_TASK_TYPES


def test_normalize_task_type_is_case_and_whitespace_tolerant() -> None:
    assert normalize_task_type("  Emotion_Refinement  ") == LLMTaskType.EMOTION_REFINEMENT.value


def test_normalize_task_type_rejects_unknown_values() -> None:
    try:
        normalize_task_type("unsupported_task")
    except LLMTaskTypeError as exc:
        assert "unsupported llm task_type" in str(exc)
    else:
        raise AssertionError("Expected unsupported task type to raise an exception")


def test_is_supported_task_type_helper_matches_normalizer() -> None:
    assert is_supported_task_type("scene_classification") is True
    assert is_supported_task_type("not_real_task") is False


def test_llm_router_rejects_unsupported_task_type_without_calling_provider() -> None:
    router = LLMRouter(openrouter_base_url="https://example.test")
    response = router.call(
        request=LLMRequest(
            request_id="unsupported-task",
            project_id=1,
            task_type="unsupported_task",
            input_text="Hello.",
            expected_schema={},
            configuration_snapshot_id="unsupported-task-check",
        ),
        provider_name="openrouter",
        model_identifier="dummy-model",
        api_key=None,
    )

    assert response.success_flag is False
    assert response.error_code == "unsupported_task_type"
    assert response.raw_output == ""
