import pytest

from app.services import pipeline
from app.services.pipeline import PipelineError


def _record_stage(step_records: list[dict[str, object]], stage_name: str, completed_stages: list[str]) -> None:
    with pipeline._record_pipeline_stage(
        step_records=step_records,
        stage_name=stage_name,
        completed_stages=completed_stages,
    ):
        return


def test_pipeline_stage_guard_rejects_out_of_order_transition() -> None:
    completed_stages: list[str] = []
    with pytest.raises(PipelineError):
        _record_stage([], "run_llm_probe", completed_stages)


def test_pipeline_stage_guard_rejects_duplicate_stage() -> None:
    completed_stages: list[str] = []
    _record_stage([], "load_and_validate_source_data", completed_stages)

    with pytest.raises(PipelineError):
        _record_stage([], "load_and_validate_source_data", completed_stages)


def test_pipeline_stage_guard_allows_all_valid_paths() -> None:
    expected_no_copy_stage_flow = [
        stage for stage in pipeline._PIPELINE_STAGE_ORDER if stage != "copy_incremental_segments"
    ]
    no_copy: list[str] = []
    for stage in (
        "load_and_validate_source_data",
        "persist_normalized_corpus_blob",
        "load_project_artifacts",
        "clear_previous_run_artifacts",
        "resolve_incremental_recompute_scope",
        "build_chunking_plan",
        "build_chunk_payloads",
        "merge_segment_payloads",
        "run_llm_probe",
        "derive_character_analytics",
        "finalize_run_and_build_export",
    ):
        _record_stage([], stage, no_copy)
    assert no_copy == expected_no_copy_stage_flow

    with_copy: list[str] = []
    for stage in (
        "load_and_validate_source_data",
        "persist_normalized_corpus_blob",
        "load_project_artifacts",
        "clear_previous_run_artifacts",
        "resolve_incremental_recompute_scope",
        "build_chunking_plan",
        "copy_incremental_segments",
        "build_chunk_payloads",
        "merge_segment_payloads",
        "run_llm_probe",
        "derive_character_analytics",
        "finalize_run_and_build_export",
    ):
        _record_stage([], stage, with_copy)
    assert with_copy == [
        *pipeline._PIPELINE_STAGE_ORDER[:6],
        "copy_incremental_segments",
        *pipeline._PIPELINE_STAGE_ORDER[7:],
    ]
