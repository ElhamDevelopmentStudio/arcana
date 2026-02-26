import pytest
from pydantic import ValidationError

from app.schemas import ProjectControlPanelSummaryResponse


def test_unit_project_control_panel_summary_contract_defaults() -> None:
    payload = ProjectControlPanelSummaryResponse(
        generated_at="2026-02-26T00:00:00Z",
        total_projects=6,
        project_counts_by_state=[
            {"lifecycle_state": "draft", "project_count": 2},
            {"lifecycle_state": "ingested", "project_count": 3},
            {"lifecycle_state": "failed", "project_count": 1},
        ],
        active_run_count=2,
        blocked_export_project_count=2,
        blocked_export_run_count=3,
        recent_failure_count=1,
        recent_failures=[
            {
                "project_id": 42,
                "project_title": "Control Panel Failure Example",
                "run_id": 88,
                "failed_at": "2026-02-25T22:15:00Z",
                "error_code": "pipeline_failed",
                "error_message": "Pipeline error: no chapters available.",
            }
        ],
    )

    assert payload.schema_version == "1.0.0"
    assert payload.output_schema == "project_control_panel_summary_json"
    assert payload.output_format == "json"
    assert payload.output_id == "CP-001"
    assert payload.output_name == "project_control_panel_summary"


def test_integration_project_control_panel_summary_contract_accepts_minimal_payload() -> None:
    payload = ProjectControlPanelSummaryResponse.model_validate(
        {
            "generated_at": "2026-02-26T02:00:00Z",
            "generated_by": "dashboard_aggregate_job",
            "total_projects": 0,
            "project_counts_by_state": [],
            "active_run_count": 0,
            "blocked_export_project_count": 0,
            "blocked_export_run_count": 0,
            "recent_failure_count": 0,
            "recent_failures": [],
        }
    )

    assert payload.generated_by == "dashboard_aggregate_job"
    assert payload.total_projects == 0
    assert payload.recent_failures == []


def test_regression_project_control_panel_summary_rejects_unknown_lifecycle_state() -> None:
    with pytest.raises(ValidationError):
        ProjectControlPanelSummaryResponse(
            generated_at="2026-02-26T03:00:00Z",
            total_projects=1,
            project_counts_by_state=[{"lifecycle_state": "queued", "project_count": 1}],
            active_run_count=0,
            blocked_export_project_count=0,
            blocked_export_run_count=0,
            recent_failure_count=0,
            recent_failures=[],
        )
