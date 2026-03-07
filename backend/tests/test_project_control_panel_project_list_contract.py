import pytest
from pydantic import ValidationError

from app.schemas import ProjectControlPanelProjectListResponse


def test_unit_project_control_panel_project_list_contract_defaults() -> None:
    payload = ProjectControlPanelProjectListResponse(
        generated_at="2026-02-26T00:00:00Z",
        total_items=2,
        page=1,
        page_size=20,
        has_next_page=False,
        items=[
            {
                "project_id": 101,
                "status": "ingested",
                "selected_mode": "audiobook",
                "last_run_status": "completed",
                "updated_at": "2026-02-26T00:00:00Z",
                "next_required_action": "export",
            },
            {
                "project_id": 102,
                "status": "draft",
                "selected_mode": "audiobook",
                "last_run_status": None,
                "updated_at": "2026-02-26T00:05:00Z",
                "next_required_action": "ingest",
            },
        ],
    )

    assert payload.schema_version == "1.0.0"
    assert payload.output_schema == "project_control_panel_project_list_json"
    assert payload.output_format == "json"
    assert payload.output_id == "CP-002"
    assert payload.output_name == "project_control_panel_project_list"


def test_integration_project_control_panel_project_list_contract_accepts_minimal_payload() -> None:
    payload = ProjectControlPanelProjectListResponse.model_validate(
        {
            "generated_at": "2026-02-26T03:00:00Z",
            "generated_by": "dashboard_project_list_job",
            "total_items": 0,
            "page": 1,
            "page_size": 20,
            "has_next_page": False,
            "items": [],
        }
    )

    assert payload.generated_by == "dashboard_project_list_job"
    assert payload.total_items == 0
    assert payload.items == []


def test_regression_project_control_panel_project_list_rejects_unknown_next_required_action() -> None:
    with pytest.raises(ValidationError):
        ProjectControlPanelProjectListResponse(
            generated_at="2026-02-26T04:00:00Z",
            total_items=1,
            page=1,
            page_size=20,
            has_next_page=False,
            items=[
                {
                    "project_id": 222,
                    "status": "configured",
                    "selected_mode": "academic",
                    "last_run_status": "failed",
                    "updated_at": "2026-02-26T04:00:00Z",
                    "next_required_action": "launch",
                }
            ],
        )
