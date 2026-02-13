from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.modes import is_valid_mode
from app.models import Chapter, Character, CharacterVoiceMap, Project, Run
from app.schemas import ProjectSetupStatusResponse
from app.services.project_lifecycle import (
    PROJECT_LIFECYCLE_COMPLETED,
    PROJECT_LIFECYCLE_DRAFT,
    PROJECT_LIFECYCLE_FAILED,
    PROJECT_LIFECYCLE_RUNNING,
)
from app.services.run_status import (
    RUN_STATUS_CANCELLED,
    RUN_STATUS_COMPLETED,
    RUN_STATUS_FAILED,
    RUN_STATUS_QUEUED,
    RUN_STATUS_RUNNING,
)

_SETUP_LIFECYCLE_STATES = frozenset(
    {
        "draft",
        "ingested",
        "configured",
        "running",
        "completed",
        "failed",
        "archived",
    }
)
_SETUP_NEXT_REQUIRED_ACTION_VALUES = frozenset(
    {"ingest", "select_mode", "configure", "run", "rerun", "export", "review_failure", "archived", "none"}
)
_SETUP_INITIAL_RUN_STATUSES = frozenset(
    {RUN_STATUS_QUEUED, RUN_STATUS_RUNNING, RUN_STATUS_COMPLETED, RUN_STATUS_FAILED, RUN_STATUS_CANCELLED, "interrupted"}
)


def build_project_setup_status_response(
    *,
    session: Session,
    project: Project,
    next_required_action_resolver: Callable[..., str],
) -> ProjectSetupStatusResponse:
    normalized_lifecycle_state = str(project.lifecycle_state or PROJECT_LIFECYCLE_DRAFT).strip().lower()
    if normalized_lifecycle_state not in _SETUP_LIFECYCLE_STATES:
        normalized_lifecycle_state = PROJECT_LIFECYCLE_DRAFT

    normalized_last_run_status = (
        str(project.last_run_status).strip().lower()
        if project.last_run_status is not None
        else None
    )
    if normalized_last_run_status == "":
        normalized_last_run_status = None

    normalized_next_required_action = str(project.next_required_action or "").strip().lower()
    if normalized_next_required_action not in _SETUP_NEXT_REQUIRED_ACTION_VALUES:
        normalized_next_required_action = next_required_action_resolver(
            lifecycle_state=normalized_lifecycle_state,
            last_run_status=normalized_last_run_status,
        )

    normalized_selected_mode = str(project.selected_mode or "").strip().lower()
    chapter_count = session.query(Chapter.id).filter(Chapter.project_id == project.id).count()
    character_count = session.query(Character.id).filter(Character.project_id == project.id).count()
    voice_mapping_count = session.query(CharacterVoiceMap.id).filter(CharacterVoiceMap.project_id == project.id).count()
    has_run = session.query(Run.id).filter(Run.project_id == project.id).first() is not None

    ingestion_ready = project.ingestion_timestamp is not None or chapter_count > 0
    mode_selection_ready = is_valid_mode(normalized_selected_mode)
    initial_run_ready = (
        has_run
        or normalized_last_run_status in _SETUP_INITIAL_RUN_STATUSES
        or normalized_lifecycle_state
        in {
            PROJECT_LIFECYCLE_RUNNING,
            PROJECT_LIFECYCLE_COMPLETED,
            PROJECT_LIFECYCLE_FAILED,
        }
    )
    character_mapping_ready = bool(project.character_map_finalized or character_count > 0)
    voice_mapping_ready = voice_mapping_count > 0
    is_complete = all([ingestion_ready, mode_selection_ready, initial_run_ready])

    return ProjectSetupStatusResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        project_id=project.id,
        lifecycle_state=normalized_lifecycle_state,
        next_required_action=normalized_next_required_action,
        is_complete=is_complete,
        steps=[
            {
                "step_id": "ingestion",
                "label": "Ingestion",
                "ready": ingestion_ready,
                "required": True,
            },
            {
                "step_id": "mode_selection",
                "label": "Mode Selection",
                "ready": mode_selection_ready,
                "required": True,
            },
            {
                "step_id": "initial_run",
                "label": "Initial Run",
                "ready": initial_run_ready,
                "required": True,
            },
            {
                "step_id": "character_mapping",
                "label": "Character Mapping",
                "ready": character_mapping_ready,
                "required": False,
            },
            {
                "step_id": "voice_mapping",
                "label": "Voice Mapping",
                "ready": voice_mapping_ready,
                "required": False,
            },
        ],
    )
