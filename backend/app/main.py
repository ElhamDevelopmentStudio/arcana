from datetime import datetime, timedelta, timezone
from bisect import bisect_right
from collections.abc import Callable, Mapping
import hashlib
import io
import json
import re
from threading import Thread
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.exception_handlers import request_validation_exception_handler as fastapi_request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.chart_contracts import build_polarity_graph_contract, build_tension_graph_contract
from app.config import get_settings
from app.database import get_session, get_session_factory, init_db
from app.modes import DEFAULT_MODE, get_mode_catalog, is_valid_mode
from app.models import (
    Chapter,
    Character,
    CharacterProposal,
    CharacterExtractionJob,
    ProjectIngestionJob,
    ProjectIngestionJobFile,
    CharacterVoiceMap,
    ProjectAccess,
    CharacterMapSnapshot,
    ComparisonWorkspace,
    ComparisonWorkspaceRun,
    LLMCall,
    SubSegmentTag,
    RunChangelogEntry,
    Project,
    ProjectActivityEvent,
    ProjectLifecycleTransition,
    ProjectRawCorpusBlob,
    PronunciationDictionary,
    PronunciationDictionarySnapshot,
    RunConfigurationSnapshot,
    TimeSeriesSnapshot,
    VoiceMapSnapshot,
    Run,
    Segment,
    RunNormalizedCorpusBlob,
)
from app.schemas import (
    CharacterImportResponse,
    CharacterMapItem,
    CharacterMapResponse,
    CharacterMapUpdateRequest,
    CharacterMapFinalizeResponse,
    CharacterExtractionRequest,
    CharacterAliasLookupRequest,
    CharacterAliasLookupResponse,
    CharacterAliasCollisionItem,
    CharacterAliasCollisionResponse,
    PronunciationDictionaryItem,
    PronunciationDictionaryPreviewItem,
    PronunciationDictionaryPreviewRequest,
    PronunciationDictionaryPreviewResponse,
    PronunciationDictionaryResponse,
    PronunciationDictionaryUpdateRequest,
    IngestResponse,
    ProjectIngestionJobStartResponse,
    ProjectIngestionJobStatusResponse,
    CharacterExtractionResponse,
    CharacterExtractionJobStartResponse,
    CharacterExtractionJobStatusResponse,
    CharacterProposalItem,
    CharacterProposalListResponse,
    CharacterProposalReviewRequest,
    CharacterProposalReviewResponse,
    CharacterScrapeRequest,
    CharacterCandidatesMergeRequest,
    CharacterGenderComparisonItem,
    CharacterGenderComparisonResponse,
    ComparisonAlignedCurveMetricDescriptor,
    ComparisonAlignedCurvePoint,
    ComparisonAlignedCurveRunDescriptor,
    ComparisonWorkspaceCreateRequest,
    ComparisonWorkspaceAlignedCurvesResponse,
    ComparisonWorkspaceComparativeExportResponse,
    ComparisonWorkspaceComparativeRunDescriptor,
    ComparisonWorkspaceResponse,
    ComparisonWorkspaceRunDescriptor,
    ComparisonWorkspaceRunLinkRequest,
    ModeCatalogResponse,
    ProjectCreate,
    ProjectModeSwitchRequest,
    ProjectModeSwitchResponse,
    ProjectAccessGrantRequest,
    ProjectAccessGrantResponse,
    ProjectAccessListResponse,
    ALLOWED_PROJECT_ACCESS_PRINCIPAL_TYPES,
    ALLOWED_PROJECT_ACCESS_ROLES,
    ProjectResponse,
    ProjectIngestionSourceAttachRequest,
    ProjectIngestionSourceAttachResponse,
    ProjectMetadataUpdateRequest,
    ProjectMetadataUpdateResponse,
    ProjectAllowedActionsResponse,
    ProjectSetupStatusResponse,
    ProjectWorkspaceSummaryResponse,
    ProjectActivityTimelineResponse,
    ProjectDetailResponse,
    ProjectLifecycleStateChangeResponse,
    ProjectControlPanelProjectListResponse,
    ProjectControlPanelSummaryResponse,
    ProjectLLMSettingsRequest,
    ProjectLLMSettingsResponse,
    LLMProviderStatus,
    LLMProviderStatusUpdateRequest,
    LLMProvidersResponse,
    RunCreateRequest,
    CharacterOccurrenceAnalyticsResponse,
    CharacterCooccurrenceGraphResponse,
    AudiobookPrepDashboardResponse,
    PipelineStageDurationsDashboardResponse,
    TensionGraphContractResponse,
    PolarityGraphResponse,
    RunDetailResponse,
    RunConfigDiffResponse,
    RunConfigPresetResponse,
    RunResponse,
    VoiceConfigRequest,
    VoiceConfigResponse,
)
from app.services.characters import parse_character_file
from app.services.character_extraction import CandidateEvidence, extract_character_candidates_from_texts
from app.services.character_scrape import extract_character_candidates_from_scrape_url
from app.services.epub_ingestion import extract_epub_chapters
from app.services.character_merge import build_canonical_name_merge_suggestions, merge_character_candidates
from app.services.character_merge import build_ambiguous_alias_collision_warnings
from app.services.character_merge import build_duplicate_canonical_candidate_warnings
from app.services.character_merge import build_low_confidence_extracted_character_warnings
from app.services.character_merge import normalize_candidate_key
from app.services.character_merge import detect_alias_conflicts
from app.services.character_merge import resolve_alias_to_canonical_name
from app.services.export import (
    _build_rolling_emotional_curves,
    build_run_export,
    build_run_export_csv,
)
from app.services.export import build_run_export_graph_json
from app.services.export import build_run_export_academic_csv
from app.services.export import resolve_run_allowed_export_formats
from app.services.ingestion_errors import (
    IngestionInProgressError,
    MissingChaptersIngestionError,
    UnsupportedEncodingIngestionError,
    UnsupportedFormatIngestionError,
)
from app.services.ingestion import (
    build_duplicate_title_dedup_actions,
    build_duplicate_title_warnings,
    build_encoding_warning,
    build_suspected_duplicate_content_warnings,
    build_internal_chapter_id,
    calculate_delta_affected_range,
    chapter_filename_sort_key,
    chapter_title_from_filename,
    contains_explicit_chapter_header,
    decode_text,
    decode_text_with_metadata,
    detect_append_overlap_or_duplicate,
    detect_chapters,
    detect_chapters_with_metadata,
    detect_chapters_from_file_boundaries,
    detect_suspected_duplicate_content,
    build_ambiguous_chapter_boundary_warning,
    detect_title_with_fallback,
    detect_text_encoding,
    extract_single_append_chapter,
    is_likely_unsupported_encoding,
    normalize_markdown_for_ingestion,
    to_internal_utf8,
)
from app.services.mode_profiles import (
    PROFILE_CONFIG_KEYS,
    RUN_CONFIG_SCHEMA_VERSION,
    build_run_config_snapshot,
    load_mode_profile,
)
from app.services.llm_router import (
    LLMProviderConfig,
    LLMRequest,
    LLMRouter,
    get_provider_api_keys,
    get_provider_priority_order,
    get_provider_runtime_settings,
)
from app.services.mode_switch import mark_runs_stale_for_gender_edit, mark_runs_stale_for_mode_switch
from app.services.character_analytics import build_character_occurrence_analytics
from app.services.gender_comparison import compare_manual_and_inferred_gender_fields
from app.services.gender_comparison import build_manual_inferred_gender_contradiction_warnings
from app.services.gender_comparison import build_insufficient_inference_evidence_warnings
from app.services.gender_inference import infer_character_genders
from app.services.normalization import (
    build_original_to_normalized_offset_map,
    build_normalization_report,
    normalize_text_with_report,
)
from app.services.voice_preview import recompute_voice_previews_for_runs
from app.services.background_jobs import submit_background_job
from app.services.pipeline import PipelineError, execute_pipeline
from app.services.llm_router import is_supported_provider
from app.services.run_status import (
    RUN_STATUS_CANCELLED,
    RUN_STATUS_COMPLETED,
    RUN_STATUS_FAILED,
    RUN_STATUS_QUEUED,
    RUN_STATUS_RUNNING,
)
from app.services.project_lifecycle import (
    PROJECT_LIFECYCLE_ARCHIVED,
    PROJECT_LIFECYCLE_COMPLETED,
    PROJECT_LIFECYCLE_CONFIGURED,
    PROJECT_LIFECYCLE_DRAFT,
    PROJECT_LIFECYCLE_FAILED,
    PROJECT_LIFECYCLE_INGESTED,
    PROJECT_LIFECYCLE_RUNNING,
    transition_project_lifecycle_state,
)
from app.services.provider_toggle import (
    get_provider_statuses,
    is_provider_enabled,
    set_provider_enabled,
)
from app.services.project_setup_status import build_project_setup_status_response
from app.services.voice import DEFAULT_VOICE_CONFIG, _normalize_internal_thought_voice_policy
from app.services.phonetics import replace_pronunciations_with_counts
from app.celery_app import celery_app, is_celery_available

LOW_CONFIDENCE_STATE_VALUES = {"uncertain", "unknown"}
LOW_CONFIDENCE_REGION_THRESHOLD = 0.8
CHARACTER_EXTRACTION_LOW_CONFIDENCE_THRESHOLD = 0.7
CHARACTER_EXTRACTION_DEFAULT_MIN_CONFIDENCE = 0.4
CHARACTER_EXTRACTION_EXTRACTOR_VERSION = "v2"
CHARACTER_EXTRACTION_LLM_DEFAULT_CHUNK_MAX_CHARS = 5600
CHARACTER_EXTRACTION_LLM_DEFAULT_MAX_CHUNKS = 120
CHARACTER_EXTRACTION_LLM_DEFAULT_VERIFICATION_BATCH_SIZE = 24
CHARACTER_EXTRACTION_LLM_TRACE_LIMIT = 8
CHARACTER_EXTRACTION_LLM_MIN_VALID_NAME_LENGTH = 2
CHARACTER_EXTRACTION_LLM_MAX_VALID_NAME_LENGTH = 80
CHARACTER_EXTRACTION_LLM_MIN_EXCERPT_LENGTH = 8
CHARACTER_EXTRACTION_JOB_STATUS_QUEUED = "queued"
CHARACTER_EXTRACTION_JOB_STATUS_RUNNING = "running"
CHARACTER_EXTRACTION_JOB_STATUS_COMPLETED = "completed"
CHARACTER_EXTRACTION_JOB_STATUS_FAILED = "failed"
PROJECT_INGESTION_ALLOWED_SOURCES = {"txt", "markdown", "epub", "chapters-dir", "append-chapter"}
PROJECT_INGESTION_JOB_STATUS_QUEUED = "queued"
PROJECT_INGESTION_JOB_STATUS_RUNNING = "running"
PROJECT_INGESTION_JOB_STATUS_COMPLETED = "completed"
PROJECT_INGESTION_JOB_STATUS_FAILED = "failed"
_RUN_RECOVERY_STALE_WINDOW_SECONDS = 600
_PIPELINE_RECOVERY_CONFIG_KEY = "pipeline_recovery"
_CORRELATION_ID_HEADER = "X-Correlation-Id"
_PROJECT_ACCESS_ROLE_HIERARCHY = {"viewer": 1, "editor": 2, "owner": 3}
_PROJECT_ACCESS_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_PROJECT_ACCESS_HEADER_TYPE = "x-principal-type"
_PROJECT_ACCESS_HEADER_ID = "x-principal-id"

_PROJECT_ACCESS_SCOPE_READ = "read"
_PROJECT_ACCESS_SCOPE_RUN_EXEC = "run_execute"
_PROJECT_ACCESS_SCOPE_WRITE = "project_write"
_CONTROL_PANEL_RECENT_FAILURE_LIMIT = 20
_CONTROL_PANEL_STATE_ORDER = (
    PROJECT_LIFECYCLE_DRAFT,
    PROJECT_LIFECYCLE_INGESTED,
    PROJECT_LIFECYCLE_CONFIGURED,
    PROJECT_LIFECYCLE_RUNNING,
    PROJECT_LIFECYCLE_COMPLETED,
    PROJECT_LIFECYCLE_FAILED,
    PROJECT_LIFECYCLE_ARCHIVED,
)
_CONTROL_PANEL_NEXT_REQUIRED_ACTION_VALUES = frozenset(
    {"ingest", "select_mode", "configure", "run", "rerun", "export", "review_failure", "archived", "none"}
)
_PROJECT_ALLOWED_ACTION_ORDER = (
    "ingest",
    "select_mode",
    "configure",
    "run",
    "rerun",
    "export",
    "archive",
    "restore",
)
_PROJECT_ACTIVITY_EVENT_TYPES = frozenset(
    {"ingest", "mode_change", "run_start", "run_complete", "export", "manual_edit", "rerun"}
)
_PROJECT_ARCHIVE_METADATA_KEY = "control_panel_archive"

_PROJECT_SERVICE_ROLE_SCOPE_MATRIX: dict[str, dict[str, set[str]]] = {
    "service": {
        "viewer": {_PROJECT_ACCESS_SCOPE_READ},
        "editor": {_PROJECT_ACCESS_SCOPE_READ, _PROJECT_ACCESS_SCOPE_RUN_EXEC},
        "owner": {_PROJECT_ACCESS_SCOPE_READ, _PROJECT_ACCESS_SCOPE_RUN_EXEC},
    },
    "system": {
        "viewer": {_PROJECT_ACCESS_SCOPE_READ},
        "editor": {_PROJECT_ACCESS_SCOPE_READ},
        "owner": {_PROJECT_ACCESS_SCOPE_READ},
    },
}

app = FastAPI(title="NIPE PoC API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()
    session = get_session_factory()()
    try:
        _backfill_project_lifecycle_and_activity_records(session=session)
        session.commit()
    finally:
        session.close()


def _extract_project_id_from_path(path: str) -> int | None:
    parts = [segment for segment in path.split("/") if segment]
    if len(parts) >= 3 and parts[0] == "api" and parts[1] == "projects" and parts[2].isdigit():
        return int(parts[2])
    return None


def _resolve_project_access_headers(request: Request) -> tuple[str | None, str | None] | None:
    principal_type_header = request.headers.get(_PROJECT_ACCESS_HEADER_TYPE)
    principal_id_header = request.headers.get(_PROJECT_ACCESS_HEADER_ID)

    if principal_type_header is None and principal_id_header is None:
        return None

    if principal_type_header is None or principal_id_header is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both X-Principal-Type and X-Principal-Id headers are required.",
        )

    principal_type = str(principal_type_header).strip().lower()
    principal_id = str(principal_id_header).strip()
    if not principal_type or principal_type not in ALLOWED_PROJECT_ACCESS_PRINCIPAL_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported principal_type header value.",
        )
    if not principal_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Principal-Id header must not be blank.",
        )

    return principal_type, principal_id


def _resolve_request_correlation_id(request: Request) -> str:
    correlation_id_header = request.headers.get(_CORRELATION_ID_HEADER)
    if correlation_id_header is not None:
        correlation_id = str(correlation_id_header).strip()
        if correlation_id:
            return correlation_id
    return str(uuid4())


def _resolve_correlation_id_from_run_config(run_config: Mapping[str, object] | None) -> str | None:
    if not isinstance(run_config, Mapping):
        return None
    raw_correlation_id = run_config.get("correlation_id")
    if not isinstance(raw_correlation_id, str):
        return None
    correlation_id = raw_correlation_id.strip()
    return correlation_id or None


def _build_export_correlation_headers(run_config: Mapping[str, object] | None) -> dict[str, str]:
    correlation_id = _resolve_correlation_id_from_run_config(run_config)
    if not correlation_id:
        return {}
    return {_CORRELATION_ID_HEADER: correlation_id}


def _required_project_role_for_scope(access_scope: str) -> str:
    return "viewer" if access_scope == _PROJECT_ACCESS_SCOPE_READ else "editor"


def _normalize_project_route_suffix(path: str) -> str:
    segments = [segment for segment in path.strip("/").split("/") if segment]
    if len(segments) < 3 or segments[0] != "api" or segments[1] != "projects":
        return ""
    # segments[2] is project_id
    return "/".join(segments[3:]).lower()


def _required_project_access_scope(method: str, path: str) -> str:
    method_upper = method.upper()
    if method_upper in {"GET", "HEAD", "OPTIONS"}:
        return _PROJECT_ACCESS_SCOPE_READ

    if method_upper not in _PROJECT_ACCESS_WRITE_METHODS:
        return _PROJECT_ACCESS_SCOPE_READ

    suffix = _normalize_project_route_suffix(path)
    parts = [part for part in suffix.split("/") if part]

    if method_upper == "POST" and len(parts) == 3 and parts[0] == "runs" and parts[2] in {"recover", "cancel"}:
        return _PROJECT_ACCESS_SCOPE_RUN_EXEC

    if method_upper == "POST" and parts == ["runs"]:
        return _PROJECT_ACCESS_SCOPE_RUN_EXEC

    return _PROJECT_ACCESS_SCOPE_WRITE


def _sanitize_provider_config_for_frontend(provider_config: object) -> dict[str, dict[str, object]]:
    if not isinstance(provider_config, dict):
        return {}

    sanitized: dict[str, dict[str, object]] = {}
    for provider_name, config in provider_config.items():
        if not isinstance(config, dict):
            continue

        normalized_provider_name = str(provider_name).strip().lower()
        if not normalized_provider_name:
            continue

        sanitized_config: dict[str, object] = {}
        for key, value in config.items():
            if not isinstance(key, str):
                continue
            normalized_key = key.strip().lower()
            if normalized_key in {"api_key", "api_keys"}:
                continue
            sanitized_config[key] = value

        sanitized[normalized_provider_name] = sanitized_config

    return sanitized


def _sanitize_run_config_for_frontend(run_config: object) -> dict[str, object]:
    if not isinstance(run_config, dict):
        return {}

    sanitized = dict(run_config)

    raw_provider_config = run_config.get("provider_config")
    if raw_provider_config is not None:
        sanitized["provider_config"] = _sanitize_provider_config_for_frontend(raw_provider_config)

    if "provider_api_keys" in sanitized:
        sanitized.pop("provider_api_keys")

    return sanitized


def _build_field_level_validation_errors(exc: RequestValidationError) -> list[dict[str, str]]:
    field_errors: list[dict[str, str]] = []
    for issue in exc.errors():
        location = issue.get("loc", ())
        if not isinstance(location, (tuple, list)):
            continue

        normalized_location = [str(part).strip() for part in location if str(part).strip()]
        if normalized_location and normalized_location[0] in {"body", "query"}:
            normalized_location = normalized_location[1:]
        field_name = ".".join(normalized_location) if normalized_location else "request"
        message = str(issue.get("msg", "Invalid value")).strip() or "Invalid value"
        code = str(issue.get("type", "value_error")).strip() or "value_error"
        field_errors.append(
            {
                "field": field_name,
                "message": message,
                "code": code,
            }
        )

    return field_errors


_RUN_CONFIG_DIFF_EXCLUDED_FIELDS: frozenset[str] = frozenset(
    {
        "idempotency_key",
        "idempotency_signature",
        "configuration_snapshot_id",
        "configuration_snapshot_version",
        "character_map_snapshot_id",
        "character_map_snapshot_version",
        "pronunciation_dictionary_snapshot_id",
        "pronunciation_dictionary_snapshot_version",
        "voice_map_snapshot_id",
        "voice_map_snapshot_version",
        "time_series_snapshot_id",
        "time_series_snapshot_version",
        "pipeline_recovery",
    }
)

_RUN_CONFIG_PRESET_FIELDS: tuple[str, ...] = (
    "mode",
    "max_segment_chars",
    "llm_enabled",
    "provider_name",
    "export_formats",
    "export_chunk_size",
    "deep_semantic_refinement",
    "deterministic_mode",
    "contradiction_review_required",
    "max_calls_per_day",
    "llm_confidence_threshold",
    "speaker_confidence_threshold",
    "high_ambiguity_dialogue_flag_threshold",
    "unstable_emotion_shift_transition_threshold",
    "unstable_emotion_shift_density_threshold",
    "deterministic_model_identifier",
    "web_scraping_enabled",
    "deterministic_seed",
    "randomization_config",
    "emotion_taxonomy",
    "allow_unfinalized_character_map",
    "internal_thought_voice_policy",
    "internal_thought_voice",
    "incremental_recompute",
    "pipeline_chunk_max_chars",
)


def _prepare_run_config_for_diff(run_config: object) -> dict[str, object]:
    prepared = _sanitize_run_config_for_frontend(run_config)
    for field_name in _RUN_CONFIG_DIFF_EXCLUDED_FIELDS:
        prepared.pop(field_name, None)
    return prepared


def _build_run_config_diff(
    *,
    base_run_config: object,
    target_run_config: object,
) -> dict[str, object]:
    base_config = _prepare_run_config_for_diff(base_run_config)
    target_config = _prepare_run_config_for_diff(target_run_config)
    base_keys = set(base_config.keys())
    target_keys = set(target_config.keys())

    changed_fields: list[dict[str, object | None]] = []
    for key in sorted(base_keys & target_keys):
        if base_config.get(key) != target_config.get(key):
            changed_fields.append(
                {
                    "field": key,
                    "base_value": base_config.get(key),
                    "target_value": target_config.get(key),
                }
            )

    return {
        "base_config_schema_version": str(base_config.get("config_schema_version", RUN_CONFIG_SCHEMA_VERSION)),
        "target_config_schema_version": str(target_config.get("config_schema_version", RUN_CONFIG_SCHEMA_VERSION)),
        "is_identical": (
            len(changed_fields) == 0
            and len(base_keys - target_keys) == 0
            and len(target_keys - base_keys) == 0
        ),
        "changed_fields": changed_fields,
        "base_only_fields": sorted(base_keys - target_keys),
        "target_only_fields": sorted(target_keys - base_keys),
    }


def _build_run_config_preset(run_config: object) -> dict[str, object]:
    sanitized_run_config = _sanitize_run_config_for_frontend(run_config)
    preset: dict[str, object] = {}
    for field_name in _RUN_CONFIG_PRESET_FIELDS:
        if field_name in sanitized_run_config and sanitized_run_config[field_name] is not None:
            preset[field_name] = sanitized_run_config[field_name]
    return preset


def _has_required_project_access(
    *,
    session: Session,
    project_id: int,
    principal_type: str,
    principal_id: str,
    required_role: str,
    access_scope: str,
) -> None:
    project = session.query(Project).filter(Project.id == project_id).one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    grant = (
        session.query(ProjectAccess)
        .filter(
            ProjectAccess.project_id == project_id,
            ProjectAccess.principal_type == principal_type,
            ProjectAccess.principal_id == principal_id,
            ProjectAccess.role.in_(ALLOWED_PROJECT_ACCESS_ROLES),
        )
        .one_or_none()
    )
    if grant is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project access denied.")

    if principal_type != "user":
        allowed_scopes_by_role = _PROJECT_SERVICE_ROLE_SCOPE_MATRIX.get(principal_type)
        if allowed_scopes_by_role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Project role is insufficient for this operation.",
            )

        allowed_scopes = allowed_scopes_by_role.get(grant.role)
        if allowed_scopes is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Project role is insufficient for this operation.",
            )

        if access_scope not in allowed_scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Project role is insufficient for this operation.",
            )
        return

    if _PROJECT_ACCESS_ROLE_HIERARCHY.get(grant.role, 0) < _PROJECT_ACCESS_ROLE_HIERARCHY.get(required_role, 0):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Project role is insufficient for this operation.",
        )


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(request: Request, exc: RequestValidationError):
    request_path = request.url.path.strip().lower()
    if request.method.upper() == "POST" and request_path.startswith("/api/projects/") and request_path.endswith("/runs"):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "Run configuration validation failed.",
                "field_errors": _build_field_level_validation_errors(exc),
            },
        )
    return await fastapi_request_validation_exception_handler(request, exc)


@app.middleware("http")
async def enforce_project_data_isolation(request: Request, call_next):
    project_id = _extract_project_id_from_path(request.url.path)
    if project_id is None:
        return await call_next(request)

    try:
        project_principal = _resolve_project_access_headers(request)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    if project_principal is None:
        return await call_next(request)

    principal_type, principal_id = project_principal
    required_scope = _required_project_access_scope(request.method, request.url.path)
    required_role = _required_project_role_for_scope(required_scope)

    session = get_session_factory()()
    try:
        try:
            _has_required_project_access(
                session=session,
                project_id=project_id,
                principal_type=principal_type,
                principal_id=principal_id,
                required_role=required_role,
                access_scope=required_scope,
            )
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    finally:
        session.close()

    return await call_next(request)


def _serialize_datetime_to_utc_iso(value: datetime | None) -> str | None:
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).isoformat()
    return value.astimezone(timezone.utc).isoformat()


def _append_run_changelog_entry(
    *,
    session: Session,
    run: Run,
    event_type: str,
    event_message: str | None = None,
    event_metadata: dict[str, object] | None = None,
) -> None:
    session.add(
        RunChangelogEntry(
            run_id=run.id,
            event_type=event_type.strip() or "unknown_event",
            event_message=event_message,
            event_metadata=dict(event_metadata or {}),
        )
    )


def _coerce_float(value: object | None, *, fallback: float | None = None) -> float | None:
    if value is None:
        return fallback
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _is_low_confidence_state(value: object) -> bool:
    return isinstance(value, str) and value.strip().lower() in LOW_CONFIDENCE_STATE_VALUES


def _as_dict(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, Mapping) else {}


def _is_low_confidence_region(segment: dict[str, object]) -> bool:
    tag_states = _as_dict(segment.get("tag_states"))
    states_to_check = [
        tag_states.get("type"),
        tag_states.get("speaker"),
        tag_states.get("emotion"),
        tag_states.get("tension"),
        tag_states.get("dominance"),
        tag_states.get("summary"),
        segment.get("speaker_state"),
        segment.get("emotion_state"),
    ]
    if any(_is_low_confidence_state(state) for state in states_to_check):
        return True

    confidence = _as_dict(segment.get("confidence"))
    tension_contribution = _as_dict(segment.get("tension_contribution"))
    dominance_contribution = _as_dict(segment.get("dominance_contribution"))
    summary_tag = _as_dict(segment.get("summary_tag"))

    for confidence_value in [
        confidence.get("speaker"),
        confidence.get("emotion"),
        confidence.get("type"),
        confidence.get("tension"),
        confidence.get("dominance"),
        tension_contribution.get("confidence"),
        dominance_contribution.get("confidence"),
        summary_tag.get("confidence"),
    ]:
        confidence_numeric = _coerce_float(confidence_value)
        if confidence_numeric is not None and confidence_numeric < LOW_CONFIDENCE_REGION_THRESHOLD:
            return True

    return False


def _hash_text(value: str | None) -> str:
    if value is None:
        return ""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _build_snapshot_json_checksum(payload: object) -> str:
    if not isinstance(payload, dict):
        return _hash_text(None)
    return _hash_text(_canonical_json(payload))


def _build_idempotent_state_signature_payload(
    *,
    session: Session,
    project: Project,
    run_config: dict[str, object],
) -> dict[str, object]:
    chapter_rows = (
        session.query(Chapter)
        .filter(Chapter.project_id == project.id)
        .order_by(Chapter.chapter_index.asc(), Chapter.id.asc())
        .all()
    )
    chapters = [
        {
            "chapter_index": row.chapter_index,
            "chapter_internal_id": row.chapter_internal_id,
            "chapter_title": row.chapter_title,
            "raw_text_hash": _hash_text(row.raw_text),
            "normalized_text_hash": _hash_text(row.normalized_text),
            "raw_text_len": len(row.raw_text),
            "normalized_text_len": len(row.normalized_text),
        }
        for row in chapter_rows
    ]

    character_rows = (
        session.query(Character)
        .filter(Character.project_id == project.id)
        .order_by(Character.name.asc(), Character.id.asc())
        .all()
    )
    characters = [
        {
            "name": row.name,
            "verbalized_form": row.verbalized_form,
            "gender": row.gender,
            "aliases": sorted({alias.strip() for alias in (row.aliases or []) if str(alias).strip()}),
            "source": row.source,
            "voice_id": row.voice_id or None,
            "inferred_gender": row.inferred_gender,
            "inferred_confidence": row.inferred_confidence,
        }
        for row in character_rows
    ]

    voice_map_rows = (
        session.query(CharacterVoiceMap)
        .filter(CharacterVoiceMap.project_id == project.id)
        .order_by(CharacterVoiceMap.character_id.asc(), CharacterVoiceMap.id.asc())
        .all()
    )
    character_voice_map = [
        {
            "character_id": row.character_id,
            "voice_id": row.voice_id,
        }
        for row in voice_map_rows
    ]

    pronunciation_rows = (
        session.query(PronunciationDictionary)
        .filter(PronunciationDictionary.project_id == project.id)
        .order_by(
            PronunciationDictionary.scope.asc(),
            PronunciationDictionary.character_name.asc(),
            PronunciationDictionary.term.asc(),
            PronunciationDictionary.id.asc(),
        )
        .all()
    )
    pronunciation_dictionary = [
        {
            "scope": row.scope,
            "character_name": row.character_name,
            "term": row.term,
            "verbalized_form": row.verbalized_form,
            "source": row.source,
            "confidence": row.confidence,
        }
        for row in pronunciation_rows
    ]

    run_config_signature = dict(run_config)
    run_config_signature.pop("idempotency_key", None)
    run_config_signature.pop("idempotency_signature", None)
    run_config_signature.pop("configuration_snapshot_id", None)
    run_config_signature.pop("configuration_snapshot_version", None)
    run_config_signature.pop("character_map_snapshot_id", None)
    run_config_signature.pop("character_map_snapshot_version", None)
    run_config_signature.pop("pronunciation_dictionary_snapshot_id", None)
    run_config_signature.pop("pronunciation_dictionary_snapshot_version", None)
    run_config_signature.pop("voice_map_snapshot_id", None)
    run_config_signature.pop("voice_map_snapshot_version", None)
    run_config_signature.pop("time_series_snapshot_id", None)
    run_config_signature.pop("time_series_snapshot_version", None)
    run_config_signature.pop("pipeline_recovery", None)

    return {
        "run_config": run_config_signature,
        "project": {
            "selected_mode": project.selected_mode,
            "selected_modes": sorted(project.selected_modes or []),
            "llm_enabled": project.llm_enabled,
            "llm_provider_config_json": dict(project.llm_provider_config_json or {}),
            "voice_config_json": dict(project.voice_config_json or {}),
            "character_map_finalized": project.character_map_finalized,
            "ingestion_timestamp": _serialize_datetime_to_utc_iso(project.ingestion_timestamp),
            "ingestion_log_hash": _hash_text(_canonical_json(project.ingestion_log_json or {})),
        },
        "chapters": chapters,
        "characters": characters,
        "character_voice_map": character_voice_map,
        "pronunciation_dictionary": pronunciation_dictionary,
    }


def _build_idempotent_rerun_signature(
    *,
    session: Session,
    project: Project,
    run_config: dict[str, object],
) -> str:
    payload = _build_idempotent_state_signature_payload(
        session=session,
        project=project,
        run_config=run_config,
    )
    return _hash_text(_canonical_json(payload))


def _find_matching_idempotent_run(
    *,
    session: Session,
    project_id: int,
    idempotency_key: str,
    idempotency_signature: str,
) -> Run | None:
    candidate_runs = (
        session.query(Run)
        .filter(Run.project_id == project_id)
        .order_by(Run.id.desc())
        .all()
    )
    for run in candidate_runs:
        run_config = run.config_json
        if not isinstance(run_config, dict):
            continue
        if run_config.get("idempotency_key") != idempotency_key:
            continue
        if run_config.get("idempotency_signature") != idempotency_signature:
            continue
        if run.status == RUN_STATUS_FAILED:
            continue
        return run
    return None


def _build_run_response_from_existing(session: Session, run: Run) -> RunResponse:
    segment_count = session.query(Segment).filter(Segment.run_id == run.id).count()
    return RunResponse(
        run_id=run.id,
        project_id=run.project_id,
        status=run.status,
        segment_count=segment_count,
    )


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/modes", response_model=ModeCatalogResponse, status_code=status.HTTP_200_OK)
def get_modes() -> ModeCatalogResponse:
    return ModeCatalogResponse(**get_mode_catalog())


def _get_project_or_404(session: Session, project_id: int) -> Project:
    project = session.query(Project).filter(Project.id == project_id).one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _get_run_or_404(session: Session, project_id: int, run_id: int) -> Run:
    run = (
        session.query(Run)
        .filter(Run.id == run_id, Run.project_id == project_id)
        .one_or_none()
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


def _get_comparison_workspace_or_404(session: Session, workspace_id: int) -> ComparisonWorkspace:
    workspace = session.query(ComparisonWorkspace).filter(ComparisonWorkspace.id == workspace_id).one_or_none()
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comparison workspace not found")
    return workspace


def _build_comparison_workspace_response(
    session: Session,
    workspace: ComparisonWorkspace,
) -> ComparisonWorkspaceResponse:
    links = (
        session.query(ComparisonWorkspaceRun)
        .filter(ComparisonWorkspaceRun.workspace_id == workspace.id)
        .order_by(ComparisonWorkspaceRun.created_at.asc(), ComparisonWorkspaceRun.id.asc())
        .all()
    )

    runs: list[ComparisonWorkspaceRunDescriptor] = []
    for link in links:
        run = session.query(Run).filter(Run.id == link.run_id).one_or_none()
        if run is None:
            continue

        segment_count = session.query(Segment).filter(Segment.run_id == run.id).count()
        config = dict(run.config_json or {})
        runs.append(
            ComparisonWorkspaceRunDescriptor(
                run_id=run.id,
                project_id=link.project_id,
                project_title=link.project.title if link.project else "",
                status=run.status,
                segment_count=segment_count,
                run_config_mode=str(config.get("mode", DEFAULT_MODE)),
            )
        )

    return ComparisonWorkspaceResponse(
        workspace_id=workspace.id,
        name=workspace.name,
        description=workspace.description,
        created_at=workspace.created_at,
        run_count=len(runs),
        runs=runs,
    )


_ALIGNED_CURVE_DEFINITIONS = {
    "chapter_valence_mean": {
        "label": "Chapter valence mean",
        "source_path": ["chapter_level_valence_means"],
        "value_key": "valence_mean",
        "position_key": "chapter_id",
    },
    "chapter_valence_variance": {
        "label": "Chapter valence variance",
        "source_path": ["chapter_level_valence_variance"],
        "value_key": "valence_variance",
        "position_key": "chapter_id",
    },
    "chapter_emotional_volatility": {
        "label": "Chapter emotional volatility",
        "source_path": ["chapter_level_emotional_volatility_index"],
        "value_key": "emotional_volatility_index",
        "position_key": "chapter_id",
    },
    "smoothed_tension_curve": {
        "label": "Smoothed tension curve",
        "source_path": ["smoothed_tension_curve", "tension_curve"],
        "value_key": "smoothed_tension",
        "position_key": "position",
    },
    "rolling_valence_curve": {
        "label": "Rolling valence mean",
        "source_path": ["rolling_window_emotional_curves", "valence_curve"],
        "value_key": "rolling_mean_valence",
        "position_key": "position",
    },
    "rolling_intensity_curve": {
        "label": "Rolling intensity mean",
        "source_path": ["rolling_window_emotional_curves", "intensity_curve"],
        "value_key": "rolling_mean_intensity",
        "position_key": "position",
    },
    "normalized_pacing_signature": {
        "label": "Normalized pacing signature",
        "source_path": ["normalized_pacing_signature"],
        "value_key": "signature_value",
        "position_key": "position",
    },
}


def _coerce_float(value: object) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    return None


def _extract_nested_value(payload: dict[str, object], path: list[str]) -> object:
    current: object = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _extract_curve_points(
    academic_reports: dict[str, object],
    source_path: list[str],
    value_key: str,
    position_key: str,
) -> list[tuple[float, float]]:
    raw_points = _extract_nested_value(academic_reports, source_path)
    if not isinstance(raw_points, list):
        return []

    values: list[tuple[float, float]] = []
    for index, raw_point in enumerate(raw_points):
        if not isinstance(raw_point, dict):
            continue
        value = _coerce_float(raw_point.get(value_key))
        if value is None:
            continue
        position = raw_point.get(position_key)
        normalized_position = _coerce_float(position)
        if normalized_position is None:
            normalized_position = float(index + 1)
        values.append((normalized_position, value))
    return sorted(values, key=lambda point: point[0])


def _align_curve_points(points: list[tuple[float, float]], align_count: int) -> list[ComparisonAlignedCurvePoint]:
    if align_count < 2:
        align_count = 2
    if not points:
        return []

    if len(points) == 1:
        return [
            ComparisonAlignedCurvePoint(
                normalized_position=round(index / (align_count - 1), 6),
                value=round(points[0][1], 6),
                source_position=int(points[0][0]),
            )
            for index in range(align_count)
        ]

    min_position = points[0][0]
    max_position = points[-1][0]
    if min_position == max_position:
        return [
            ComparisonAlignedCurvePoint(
                normalized_position=round(index / (align_count - 1), 6),
                value=round(points[0][1], 6),
                source_position=int(points[0][0]),
            )
            for index in range(align_count)
        ]

    positions = [point_position for point_position, _ in points]
    values = [value for _, value in points]
    aligned_points: list[ComparisonAlignedCurvePoint] = []
    for index in range(align_count):
        normalized_position = index / (align_count - 1)
        target_position = min_position + ((max_position - min_position) * normalized_position)
        right_index = bisect_right(positions, target_position)
        left_index = max(0, right_index - 1)
        right_index = min(right_index, len(points) - 1)
        left_position = positions[left_index]
        left_value = values[left_index]
        if right_index == left_index:
            value = left_value
            source_position = left_position
        else:
            right_position = positions[right_index]
            right_value = values[right_index]
            if right_position == left_position:
                ratio = 0.0
            else:
                ratio = (target_position - left_position) / (right_position - left_position)
            value = left_value + ((right_value - left_value) * ratio)
            source_position = target_position

        aligned_points.append(
            ComparisonAlignedCurvePoint(
                normalized_position=round(normalized_position, 6),
                value=round(float(value), 6),
                source_position=int(round(source_position)),
            )
        )

    return aligned_points


def _resolve_aligned_curve_metric_ids(metrics: str | None) -> list[str]:
    requested = [value.strip() for value in (metrics or "").split(",") if value.strip()]
    available_metric_ids = set(_ALIGNED_CURVE_DEFINITIONS.keys())
    if requested:
        unknown_metrics = [metric_id for metric_id in requested if metric_id not in available_metric_ids]
        if unknown_metrics:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unsupported metric filter(s): {', '.join(sorted(unknown_metrics))}",
            )
        return requested
    return sorted(available_metric_ids)


def _load_workspace_runs_for_comparison(
    session: Session,
    workspace: ComparisonWorkspace,
) -> list[tuple[ComparisonWorkspaceRun, Project, Run]]:
    return (
        session.query(ComparisonWorkspaceRun, Project, Run)
        .join(Project, ComparisonWorkspaceRun.project_id == Project.id)
        .join(Run, ComparisonWorkspaceRun.run_id == Run.id)
        .filter(ComparisonWorkspaceRun.workspace_id == workspace.id)
        .order_by(ComparisonWorkspaceRun.created_at.asc(), ComparisonWorkspaceRun.id.asc())
        .all()
    )


def _build_workspace_aligned_curve_payloads(
    session: Session,
    workspace_runs: list[tuple[ComparisonWorkspaceRun, Project, Run]],
    selected_metric_ids: list[str],
    aligned_points: int,
) -> list[ComparisonAlignedCurveMetricDescriptor]:
    metric_series_by_id = {
        metric_id: []
        for metric_id in selected_metric_ids
    }

    for _, project_row, run in workspace_runs:
        if run is None or project_row is None:
            continue
        export_payload = build_run_export(session=session, project=project_row, run=run)
        manifest = export_payload.get("manifest", {})
        academic_reports = manifest.get("academic_reports", {})
        if not isinstance(academic_reports, dict):
            academic_reports = {}

        for metric_id in selected_metric_ids:
            definition = _ALIGNED_CURVE_DEFINITIONS[metric_id]
            points = _extract_curve_points(
                academic_reports=academic_reports,
                source_path=definition["source_path"],
                value_key=definition["value_key"],
                position_key=definition["position_key"],
            )
            aligned_points_for_run = _align_curve_points(points=points, align_count=aligned_points)
            metric_series_by_id[metric_id].append(
                ComparisonAlignedCurveRunDescriptor(
                    run_id=run.id,
                    project_id=project_row.id,
                    project_title=project_row.title,
                    status=run.status,
                    points=aligned_points_for_run,
                )
            )

    metric_payloads: list[ComparisonAlignedCurveMetricDescriptor] = []
    for metric_id in selected_metric_ids:
        definition = _ALIGNED_CURVE_DEFINITIONS[metric_id]
        metric_payloads.append(
            ComparisonAlignedCurveMetricDescriptor(
                metric_id=metric_id,
                metric_label=definition["label"],
                value_key=definition["value_key"],
                source_path=definition["source_path"],
                points_per_run=metric_series_by_id[metric_id],
            )
        )
    return metric_payloads


def _build_comparison_run_export_records(
    session: Session,
    workspace_runs: list[tuple[ComparisonWorkspaceRun, Project, Run]],
) -> list[ComparisonWorkspaceComparativeRunDescriptor]:
    run_records: list[ComparisonWorkspaceComparativeRunDescriptor] = []
    for _, project_row, run in workspace_runs:
        if run is None or project_row is None:
            continue
        segment_count = session.query(Segment).filter(Segment.run_id == run.id).count()
        export_payload = build_run_export(session=session, project=project_row, run=run)
        manifest = export_payload.get("manifest", {})
        academic_reports = manifest.get("academic_reports", {})
        academic_export_manifest = manifest.get("academic_export_manifest", {})
        config = dict(run.config_json or {})

        if not isinstance(academic_reports, dict):
            academic_reports = {}
        if not isinstance(academic_export_manifest, dict):
            academic_export_manifest = {}

        run_records.append(
            ComparisonWorkspaceComparativeRunDescriptor(
                run_id=run.id,
                project_id=project_row.id,
                project_title=project_row.title,
                status=run.status,
                segment_count=segment_count,
                run_config_mode=str(config.get("mode", DEFAULT_MODE)),
                academic_reports=academic_reports,
                comparative_run_metrics_snapshot=(
                    dict(academic_reports.get("comparative_run_metrics_snapshot", {}))
                )
                if isinstance(academic_reports, dict)
                else {},
                academic_export_manifest=academic_export_manifest,
            )
        )

    return run_records


def _merge_selected_modes(existing_modes: list[str] | None, mode: str) -> list[str]:
    merged = list(existing_modes or [])
    if mode not in merged:
        merged.append(mode)
    return merged


def _resolve_project_activity_actor(
    *,
    principal_type: str | None = None,
    principal_id: str | None = None,
) -> str:
    normalized_principal_type = str(principal_type).strip() if principal_type is not None else ""
    normalized_principal_id = str(principal_id).strip() if principal_id is not None else ""
    if normalized_principal_type and normalized_principal_id:
        return f"{normalized_principal_type}:{normalized_principal_id}"
    if normalized_principal_type:
        return normalized_principal_type
    return "system"


def _append_project_activity_event(
    *,
    session: Session,
    project_id: int,
    event_type: str,
    run_id: int | None = None,
    actor: str = "system",
    event_metadata: dict[str, object] | None = None,
) -> None:
    normalized_event_type = str(event_type).strip().lower()
    if normalized_event_type not in _PROJECT_ACTIVITY_EVENT_TYPES:
        raise ValueError(f"Unsupported project activity event type: {event_type}")
    normalized_actor = str(actor).strip() or "system"
    session.add(
        ProjectActivityEvent(
            project_id=project_id,
            run_id=run_id,
            event_type=normalized_event_type,
            actor=normalized_actor,
            event_metadata=dict(event_metadata or {}),
        )
    )


def _backfill_project_lifecycle_and_activity_records(*, session: Session) -> dict[str, int]:
    transitions_created = 0
    events_created = 0
    projects = session.query(Project).order_by(Project.id.asc()).all()
    for project in projects:
        normalized_lifecycle_state = str(project.lifecycle_state or PROJECT_LIFECYCLE_DRAFT).strip().lower()
        if normalized_lifecycle_state not in set(_CONTROL_PANEL_STATE_ORDER):
            normalized_lifecycle_state = PROJECT_LIFECYCLE_DRAFT

        has_transition = (
            session.query(ProjectLifecycleTransition.id)
            .filter(ProjectLifecycleTransition.project_id == project.id)
            .first()
            is not None
        )
        if not has_transition and normalized_lifecycle_state != PROJECT_LIFECYCLE_DRAFT:
            session.add(
                ProjectLifecycleTransition(
                    project_id=project.id,
                    from_state=PROJECT_LIFECYCLE_DRAFT,
                    to_state=normalized_lifecycle_state,
                    actor="system",
                    created_at=project.created_at,
                )
            )
            transitions_created += 1

        has_activity_event = (
            session.query(ProjectActivityEvent.id)
            .filter(ProjectActivityEvent.project_id == project.id)
            .first()
            is not None
        )
        if has_activity_event:
            continue

        chapter_count = session.query(Chapter).filter(Chapter.project_id == project.id).count()
        if project.ingestion_timestamp is not None or chapter_count > 0:
            session.add(
                ProjectActivityEvent(
                    project_id=project.id,
                    event_type="ingest",
                    actor="system",
                    event_metadata={
                        "backfilled": True,
                        "chapter_count": chapter_count,
                        "source": "legacy_unknown",
                    },
                    created_at=project.ingestion_timestamp or project.created_at,
                )
            )
            events_created += 1

        selected_mode = str(project.selected_mode or DEFAULT_MODE).strip().lower() or DEFAULT_MODE
        if selected_mode != DEFAULT_MODE:
            session.add(
                ProjectActivityEvent(
                    project_id=project.id,
                    event_type="mode_change",
                    actor="system",
                    event_metadata={
                        "backfilled": True,
                        "previous_mode": DEFAULT_MODE,
                        "selected_mode": selected_mode,
                    },
                    created_at=project.created_at,
                )
            )
            events_created += 1

        project_runs = (
            session.query(Run)
            .filter(Run.project_id == project.id)
            .order_by(Run.id.asc())
            .all()
        )
        latest_completed_run_id: int | None = None
        for run in project_runs:
            run_started_at = run.started_at or project.created_at
            run_status = str(run.status or "").strip().lower()
            raw_config = run.config_json if isinstance(run.config_json, dict) else {}
            recovery_state = _coerce_recovery_state(raw_config.get(_PIPELINE_RECOVERY_CONFIG_KEY))
            recovery_attempt = recovery_state.get("attempt")
            try:
                recovery_attempt_int = max(int(recovery_attempt), 0)
            except (TypeError, ValueError):
                recovery_attempt_int = 0

            session.add(
                ProjectActivityEvent(
                    project_id=project.id,
                    run_id=run.id,
                    event_type="run_start",
                    actor="system",
                    event_metadata={
                        "backfilled": True,
                        "mode": str(raw_config.get("mode", selected_mode or DEFAULT_MODE)),
                    },
                    created_at=run_started_at,
                )
            )
            events_created += 1

            if recovery_attempt_int > 0:
                session.add(
                    ProjectActivityEvent(
                        project_id=project.id,
                        run_id=run.id,
                        event_type="rerun",
                        actor="system",
                        event_metadata={
                            "backfilled": True,
                            "attempt": recovery_attempt_int,
                        },
                        created_at=run_started_at,
                    )
                )
                events_created += 1

            if run_status and run_status not in {RUN_STATUS_QUEUED, RUN_STATUS_RUNNING}:
                session.add(
                    ProjectActivityEvent(
                        project_id=project.id,
                        run_id=run.id,
                        event_type="run_complete",
                        actor="system",
                        event_metadata={
                            "backfilled": True,
                            "status": run_status,
                        },
                        created_at=run.finished_at or run_started_at,
                    )
                )
                events_created += 1

            if run_status == RUN_STATUS_COMPLETED:
                latest_completed_run_id = run.id

        if project.last_export_at is not None:
            session.add(
                ProjectActivityEvent(
                    project_id=project.id,
                    run_id=latest_completed_run_id,
                    event_type="export",
                    actor="system",
                    event_metadata={
                        "backfilled": True,
                        "output_schema": "legacy_unknown",
                        "output_format": "legacy_unknown",
                    },
                    created_at=project.last_export_at,
                )
            )
            events_created += 1

    return {
        "projects_scanned": len(projects),
        "transitions_created": transitions_created,
        "events_created": events_created,
    }


def _transition_project_lifecycle_state(
    project: Project,
    next_state: str,
    *,
    session: Session,
    actor: str = "system",
) -> None:
    current_state = str(project.lifecycle_state or "").strip().lower()
    try:
        resolved_state = transition_project_lifecycle_state(
            current_state=current_state,
            next_state=next_state,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invalid project lifecycle transition: {exc}",
        ) from exc
    if resolved_state == current_state:
        return

    normalized_actor = str(actor).strip() or "system"
    project.lifecycle_state = resolved_state
    session.add(
        ProjectLifecycleTransition(
            project_id=project.id,
            from_state=current_state,
            to_state=resolved_state,
            actor=normalized_actor,
        )
    )
    _refresh_project_dashboard_projection(session=session, project=project)


def _build_initial_configuration_snapshot_id(project_id: int) -> str:
    return f"project-{project_id}-config-initial"


def _build_run_configuration_snapshot_id(run_id: int, version: int) -> str:
    return f"run-{run_id}-config-{version}"


def _project_title_needs_fallback(title: str) -> bool:
    normalized = title.strip().lower()
    return normalized in {"", "untitled", "untitled project", "new project"}


def _update_project_ingestion_log(
    project: Project,
    source: str,
    warnings: list[dict[str, object]],
    dedup_actions: list[dict[str, object]] | None = None,
    affected_range: dict[str, int] | None = None,
    normalization_report: dict[str, object] | None = None,
) -> None:
    log_json = dict(project.ingestion_log_json or {})
    existing_warnings = list(log_json.get("warnings", []))
    existing_warnings.extend(warnings)
    log_json["warnings"] = existing_warnings
    if dedup_actions:
        existing_dedup_actions = list(log_json.get("dedup_actions", []))
        existing_dedup_actions.extend(dedup_actions)
        log_json["dedup_actions"] = existing_dedup_actions
    log_json["source"] = source
    if normalization_report is not None:
        log_json["normalization_report"] = normalization_report
    if affected_range is not None:
        log_json["affected_range"] = affected_range
    log_json["updated_at"] = datetime.now(timezone.utc).isoformat()
    project.ingestion_log_json = log_json


def _get_next_chapter_index(session: Session, project_id: int) -> int:
    last_chapter = (
        session.query(Chapter)
        .filter(Chapter.project_id == project_id)
        .order_by(Chapter.chapter_index.desc())
        .first()
    )
    if last_chapter is None:
        return 1
    return int(last_chapter.chapter_index) + 1


def _is_ingestion_row_lock_conflict(error: OperationalError) -> bool:
    original_error = getattr(error, "orig", None)
    sql_state = getattr(original_error, "sqlstate", None) or getattr(original_error, "pgcode", None)
    if sql_state == "55P03":
        return True
    if original_error is not None and "locknotavailable" in original_error.__class__.__name__.lower():
        return True
    return "could not obtain lock on row" in str(original_error).lower()


def _lock_project_for_ingestion(session: Session, project_id: int) -> None:
    try:
        (
            session.query(Project)
            .filter(Project.id == project_id)
            .with_for_update(nowait=True)
            .one_or_none()
        )
    except OperationalError as error:
        if _is_ingestion_row_lock_conflict(error):
            raise IngestionInProgressError(
                detail="Ingestion is already running for this project. Wait for completion before uploading again.",
            ) from error
        raise


def _is_project_chapter_uniqueness_conflict(error: IntegrityError) -> bool:
    error_text = str(getattr(error, "orig", error)).lower()
    return "uq_project_chapter_index" in error_text or "chapters.project_id, chapters.chapter_index" in error_text


def _commit_ingestion_session(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError as error:
        if _is_project_chapter_uniqueness_conflict(error):
            session.rollback()
            raise IngestionInProgressError(
                detail="Ingestion is already running for this project. Wait for completion before uploading again.",
            ) from error
        raise


def _persist_raw_corpus_blob(
    session: Session,
    project_id: int,
    source: str,
    raw_corpus: str,
    *,
    source_filename: str | None = None,
) -> None:
    normalized_source = to_internal_utf8(raw_corpus)
    blob_payload = normalized_source.encode("utf-8")
    session.add(
        ProjectRawCorpusBlob(
            project_id=project_id,
            source=source,
            source_filename=(source_filename or None),
            blob_sha256=hashlib.sha256(blob_payload).hexdigest(),
            raw_corpus_blob=blob_payload,
        )
    )


def _project_allows_source_text_storage(project: Project) -> bool:
    return not bool(project.do_not_store_source_text)


def _build_full_corpus_text(rows: list[tuple[int, str, str]]) -> str:
    return "\n\n".join(row[2] for row in rows)


def _build_ingested_chapter_text_payload(
    project: Project,
    *,
    source_text: str,
    original_to_normalized_offset_map: list[dict[str, int | str]],
) -> tuple[str, str, list[dict[str, int | str]]]:
    if _project_allows_source_text_storage(project):
        return source_text, source_text, original_to_normalized_offset_map

    return "", "", []


def _build_character_map_item_payload(
    row: Character,
    source: str,
    confidence: float,
    source_trace: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "name": row.name.strip(),
        "verbalized_form": row.verbalized_form.strip(),
        "gender": row.gender.strip().lower(),
        "voice_id": row.voice_id.strip() if row.voice_id else None,
        "aliases": row.aliases or [],
        "notes": row.notes.strip() if row.notes else None,
        "source": source,
        "confidence": confidence,
        "source_trace": source_trace or [],
        "inferred_gender": row.inferred_gender,
        "inferred_confidence": row.inferred_confidence,
        "inferred_source_trace": row.inferred_source_trace or [],
    }


def _build_character_map_item_payload_from_row(row: Character) -> CharacterMapItem:
    return CharacterMapItem(
        name=row.name.strip(),
        verbalized_form=row.verbalized_form.strip(),
        gender=row.gender.strip().lower(),
        voice_id=row.voice_id.strip() if row.voice_id else None,
        aliases=row.aliases or [],
        notes=row.notes.strip() if row.notes else None,
        source=row.source,
        confidence=row.confidence,
        inferred_gender=row.inferred_gender,
        inferred_confidence=row.inferred_confidence,
        inferred_source_trace=row.inferred_source_trace or [],
    )


def _build_character_proposal_item_payload_from_row(row: CharacterProposal) -> CharacterProposalItem:
    return CharacterProposalItem(
        id=row.id,
        name=row.name.strip(),
        verbalized_form=row.verbalized_form.strip(),
        gender="unknown",
        aliases=row.aliases or [],
        notes=row.notes.strip() if row.notes else None,
        source=row.source,
        confidence=row.confidence,
        source_trace=row.source_trace or [],
        inferred_gender=row.inferred_gender,
        inferred_confidence=row.inferred_confidence,
        inferred_source_trace=row.inferred_source_trace or [],
        status=row.status,
        extractor_version=row.extractor_version,
        extraction_batch_id=row.extraction_batch_id,
        reviewed_at=row.reviewed_at,
        reviewed_by=row.reviewed_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _build_character_payload_from_proposal(row: CharacterProposal) -> dict[str, object]:
    return {
        "name": row.name.strip(),
        "verbalized_form": row.verbalized_form.strip(),
        "gender": "unknown",
        "aliases": row.aliases or [],
        "notes": row.notes.strip() if row.notes else None,
        "source": row.source,
        "confidence": row.confidence,
        "source_trace": row.source_trace or [],
        "inferred_gender": row.inferred_gender,
        "inferred_confidence": row.inferred_confidence,
        "inferred_source_trace": row.inferred_source_trace or [],
    }


def _persist_character_proposals(
    *,
    session: Session,
    project_id: int,
    candidate_payloads: list[dict[str, object]],
    extraction_batch_id: str,
    replace_existing_proposed: bool = True,
) -> list[CharacterProposal]:
    if replace_existing_proposed:
        session.query(CharacterProposal).filter(
            CharacterProposal.project_id == project_id,
            CharacterProposal.status == "proposed",
        ).delete()

    persisted_rows: list[CharacterProposal] = []
    for payload in candidate_payloads:
        name = str(payload.get("name") or "").strip()
        if not name:
            continue

        row = CharacterProposal(
            project_id=project_id,
            name=name,
            normalized_name=normalize_candidate_key(name),
            verbalized_form=str(payload.get("verbalized_form") or name).strip() or name,
            aliases=list(payload.get("aliases") or []),
            notes=(str(payload.get("notes")).strip() if payload.get("notes") is not None else None),
            source=str(payload.get("source") or "auto").strip() or "auto",
            confidence=float(payload.get("confidence") or 0.0),
            source_trace=list(payload.get("source_trace") or []),
            inferred_gender=str(payload.get("inferred_gender") or "unknown").strip().lower() or "unknown",
            inferred_confidence=float(payload.get("inferred_confidence") or 0.0),
            inferred_source_trace=list(payload.get("inferred_source_trace") or []),
            status="proposed",
            extractor_version=CHARACTER_EXTRACTION_EXTRACTOR_VERSION,
            extraction_batch_id=extraction_batch_id,
        )
        session.add(row)
        persisted_rows.append(row)

    session.flush()
    return persisted_rows


def _payload_has_auto_apply_evidence(payload: dict[str, object]) -> bool:
    source_trace = payload.get("source_trace")
    if not isinstance(source_trace, list):
        return False

    strong_kinds = {
        "dialogue_attribution",
        "narrative_attribution",
        "bracketed_heading",
        "line_value_name",
        "llm_extraction",
        "llm_verification",
    }
    for row in source_trace:
        if isinstance(row, dict) and str(row.get("kind") or "").strip() in strong_kinds:
            return True
    return False


def _auto_apply_character_candidates(
    *,
    session: Session,
    project_id: int,
    candidate_payloads: list[dict[str, object]],
    min_confidence: float,
) -> int:
    selected_payloads: list[dict[str, object]] = []
    for payload in candidate_payloads:
        confidence = float(payload.get("confidence") or 0.0)
        if confidence < min_confidence:
            continue
        if not _payload_has_auto_apply_evidence(payload):
            continue
        selected_payloads.append(payload)

    if not selected_payloads:
        return 0

    existing_rows = (
        session.query(Character)
        .filter(Character.project_id == project_id)
        .order_by(Character.name.asc())
        .all()
    )
    merged_payloads = merge_character_candidates(
        [
            _build_character_map_item_payload(
                row=row,
                source=row.source,
                confidence=row.confidence,
                source_trace=[],
            )
            for row in existing_rows
        ]
        + selected_payloads
    )

    session.query(Character).filter(Character.project_id == project_id).delete()
    for row in merged_payloads:
        session.add(
            Character(
                project_id=project_id,
                name=str(row.get("name") or "").strip(),
                verbalized_form=str(row.get("verbalized_form") or row.get("name") or "").strip(),
                gender=str(row.get("gender") or "unknown").strip().lower() or "unknown",
                aliases=list(row.get("aliases") or []),
                notes=(str(row.get("notes")).strip() if row.get("notes") is not None else None),
                source=str(row.get("source") or "auto").strip() or "auto",
                confidence=float(row.get("confidence") or 0.0),
                inferred_gender=str(row.get("inferred_gender") or "unknown").strip().lower() or "unknown",
                inferred_confidence=float(row.get("inferred_confidence") or 0.0),
                inferred_source_trace=list(row.get("inferred_source_trace") or []),
            )
        )

    project = _get_project_or_404(session, project_id)
    project.character_map_finalized = False
    project_runs = session.query(Run).filter(Run.project_id == project.id).all()
    mark_runs_stale_for_gender_edit(project_runs)
    recompute_voice_previews_for_runs(session, project=project, runs=project_runs)
    session.add(project)
    session.add(
        _persist_character_map_snapshot(
            session=session,
            project_id=project_id,
            source="auto_extract",
        )
    )
    session.add(
        _persist_voice_map_snapshot(
            session=session,
            project_id=project_id,
            source="auto_extract",
        )
    )

    return len(selected_payloads)


def _build_character_map_snapshot_payload(project_id: int, session: Session) -> dict[str, object]:
    character_rows = (
        session.query(Character)
        .filter(Character.project_id == project_id)
        .order_by(Character.name.asc())
        .all()
    )
    return {
        "schema_version": "1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "character_count": len(character_rows),
        "characters": [
            _build_character_map_item_payload_from_row(row).model_dump()
            for row in character_rows
        ],
    }


def _next_character_map_snapshot_version(session: Session, project_id: int) -> int:
    latest_version = (
        session.query(CharacterMapSnapshot.version)
        .filter(CharacterMapSnapshot.project_id == project_id)
        .order_by(CharacterMapSnapshot.version.desc())
        .first()
    )
    if latest_version is None:
        return 1
    return int(latest_version[0]) + 1


def _persist_character_map_snapshot(
    session: Session,
    project_id: int,
    source: str,
    run_id: int | None = None,
) -> CharacterMapSnapshot:
    session.flush()
    snapshot_payload = _build_character_map_snapshot_payload(
        project_id=project_id,
        session=session,
    )
    return CharacterMapSnapshot(
        project_id=project_id,
        run_id=run_id,
        version=_next_character_map_snapshot_version(session=session, project_id=project_id),
        source=source.strip() or "project_edit",
        snapshot_json=snapshot_payload,
        snapshot_json_sha256=_build_snapshot_json_checksum(snapshot_payload),
    )


def _build_run_configuration_snapshot_payload(
    project_id: int,
    run_id: int,
    run_config: Mapping[str, object],
    version: int,
) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "config_schema_version": str(run_config.get("config_schema_version", RUN_CONFIG_SCHEMA_VERSION)),
        "project_id": int(project_id),
        "run_id": int(run_id),
        "version": int(version),
        "configuration_snapshot_id": _build_run_configuration_snapshot_id(run_id=run_id, version=version),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "mode": str(run_config.get("mode", DEFAULT_MODE)),
        "configuration": dict(run_config),
    }


def _next_run_configuration_snapshot_version(session: Session, project_id: int) -> int:
    latest_version = (
        session.query(RunConfigurationSnapshot.version)
        .filter(RunConfigurationSnapshot.project_id == project_id)
        .order_by(RunConfigurationSnapshot.version.desc())
        .first()
    )
    if latest_version is None:
        return 1
    return int(latest_version[0]) + 1


def _persist_run_configuration_snapshot(
    session: Session,
    project_id: int,
    run_id: int,
    source: str,
    run_config: Mapping[str, object],
) -> RunConfigurationSnapshot:
    session.flush()
    version = _next_run_configuration_snapshot_version(session=session, project_id=project_id)
    snapshot_payload = _build_run_configuration_snapshot_payload(
        project_id=project_id,
        run_id=run_id,
        run_config=run_config,
        version=version,
    )
    return RunConfigurationSnapshot(
        project_id=project_id,
        run_id=run_id,
        version=version,
        source=source.strip() or "run_capture",
        snapshot_json=snapshot_payload,
        snapshot_json_sha256=_build_snapshot_json_checksum(snapshot_payload),
    )


def _build_pronunciation_dictionary_snapshot_payload(
    project_id: int,
    session: Session,
) -> dict[str, object]:
    entries = (
        session.query(PronunciationDictionary)
        .filter(PronunciationDictionary.project_id == project_id)
        .order_by(
            PronunciationDictionary.scope.asc(),
            PronunciationDictionary.character_name.asc(),
            PronunciationDictionary.term.asc(),
        )
        .all()
    )

    by_scope: dict[str, list[dict[str, object]]] = {
        scope: [] for scope in ["global", "character", "place", "artifact", "invented"]
    }
    for entry in entries:
        payload: dict[str, object] = {
            "term": entry.term.strip(),
            "verbalized_form": entry.verbalized_form.strip(),
            "source": entry.source,
            "confidence": entry.confidence,
        }
        if entry.scope == "character":
            payload["character_name"] = entry.character_name.strip()
        by_scope[entry.scope].append(payload)

    return {
        "schema_version": "1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "entry_count": len(entries),
        "by_scope": by_scope,
    }


def _next_pronunciation_dictionary_snapshot_version(session: Session, project_id: int) -> int:
    latest_version = (
        session.query(PronunciationDictionarySnapshot.version)
        .filter(PronunciationDictionarySnapshot.project_id == project_id)
        .order_by(PronunciationDictionarySnapshot.version.desc())
        .first()
    )
    if latest_version is None:
        return 1
    return int(latest_version[0]) + 1


def _persist_pronunciation_dictionary_snapshot(
    session: Session,
    project_id: int,
    source: str,
    run_id: int | None = None,
) -> PronunciationDictionarySnapshot:
    session.flush()
    snapshot_payload = _build_pronunciation_dictionary_snapshot_payload(
        project_id=project_id,
        session=session,
    )
    return PronunciationDictionarySnapshot(
        project_id=project_id,
        run_id=run_id,
        version=_next_pronunciation_dictionary_snapshot_version(
            session=session,
            project_id=project_id,
        ),
        source=source.strip() or "dictionary_edit",
        snapshot_json=snapshot_payload,
        snapshot_json_sha256=_build_snapshot_json_checksum(snapshot_payload),
    )


def _build_voice_map_snapshot_payload(project_id: int, session: Session) -> dict[str, object]:
    character_rows = (
        session.query(Character)
        .filter(Character.project_id == project_id)
        .order_by(Character.name.asc())
        .all()
    )

    mappings: list[dict[str, object]] = []
    explicit_map_count = 0
    for row in character_rows:
        mapped_voice_id = (
            row.voice_map.voice_id.strip()
            if getattr(row, "voice_map", None) is not None and row.voice_map.voice_id
            else None
        )
        legacy_voice_id = row.voice_id.strip() if row.voice_id else None
        resolved_voice_id = legacy_voice_id
        voice_source = "default"
        if mapped_voice_id:
            resolved_voice_id = mapped_voice_id
            voice_source = "character_voice_map"
            explicit_map_count += 1
        elif legacy_voice_id:
            voice_source = "character_voice_id"

        mappings.append(
            {
                "character_id": row.id,
                "name": row.name.strip(),
                "verbalized_form": row.verbalized_form.strip(),
                "gender": row.gender.strip().lower(),
                "voice_id": resolved_voice_id,
                "voice_source": voice_source,
            }
        )

    return {
        "schema_version": "1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "character_count": len(character_rows),
        "explicit_character_voice_map_count": explicit_map_count,
        "mappings": mappings,
    }


def _next_voice_map_snapshot_version(session: Session, project_id: int) -> int:
    latest_version = (
        session.query(VoiceMapSnapshot.version)
        .filter(VoiceMapSnapshot.project_id == project_id)
        .order_by(VoiceMapSnapshot.version.desc())
        .first()
    )
    if latest_version is None:
        return 1
    return int(latest_version[0]) + 1


def _persist_voice_map_snapshot(
    session: Session,
    project_id: int,
    source: str,
    run_id: int | None = None,
) -> VoiceMapSnapshot:
    session.flush()
    snapshot_payload = _build_voice_map_snapshot_payload(
        project_id=project_id,
        session=session,
    )
    return VoiceMapSnapshot(
        project_id=project_id,
        run_id=run_id,
        version=_next_voice_map_snapshot_version(
            session=session,
            project_id=project_id,
        ),
        source=source.strip() or "voice_map_edit",
        snapshot_json=snapshot_payload,
        snapshot_json_sha256=_build_snapshot_json_checksum(snapshot_payload),
    )


def _build_time_series_snapshot_payload(
    project_id: int,
    run_id: int,
    run_config: dict,
    time_series: object,
) -> dict[str, object]:
    serializable_time_series = time_series if isinstance(time_series, dict) else {}
    return {
        "schema_version": "1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_id": project_id,
        "run_id": run_id,
        "mode": str(run_config.get("mode", DEFAULT_MODE)),
        "segment_count": len(serializable_time_series.get("emotion_valence", [])),
        "time_series": serializable_time_series,
    }


def _next_time_series_snapshot_version(session: Session, project_id: int) -> int:
    latest_version = (
        session.query(TimeSeriesSnapshot.version)
        .filter(TimeSeriesSnapshot.project_id == project_id)
        .order_by(TimeSeriesSnapshot.version.desc())
        .first()
    )
    if latest_version is None:
        return 1
    return int(latest_version[0]) + 1


def _persist_time_series_snapshot(
    session: Session,
    project_id: int,
    source: str,
    run: Run,
    time_series: object,
) -> TimeSeriesSnapshot:
    session.flush()
    snapshot_payload = _build_time_series_snapshot_payload(
        project_id=project_id,
        run_id=run.id,
        run_config=dict(run.config_json or {}),
        time_series=time_series,
    )
    return TimeSeriesSnapshot(
        project_id=project_id,
        run_id=run.id,
        version=_next_time_series_snapshot_version(session=session, project_id=project_id),
        source=source.strip() or "run_capture",
        snapshot_json=snapshot_payload,
        snapshot_json_sha256=_build_snapshot_json_checksum(snapshot_payload),
    )


def _build_pronunciation_dictionary_payload(entry: PronunciationDictionary) -> PronunciationDictionaryItem:
    return PronunciationDictionaryItem(
        term=entry.term.strip(),
        verbalized_form=entry.verbalized_form.strip(),
        source=entry.source,
        confidence=entry.confidence,
    )


def _normalize_character_reference_name(raw_name: str) -> str:
    normalized = raw_name.strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="character_name must not be blank",
        )
    return normalized


def _build_inferred_gender_lookup(
    character_rows: list[Character],
    chapter_rows: list[tuple[str] | str],
) -> dict[str, dict[str, object]]:
    character_names = [row.name for row in character_rows]
    chapter_texts: list[str] = []
    for raw_row in chapter_rows:
        if isinstance(raw_row, tuple):
            chapter_texts.append(str(raw_row[0] or ""))
        else:
            chapter_texts.append(str(raw_row or ""))

    if not character_names:
        return {}

    results = infer_character_genders(character_names=character_names, chapter_texts=chapter_texts)
    inferred_lookup: dict[str, dict[str, object]] = {}
    for result in results:
        normalized_name = normalize_candidate_key(result["name"])
        inferred_lookup[normalized_name] = result
    return inferred_lookup


def _coalesce_internal_thought_policy(
    project: Project,
    explicit_overrides: dict[str, object],
) -> None:
    project_voice_config = dict(project.voice_config_json or {})

    if "internal_thought_voice_policy" not in explicit_overrides:
        explicit_overrides["internal_thought_voice_policy"] = _normalize_internal_thought_voice_policy(
            project_voice_config.get("internal_thought_voice_policy")
        )

    if "internal_thought_voice" not in explicit_overrides:
        project_thought_voice = str(project_voice_config.get("thought_voice", "")).strip()
        if project_thought_voice:
            explicit_overrides["internal_thought_voice"] = project_thought_voice


def _resolve_contradiction_review_required(
    *,
    project: Project,
    run: Run | None = None,
) -> bool:
    if run is not None:
        run_config = run.config_json if isinstance(run.config_json, dict) else {}
        override = run_config.get("contradiction_review_required")
        if isinstance(override, bool):
            return override

    mode_name = run.config_json.get("mode") if run is not None and isinstance(run.config_json, dict) else None
    selected_mode = str(mode_name).strip() if mode_name else project.selected_mode
    try:
        profile = load_mode_profile(selected_mode)
        profile_value = profile.get("contradiction_review_required")
        return bool(profile_value)
    except ValueError:
        return True


def _coerce_utc_datetime(value: object | None) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _coerce_recovery_state(value: object | None) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return dict(value)


def _read_pipeline_recovery_state(run: Run) -> dict[str, object]:
    config = run.config_json or {}
    if not isinstance(config, dict):
        return {}
    return _coerce_recovery_state(config.get(_PIPELINE_RECOVERY_CONFIG_KEY))


def _set_pipeline_recovery_state(
    run: Run,
    *,
    session: Session,
    status: str,
    metadata: dict[str, object] | None = None,
) -> None:
    raw_config = run.config_json
    run_config = raw_config.copy() if isinstance(raw_config, dict) else {}
    current_recovery_state = _coerce_recovery_state(run_config.get(_PIPELINE_RECOVERY_CONFIG_KEY))
    current_recovery_state.update(metadata or {})
    current_recovery_state.update(
        {
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    run_config[_PIPELINE_RECOVERY_CONFIG_KEY] = current_recovery_state
    run.config_json = run_config
    session.add(run)


def _clear_run_pipeline_artifacts(session: Session, run: Run) -> None:
    session.query(LLMCall).filter(LLMCall.run_id == run.id).delete()
    session.query(SubSegmentTag).filter(SubSegmentTag.run_id == run.id).delete()
    session.query(Segment).filter(Segment.run_id == run.id).delete()
    session.query(RunNormalizedCorpusBlob).filter(RunNormalizedCorpusBlob.run_id == run.id).delete()


def _is_run_recoverable(run: Run, now: datetime | None = None) -> bool:
    if run.status == "interrupted":
        return True
    if run.status != RUN_STATUS_RUNNING:
        return False
    reference_time = _coerce_utc_datetime(run.started_at)
    recovery_state = _read_pipeline_recovery_state(run)
    recovery_started = _coerce_utc_datetime(recovery_state.get("updated_at"))
    if recovery_started is not None:
        reference_time = recovery_started

    if reference_time is None:
        return True

    now = now or datetime.now(timezone.utc)
    return (now - reference_time).total_seconds() >= _RUN_RECOVERY_STALE_WINDOW_SECONDS


def _prepare_run_recovery_config(run_config: dict[str, object], *, attempt: int) -> dict[str, object]:
    recovery_state = _coerce_recovery_state(run_config.get(_PIPELINE_RECOVERY_CONFIG_KEY))
    recovery_state["attempt"] = attempt
    recovery_state["status"] = "running"
    recovery_state["updated_at"] = datetime.now(timezone.utc).isoformat()
    recovery_state["reason"] = "manual_recovery"
    return {**run_config, _PIPELINE_RECOVERY_CONFIG_KEY: recovery_state}


def _coerce_non_negative_int(value: object) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed


def _build_run_artifact_integrity_report(
    *,
    session: Session,
    run: Run,
) -> dict[str, object]:
    run_config = run.config_json
    if not isinstance(run_config, dict):
        run_config = {}

    checks: list[dict[str, object]] = []

    def _record_check(name: str, passed: bool, details: dict[str, object] | None = None) -> None:
        checks.append(
            {
                "artifact": name,
                "passed": passed,
                "details": dict(details or {}),
            },
        )

    normalized_corpus_blobs = (
        session.query(RunNormalizedCorpusBlob)
        .filter(RunNormalizedCorpusBlob.run_id == run.id)
        .all()
    )
    if len(normalized_corpus_blobs) != 1:
        _record_check(
            "run_normalized_corpus_blob",
            False,
            {
                "observed_count": len(normalized_corpus_blobs),
                "expected_count": 1,
            },
        )
    else:
        normalized_corpus_blob = normalized_corpus_blobs[0]
        blob_bytes = normalized_corpus_blob.normalized_corpus_blob or b""
        observed_corpus_sha256 = hashlib.sha256(blob_bytes).hexdigest()
        corpus_integrity_ok = observed_corpus_sha256 == normalized_corpus_blob.corpus_sha256
        _record_check(
            "run_normalized_corpus_blob",
            corpus_integrity_ok,
            {
                "blob_id": normalized_corpus_blob.id,
                "expected_sha256": normalized_corpus_blob.corpus_sha256,
                "observed_sha256": observed_corpus_sha256,
                "size_bytes": len(blob_bytes),
                "reason": "hash_mismatch" if not corpus_integrity_ok else "ok",
            },
        )

    expected_run_configuration_snapshot = run.run_configuration_snapshot
    if expected_run_configuration_snapshot is None:
        _record_check("run_configuration_snapshot", False, {"reason": "run_configuration_snapshot_not_found"})
    else:
        run_configuration_snapshot_version = _coerce_non_negative_int(
            run_config.get("configuration_snapshot_version")
        )
        run_configuration_payload = expected_run_configuration_snapshot.snapshot_json
        run_configuration_payload_hash = _build_snapshot_json_checksum(run_configuration_payload)
        run_configuration_stored_hash = str(
            getattr(expected_run_configuration_snapshot, "snapshot_json_sha256", "")
        )
        if not isinstance(run_configuration_payload, dict):
            _record_check(
                "run_configuration_snapshot",
                False,
                {
                    "reason": "configuration_snapshot_payload_corrupted",
                    "payload_hash_mismatch": True,
                    "expected_payload_hash": run_configuration_payload_hash,
                    "stored_payload_hash": run_configuration_stored_hash,
                },
            )
        elif run_configuration_payload_hash != run_configuration_stored_hash:
            _record_check(
                "run_configuration_snapshot",
                False,
                {
                    "reason": "configuration_snapshot_payload_hash_mismatch",
                    "payload_hash_mismatch": True,
                    "expected_payload_hash": run_configuration_payload_hash,
                    "stored_payload_hash": run_configuration_stored_hash,
                },
            )
        elif run_configuration_snapshot_version is not None:
            expected_snapshot_id = _build_run_configuration_snapshot_id(
                run_id=run.id,
                version=run_configuration_snapshot_version,
            )
            observed_snapshot_id = str(
                (
                    expected_run_configuration_snapshot.snapshot_json or {}
                ).get("configuration_snapshot_id", "")
            )
            if observed_snapshot_id != expected_snapshot_id:
                _record_check(
                    "run_configuration_snapshot",
                    False,
                    {
                        "reason": "configuration_snapshot_id_mismatch",
                        "payload_hash_mismatch": False,
                        "expected_snapshot_id": expected_snapshot_id,
                        "observed_snapshot_id": observed_snapshot_id,
                    },
                )
            elif run_configuration_snapshot_version != expected_run_configuration_snapshot.version:
                _record_check(
                    "run_configuration_snapshot",
                    False,
                    {
                        "reason": "configuration_snapshot_version_mismatch",
                        "payload_hash_mismatch": False,
                        "expected_version": run_configuration_snapshot_version,
                        "observed_version": expected_run_configuration_snapshot.version,
                    },
                )
            else:
                _record_check(
                    "run_configuration_snapshot",
                    True,
                    {
                        "payload_hash_mismatch": False,
                        "expected_payload_hash": run_configuration_payload_hash,
                        "stored_payload_hash": run_configuration_stored_hash,
                    },
                )
        else:
            _record_check(
                "run_configuration_snapshot",
                False,
                {
                    "reason": "configuration_snapshot_version_missing",
                    "payload_hash_mismatch": False,
                    "expected_payload_hash": run_configuration_payload_hash,
                    "stored_payload_hash": run_configuration_stored_hash,
                },
            )

    character_map_snapshot = run.character_map_snapshot
    if character_map_snapshot is None:
        _record_check("character_map_snapshot", False, {"reason": "character_map_snapshot_not_found"})
    else:
        expected_character_map_snapshot_id = _coerce_non_negative_int(
            run_config.get("character_map_snapshot_id")
        )
        expected_character_map_snapshot_version = _coerce_non_negative_int(
            run_config.get("character_map_snapshot_version")
        )
        character_map_payload = character_map_snapshot.snapshot_json
        character_map_payload_hash = _build_snapshot_json_checksum(character_map_payload)
        character_map_stored_hash = str(
            getattr(character_map_snapshot, "snapshot_json_sha256", "")
        )
        if not isinstance(character_map_payload, dict):
            _record_check(
                "character_map_snapshot",
                False,
                {
                    "snapshot_id": character_map_snapshot.id,
                    "snapshot_version": character_map_snapshot.version,
                    "reason": "character_map_snapshot_payload_corrupted",
                    "payload_hash_mismatch": True,
                    "expected_payload_hash": character_map_payload_hash,
                    "stored_payload_hash": character_map_stored_hash,
                },
            )
        elif character_map_payload_hash != character_map_stored_hash:
            _record_check(
                "character_map_snapshot",
                False,
                {
                    "snapshot_id": character_map_snapshot.id,
                    "snapshot_version": character_map_snapshot.version,
                    "reason": "character_map_snapshot_payload_hash_mismatch",
                    "payload_hash_mismatch": True,
                    "expected_payload_hash": character_map_payload_hash,
                    "stored_payload_hash": character_map_stored_hash,
                },
            )
        else:
            character_map_snapshot_integrity_ok = (
                character_map_snapshot.run_id == run.id
                and (
                    expected_character_map_snapshot_id is None
                    or character_map_snapshot.id == expected_character_map_snapshot_id
                )
                and (
                    expected_character_map_snapshot_version is None
                    or character_map_snapshot.version == expected_character_map_snapshot_version
                )
            )
            if character_map_snapshot_integrity_ok:
                _record_check(
                    "character_map_snapshot",
                    True,
                    {
                        "snapshot_id": character_map_snapshot.id,
                        "snapshot_version": character_map_snapshot.version,
                        "payload_hash_mismatch": False,
                        "expected_payload_hash": character_map_payload_hash,
                        "stored_payload_hash": character_map_stored_hash,
                    },
                )
            else:
                _record_check(
                    "character_map_snapshot",
                    False,
                    {
                        "snapshot_id": character_map_snapshot.id,
                        "snapshot_version": character_map_snapshot.version,
                        "expected_snapshot_id": expected_character_map_snapshot_id,
                        "expected_snapshot_version": expected_character_map_snapshot_version,
                        "payload_hash_mismatch": False,
                        "expected_payload_hash": character_map_payload_hash,
                        "stored_payload_hash": character_map_stored_hash,
                    },
                )

    pronunciation_dictionary_snapshot = run.pronunciation_dictionary_snapshot
    if pronunciation_dictionary_snapshot is None:
        _record_check(
            "pronunciation_dictionary_snapshot",
            False,
            {"reason": "pronunciation_dictionary_snapshot_not_found"},
        )
    else:
        expected_pronunciation_dictionary_snapshot_id = _coerce_non_negative_int(
            run_config.get("pronunciation_dictionary_snapshot_id")
        )
        expected_pronunciation_dictionary_snapshot_version = _coerce_non_negative_int(
            run_config.get("pronunciation_dictionary_snapshot_version")
        )
        pronunciation_dictionary_payload = pronunciation_dictionary_snapshot.snapshot_json
        pronunciation_dictionary_payload_hash = _build_snapshot_json_checksum(pronunciation_dictionary_payload)
        pronunciation_dictionary_stored_hash = str(
            getattr(pronunciation_dictionary_snapshot, "snapshot_json_sha256", "")
        )
        if not isinstance(pronunciation_dictionary_payload, dict):
            _record_check(
                "pronunciation_dictionary_snapshot",
                False,
                {
                    "snapshot_id": pronunciation_dictionary_snapshot.id,
                    "snapshot_version": pronunciation_dictionary_snapshot.version,
                    "reason": "pronunciation_dictionary_snapshot_payload_corrupted",
                    "payload_hash_mismatch": True,
                    "expected_payload_hash": pronunciation_dictionary_payload_hash,
                    "stored_payload_hash": pronunciation_dictionary_stored_hash,
                },
            )
        elif pronunciation_dictionary_payload_hash != pronunciation_dictionary_stored_hash:
            _record_check(
                "pronunciation_dictionary_snapshot",
                False,
                {
                    "snapshot_id": pronunciation_dictionary_snapshot.id,
                    "snapshot_version": pronunciation_dictionary_snapshot.version,
                    "reason": "pronunciation_dictionary_snapshot_payload_hash_mismatch",
                    "payload_hash_mismatch": True,
                    "expected_payload_hash": pronunciation_dictionary_payload_hash,
                    "stored_payload_hash": pronunciation_dictionary_stored_hash,
                },
            )
        else:
            snapshot_integrity_ok = (
                pronunciation_dictionary_snapshot.run_id == run.id
                and (
                    expected_pronunciation_dictionary_snapshot_id is None
                    or pronunciation_dictionary_snapshot.id == expected_pronunciation_dictionary_snapshot_id
                )
                and (
                    expected_pronunciation_dictionary_snapshot_version is None
                    or pronunciation_dictionary_snapshot.version == expected_pronunciation_dictionary_snapshot_version
                )
            )
            if snapshot_integrity_ok:
                _record_check(
                    "pronunciation_dictionary_snapshot",
                    True,
                    {
                        "snapshot_id": pronunciation_dictionary_snapshot.id,
                        "snapshot_version": pronunciation_dictionary_snapshot.version,
                        "payload_hash_mismatch": False,
                        "expected_payload_hash": pronunciation_dictionary_payload_hash,
                        "stored_payload_hash": pronunciation_dictionary_stored_hash,
                    },
                )
            else:
                _record_check(
                    "pronunciation_dictionary_snapshot",
                    False,
                    {
                        "snapshot_id": pronunciation_dictionary_snapshot.id,
                        "snapshot_version": pronunciation_dictionary_snapshot.version,
                        "expected_snapshot_id": expected_pronunciation_dictionary_snapshot_id,
                        "expected_snapshot_version": expected_pronunciation_dictionary_snapshot_version,
                        "payload_hash_mismatch": False,
                        "expected_payload_hash": pronunciation_dictionary_payload_hash,
                        "stored_payload_hash": pronunciation_dictionary_stored_hash,
                    },
                )

    voice_map_snapshot = run.voice_map_snapshot
    if voice_map_snapshot is None:
        _record_check("voice_map_snapshot", False, {"reason": "voice_map_snapshot_not_found"})
    else:
        expected_voice_map_snapshot_id = _coerce_non_negative_int(run_config.get("voice_map_snapshot_id"))
        expected_voice_map_snapshot_version = _coerce_non_negative_int(run_config.get("voice_map_snapshot_version"))
        voice_map_payload = voice_map_snapshot.snapshot_json
        voice_map_payload_hash = _build_snapshot_json_checksum(voice_map_payload)
        voice_map_stored_hash = str(getattr(voice_map_snapshot, "snapshot_json_sha256", ""))
        if not isinstance(voice_map_payload, dict):
            _record_check(
                "voice_map_snapshot",
                False,
                {
                    "snapshot_id": voice_map_snapshot.id,
                    "snapshot_version": voice_map_snapshot.version,
                    "reason": "voice_map_snapshot_payload_corrupted",
                    "payload_hash_mismatch": True,
                    "expected_payload_hash": voice_map_payload_hash,
                    "stored_payload_hash": voice_map_stored_hash,
                },
            )
        elif voice_map_payload_hash != voice_map_stored_hash:
            _record_check(
                "voice_map_snapshot",
                False,
                {
                    "snapshot_id": voice_map_snapshot.id,
                    "snapshot_version": voice_map_snapshot.version,
                    "reason": "voice_map_snapshot_payload_hash_mismatch",
                    "payload_hash_mismatch": True,
                    "expected_payload_hash": voice_map_payload_hash,
                    "stored_payload_hash": voice_map_stored_hash,
                },
            )
        else:
            snapshot_integrity_ok = (
                voice_map_snapshot.run_id == run.id
                and (
                    expected_voice_map_snapshot_id is None
                    or voice_map_snapshot.id == expected_voice_map_snapshot_id
                )
                and (
                    expected_voice_map_snapshot_version is None
                    or voice_map_snapshot.version == expected_voice_map_snapshot_version
                )
            )
            if snapshot_integrity_ok:
                _record_check(
                    "voice_map_snapshot",
                    True,
                    {
                        "snapshot_id": voice_map_snapshot.id,
                        "snapshot_version": voice_map_snapshot.version,
                        "payload_hash_mismatch": False,
                        "expected_payload_hash": voice_map_payload_hash,
                        "stored_payload_hash": voice_map_stored_hash,
                    },
                )
            else:
                _record_check(
                    "voice_map_snapshot",
                    False,
                    {
                        "snapshot_id": voice_map_snapshot.id,
                        "snapshot_version": voice_map_snapshot.version,
                        "expected_snapshot_id": expected_voice_map_snapshot_id,
                        "expected_snapshot_version": expected_voice_map_snapshot_version,
                        "payload_hash_mismatch": False,
                        "expected_payload_hash": voice_map_payload_hash,
                        "stored_payload_hash": voice_map_stored_hash,
                    },
                )

    time_series_snapshot = (
        session.query(TimeSeriesSnapshot)
        .filter(TimeSeriesSnapshot.run_id == run.id)
        .order_by(TimeSeriesSnapshot.id.desc())
        .first()
    )
    if time_series_snapshot is None:
        _record_check("time_series_snapshot", False, {"reason": "time_series_snapshot_not_found"})
    else:
        expected_time_series_snapshot_id = _coerce_non_negative_int(
            run_config.get("time_series_snapshot_id")
        )
        expected_time_series_snapshot_version = _coerce_non_negative_int(
            run_config.get("time_series_snapshot_version")
        )
        time_series_payload = time_series_snapshot.snapshot_json
        time_series_payload_hash = _build_snapshot_json_checksum(time_series_payload)
        time_series_stored_hash = str(getattr(time_series_snapshot, "snapshot_json_sha256", ""))
        if not isinstance(time_series_payload, dict):
            _record_check(
                "time_series_snapshot",
                False,
                {
                    "snapshot_id": time_series_snapshot.id,
                    "snapshot_version": time_series_snapshot.version,
                    "reason": "time_series_snapshot_payload_corrupted",
                    "payload_hash_mismatch": True,
                    "expected_payload_hash": time_series_payload_hash,
                    "stored_payload_hash": time_series_stored_hash,
                },
            )
        elif time_series_payload_hash != time_series_stored_hash:
            _record_check(
                "time_series_snapshot",
                False,
                {
                    "snapshot_id": time_series_snapshot.id,
                    "snapshot_version": time_series_snapshot.version,
                    "reason": "time_series_snapshot_payload_hash_mismatch",
                    "payload_hash_mismatch": True,
                    "expected_payload_hash": time_series_payload_hash,
                    "stored_payload_hash": time_series_stored_hash,
                },
            )
        else:
            snapshot_integrity_ok = (
                (expected_time_series_snapshot_id is None or time_series_snapshot.id == expected_time_series_snapshot_id)
                and (
                    expected_time_series_snapshot_version is None
                    or time_series_snapshot.version == expected_time_series_snapshot_version
                )
            )
            if snapshot_integrity_ok:
                _record_check(
                    "time_series_snapshot",
                    True,
                    {
                        "snapshot_id": time_series_snapshot.id,
                        "snapshot_version": time_series_snapshot.version,
                        "payload_hash_mismatch": False,
                        "expected_payload_hash": time_series_payload_hash,
                        "stored_payload_hash": time_series_stored_hash,
                    },
                )
            else:
                _record_check(
                    "time_series_snapshot",
                    False,
                    {
                        "snapshot_id": time_series_snapshot.id,
                        "snapshot_version": time_series_snapshot.version,
                        "expected_snapshot_id": expected_time_series_snapshot_id,
                        "expected_snapshot_version": expected_time_series_snapshot_version,
                        "payload_hash_mismatch": False,
                        "expected_payload_hash": time_series_payload_hash,
                        "stored_payload_hash": time_series_stored_hash,
                    },
                )

    project_raw_corpus_blobs = (
        session.query(ProjectRawCorpusBlob)
        .filter(ProjectRawCorpusBlob.project_id == run.project_id)
        .order_by(ProjectRawCorpusBlob.id.asc())
        .all()
    )
    if not project_raw_corpus_blobs:
        project = session.query(Project).filter(Project.id == run.project_id).one_or_none()
        if project is not None and project.do_not_store_source_text:
            _record_check(
                "project_raw_corpus_blobs",
                True,
                {
                    "reason": "do_not_store_source_text",
                    "observed_count": 0,
                },
            )
        else:
            _record_check("project_raw_corpus_blobs", False, {"reason": "raw_corpus_blob_not_found"})
    else:
        raw_corpus_mismatches: list[dict[str, object]] = []
        for raw_corpus_blob in project_raw_corpus_blobs:
            observed_raw_corpus_sha256 = hashlib.sha256(raw_corpus_blob.raw_corpus_blob or b"").hexdigest()
            expected_raw_corpus_sha256 = str(raw_corpus_blob.blob_sha256)
            if observed_raw_corpus_sha256 != expected_raw_corpus_sha256:
                raw_corpus_mismatches.append(
                    {
                        "raw_corpus_blob_id": raw_corpus_blob.id,
                        "expected_sha256": expected_raw_corpus_sha256,
                        "observed_sha256": observed_raw_corpus_sha256,
                        "reason": "hash_mismatch",
                    }
                )

        _record_check(
            "project_raw_corpus_blobs",
            not raw_corpus_mismatches,
            {
                "observed_count": len(project_raw_corpus_blobs),
                "mismatch_count": len(raw_corpus_mismatches),
                "mismatches": raw_corpus_mismatches,
            },
        )

    return {
        "is_artifact_integrity_intact": all(check["passed"] for check in checks),
        "checks": checks,
    }


def _refresh_run_artifact_integrity_in_config(
    *,
    session: Session,
    run: Run,
) -> None:
    artifact_integrity = _build_run_artifact_integrity_report(
        session=session,
        run=run,
    )
    run_config = dict(run.config_json or {})
    if run_config.get("artifact_integrity") != artifact_integrity:
        run_config["artifact_integrity"] = artifact_integrity
        run.config_json = run_config
        session.add(run)
        session.commit()


def _emit_service_log(
    *,
    service: str,
    event: str,
    message: str,
    level: str = "info",
    project_id: int | None = None,
    run_id: int | None = None,
    correlation_id: str | None = None,
    metadata: dict[str, object] | None = None,
) -> None:
    from app.services.structured_logging import emit_structured_log

    emit_structured_log(
        service=service,
        event=event,
        message=message,
        level=level,
        project_id=project_id,
        run_id=run_id,
        correlation_id=correlation_id,
        metadata=metadata,
    )


def _execute_pipeline_and_finalize_run(
    session: Session,
    project: Project,
    run: Run,
    principal_type: str | None = None,
    principal_id: str | None = None,
) -> int:
    run_config = dict(run.config_json or {})
    correlation_id = _resolve_correlation_id_from_run_config(run_config)
    _emit_service_log(
        service="pipeline_execution",
        event="pipeline_execution_started",
        message="Pipeline execution started",
        project_id=project.id,
        run_id=run.id,
        correlation_id=correlation_id,
        metadata={
            "mode": str(run_config.get("mode", DEFAULT_MODE)),
            "principal_type": principal_type or "system",
            "principal_id": principal_id or "",
        },
    )
    lifecycle_actor = _resolve_project_activity_actor(
        principal_type=principal_type,
        principal_id=principal_id,
    )
    try:
        result = execute_pipeline(
            session=session,
            project=project,
            run=run,
            run_config=run_config,
            principal_type=principal_type,
            principal_id=principal_id,
            project_id=project.id,
        )
        if run.status != RUN_STATUS_COMPLETED:
            run.status = RUN_STATUS_COMPLETED
        if run.finished_at is None:
            run.finished_at = datetime.now(timezone.utc)
        _transition_project_lifecycle_state(
            project,
            PROJECT_LIFECYCLE_COMPLETED,
            session=session,
            actor=lifecycle_actor,
        )
        session.add(project)

        time_series_snapshot = _persist_time_series_snapshot(
            session=session,
            project_id=project.id,
            source="run_capture",
            run=run,
            time_series=result["export"]["time_series"] if isinstance(result, Mapping) else {},
        )
        session.add(time_series_snapshot)
        session.flush()
        _append_run_changelog_entry(
            session=session,
            run=run,
            event_type="time_series_snapshot_created",
            event_message="Time series snapshot created",
            event_metadata={
                "snapshot_id": time_series_snapshot.id,
                "snapshot_version": time_series_snapshot.version,
                "source": time_series_snapshot.source,
            },
        )
        run_config_with_snapshot = dict(run.config_json or {})
        run_config_with_snapshot["time_series_snapshot_id"] = time_series_snapshot.id
        run_config_with_snapshot["time_series_snapshot_version"] = time_series_snapshot.version
        run.config_json = run_config_with_snapshot
        _set_pipeline_recovery_state(run, session=session, status="completed")
        session.add(run)
        _append_run_changelog_entry(
            session=session,
            run=run,
            event_type="pipeline_completed",
            event_message="Pipeline completed",
            event_metadata={"segment_count": int(result["segment_count"])},
        )
        artifact_integrity_report = _build_run_artifact_integrity_report(session=session, run=run)
        run_config_with_snapshot = dict(run.config_json or {})
        run_config_with_snapshot["artifact_integrity"] = artifact_integrity_report
        run.config_json = run_config_with_snapshot
        session.add(run)
        if not bool(artifact_integrity_report.get("is_artifact_integrity_intact")):
            raise PipelineError(
                "artifact integrity check failed after pipeline completion",
                metadata={"artifact_integrity": artifact_integrity_report},
            )
        _append_project_activity_event(
            session=session,
            project_id=project.id,
            run_id=run.id,
            event_type="run_complete",
            actor=lifecycle_actor,
            event_metadata={
                "status": run.status,
                "segment_count": int(result["segment_count"]),
            },
        )
        session.commit()
        _emit_service_log(
            service="pipeline_execution",
            event="pipeline_execution_completed",
            message="Pipeline execution completed",
            project_id=project.id,
            run_id=run.id,
            correlation_id=correlation_id,
            metadata={
                "segment_count": int(result["segment_count"]),
                "status": run.status,
            },
        )
        return int(result["segment_count"])
    except PipelineError as exc:
        session.rollback()
        run = _get_run_or_404(session, project.id, run.id)
        project = _get_project_or_404(session, project.id)
        run.status = RUN_STATUS_FAILED
        run.finished_at = datetime.now(timezone.utc)
        _transition_project_lifecycle_state(
            project,
            PROJECT_LIFECYCLE_FAILED,
            session=session,
            actor=lifecycle_actor,
        )
        error_metadata = {"reason": str(exc)}
        if isinstance(exc, Exception) and getattr(exc, "metadata", None):
            error_metadata["metadata"] = dict(exc.metadata)
        _set_pipeline_recovery_state(run, session=session, status="failed", metadata=error_metadata)
        _append_run_changelog_entry(
            session=session,
            run=run,
            event_type="pipeline_failed",
            event_message="Pipeline error",
            event_metadata=error_metadata,
        )
        _append_project_activity_event(
            session=session,
            project_id=project.id,
            run_id=run.id,
            event_type="run_complete",
            actor=lifecycle_actor,
            event_metadata={
                "status": run.status,
                "reason": str(error_metadata.get("reason", "pipeline_error")),
            },
        )
        session.add(run)
        session.add(project)
        session.commit()
        _emit_service_log(
            service="pipeline_execution",
            event="pipeline_execution_failed",
            message="Pipeline execution failed with pipeline error",
            level="error",
            project_id=project.id,
            run_id=run.id,
            correlation_id=correlation_id,
            metadata=error_metadata,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        run = _get_run_or_404(session, project.id, run.id)
        project = _get_project_or_404(session, project.id)
        run.status = RUN_STATUS_FAILED
        run.finished_at = datetime.now(timezone.utc)
        _transition_project_lifecycle_state(
            project,
            PROJECT_LIFECYCLE_FAILED,
            session=session,
            actor=lifecycle_actor,
        )
        _set_pipeline_recovery_state(run, session=session, status="failed", metadata={"reason": "unhandled_exception"})
        _append_run_changelog_entry(
            session=session,
            run=run,
            event_type="pipeline_failed",
            event_message="Pipeline execution failed",
            event_metadata={"reason": "unhandled_exception"},
        )
        _append_project_activity_event(
            session=session,
            project_id=project.id,
            run_id=run.id,
            event_type="run_complete",
            actor=lifecycle_actor,
            event_metadata={
                "status": run.status,
                "reason": "unhandled_exception",
            },
        )
        session.add(run)
        session.add(project)
        session.commit()
        _emit_service_log(
            service="pipeline_execution",
            event="pipeline_execution_failed",
            message="Pipeline execution failed with unhandled exception",
            level="error",
            project_id=project.id,
            run_id=run.id,
            correlation_id=correlation_id,
            metadata={
                "reason": "unhandled_exception",
                "error_type": exc.__class__.__name__,
                "error_message": str(exc),
            },
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Pipeline failed") from exc
@app.post(
    "/api/projects/{project_id}/characters/infer",
    response_model=CharacterMapResponse,
    status_code=status.HTTP_200_OK,
)
def persist_inferred_gender_fields(
    project_id: int,
    session: Session = Depends(get_session),
) -> CharacterMapResponse:
    project = _get_project_or_404(session, project_id)

    character_rows = (
        session.query(Character)
        .filter(Character.project_id == project_id)
        .order_by(Character.name.asc())
        .all()
    )
    if not character_rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No character map entries found to infer.",
        )

    chapter_rows = (
        session.query(Chapter.normalized_text)
        .filter(Chapter.project_id == project_id)
        .order_by(Chapter.chapter_index.asc())
        .all()
    )
    if not chapter_rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No chapters available for character gender inference.",
        )

    inferred_lookup = _build_inferred_gender_lookup(character_rows, [row[0] for row in chapter_rows])
    for row in character_rows:
        match = inferred_lookup.get(normalize_candidate_key(row.name))
        if match is None:
            row.inferred_gender = "unknown"
            row.inferred_confidence = 0.0
            row.inferred_source_trace = []
            continue
        row.inferred_gender = str(match["inferred_gender"])
        row.inferred_confidence = float(match["confidence"])
        row.inferred_source_trace = match["evidence"]

    session.add_all(character_rows)
    session.add(
        _persist_character_map_snapshot(
            session=session,
            project_id=project_id,
            source="inferred_gender",
        )
    )
    session.commit()

    return CharacterMapResponse(
        project_id=project_id,
        character_map_finalized=project.character_map_finalized,
        characters=[
            _build_character_map_item_payload_from_row(row)
            for row in character_rows
        ],
    )


@app.get(
    "/api/projects/{project_id}/access",
    response_model=ProjectAccessListResponse,
    status_code=status.HTTP_200_OK,
)
def list_project_access_controls(
    project_id: int,
    session: Session = Depends(get_session),
) -> ProjectAccessListResponse:
    project = _get_project_or_404(session, project_id)
    project_access = (
        session.query(ProjectAccess)
        .filter(ProjectAccess.project_id == project.id)
        .order_by(ProjectAccess.created_at.asc(), ProjectAccess.id.asc())
        .all()
    )

    return ProjectAccessListResponse(
        project_id=project.id,
        grants=[
            ProjectAccessGrantResponse(
                id=entry.id,
                project_id=project.id,
                principal_type=entry.principal_type,
                principal_id=entry.principal_id,
                role=entry.role,
                created_at=entry.created_at,
            )
            for entry in project_access
        ],
    )


@app.post(
    "/api/projects/{project_id}/access",
    response_model=ProjectAccessGrantResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_project_access_control(
    project_id: int,
    payload: ProjectAccessGrantRequest,
    session: Session = Depends(get_session),
) -> ProjectAccessGrantResponse:
    project = _get_project_or_404(session, project_id)

    grant = (
        session.query(ProjectAccess)
        .filter(
            ProjectAccess.project_id == project.id,
            ProjectAccess.principal_type == payload.principal_type,
            ProjectAccess.principal_id == payload.principal_id,
        )
        .one_or_none()
    )

    if grant is None:
        grant = ProjectAccess(
            project_id=project.id,
            principal_type=payload.principal_type,
            principal_id=payload.principal_id,
            role=payload.role,
        )
    else:
        grant.role = payload.role

    session.add(grant)
    session.commit()
    session.refresh(grant)

    return ProjectAccessGrantResponse(
        id=grant.id,
        project_id=project.id,
        principal_type=grant.principal_type,
        principal_id=grant.principal_id,
        role=grant.role,
        created_at=grant.created_at,
    )


@app.get(
    "/api/projects/{project_id}/characters/gender-comparison",
    response_model=CharacterGenderComparisonResponse,
    status_code=status.HTTP_200_OK,
)
def compare_character_genders(
    project_id: int,
    include_only_conflicts: bool = False,
    session: Session = Depends(get_session),
) -> CharacterGenderComparisonResponse:
    project = _get_project_or_404(session, project_id)
    settings = get_settings()
    profile = load_mode_profile(project.selected_mode)
    contradiction_review_required = bool(profile.get("contradiction_review_required", True))

    character_rows = (
        session.query(Character)
        .filter(Character.project_id == project_id)
        .order_by(Character.name.asc())
        .all()
    )

    comparison_payloads = [
        CharacterGenderComparisonItem(**payload)
        for payload in compare_manual_and_inferred_gender_fields(
            character_rows,
            include_only_conflicts=include_only_conflicts,
            contradiction_review_required=contradiction_review_required,
            contradiction_review_threshold=settings.contradiction_review_threshold,
        )
    ]
    warning_payloads = build_manual_inferred_gender_contradiction_warnings(
        character_rows,
        source="characters.gender-comparison",
        contradiction_review_required=contradiction_review_required,
        contradiction_review_threshold=settings.contradiction_review_threshold,
    )
    warning_payloads.extend(
        build_insufficient_inference_evidence_warnings(
            character_rows,
            source="characters.gender-comparison",
        )
    )

    contradiction_count = len([payload for payload in comparison_payloads if payload.is_contradiction])

    return CharacterGenderComparisonResponse(
        project_id=project_id,
        comparison_count=len(comparison_payloads),
        contradiction_count=contradiction_count,
        comparisons=comparison_payloads,
        warnings=warning_payloads,
    )


@app.post(
    "/api/comparison-workspaces",
    response_model=ComparisonWorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_comparison_workspace(
    payload: ComparisonWorkspaceCreateRequest,
    session: Session = Depends(get_session),
) -> ComparisonWorkspaceResponse:
    workspace = ComparisonWorkspace(
        name=payload.name.strip(),
        description=(payload.description.strip() if payload.description else None),
    )
    session.add(workspace)
    session.commit()
    session.refresh(workspace)
    return _build_comparison_workspace_response(session=session, workspace=workspace)


@app.get(
    "/api/comparison-workspaces/{workspace_id}",
    response_model=ComparisonWorkspaceResponse,
    status_code=status.HTTP_200_OK,
)
def get_comparison_workspace(
    workspace_id: int,
    session: Session = Depends(get_session),
) -> ComparisonWorkspaceResponse:
    workspace = _get_comparison_workspace_or_404(session, workspace_id)
    return _build_comparison_workspace_response(session=session, workspace=workspace)


@app.post(
    "/api/comparison-workspaces/{workspace_id}/runs",
    response_model=ComparisonWorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_run_to_comparison_workspace(
    workspace_id: int,
    payload: ComparisonWorkspaceRunLinkRequest,
    session: Session = Depends(get_session),
) -> ComparisonWorkspaceResponse:
    _get_comparison_workspace_or_404(session, workspace_id)
    _get_project_or_404(session, payload.project_id)
    run = session.query(Run).filter(Run.id == payload.run_id, Run.project_id == payload.project_id).one_or_none()
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found for the selected project.",
        )

    existing = (
        session.query(ComparisonWorkspaceRun)
        .filter(
            ComparisonWorkspaceRun.workspace_id == workspace_id,
            ComparisonWorkspaceRun.run_id == payload.run_id,
        )
        .one_or_none()
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Run already assigned to this comparison workspace.",
        )

    session.add(
        ComparisonWorkspaceRun(
            workspace_id=workspace_id,
            project_id=payload.project_id,
            run_id=run.id,
        )
    )
    session.commit()
    workspace = _get_comparison_workspace_or_404(session, workspace_id)
    return _build_comparison_workspace_response(session=session, workspace=workspace)


@app.get(
    "/api/comparison-workspaces/{workspace_id}/aligned-curves",
    response_model=ComparisonWorkspaceAlignedCurvesResponse,
    status_code=status.HTTP_200_OK,
)
def get_aligned_comparison_curves(
    workspace_id: int,
    metrics: str | None = None,
    aligned_points: int = 32,
    session: Session = Depends(get_session),
) -> ComparisonWorkspaceAlignedCurvesResponse:
    if aligned_points < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="aligned_points must be at least 2",
        )
    if aligned_points > 400:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="aligned_points must be 400 or fewer",
        )

    workspace = _get_comparison_workspace_or_404(session, workspace_id)
    selected_metric_ids = _resolve_aligned_curve_metric_ids(metrics)
    workspace_runs = _load_workspace_runs_for_comparison(session=session, workspace=workspace)
    metric_payloads = _build_workspace_aligned_curve_payloads(
        session=session,
        workspace_runs=workspace_runs,
        selected_metric_ids=selected_metric_ids,
        aligned_points=aligned_points,
    )

    return ComparisonWorkspaceAlignedCurvesResponse(
        workspace_id=workspace.id,
        workspace_name=workspace.name,
        run_count=len(workspace_runs),
        aligned_points=aligned_points,
        metrics=metric_payloads,
    )


@app.get(
    "/api/comparison-workspaces/{workspace_id}/exports/comparative-dataset.json",
    response_model=ComparisonWorkspaceComparativeExportResponse,
    status_code=status.HTTP_200_OK,
)
def get_comparative_dataset_export(
    workspace_id: int,
    metrics: str | None = None,
    aligned_points: int = 32,
    session: Session = Depends(get_session),
) -> ComparisonWorkspaceComparativeExportResponse:
    if aligned_points < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="aligned_points must be at least 2",
        )
    if aligned_points > 400:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="aligned_points must be 400 or fewer",
        )

    workspace = _get_comparison_workspace_or_404(session, workspace_id)
    selected_metric_ids = _resolve_aligned_curve_metric_ids(metrics)
    workspace_runs = _load_workspace_runs_for_comparison(session=session, workspace=workspace)
    metric_payloads = _build_workspace_aligned_curve_payloads(
        session=session,
        workspace_runs=workspace_runs,
        selected_metric_ids=selected_metric_ids,
        aligned_points=aligned_points,
    )
    run_records = _build_comparison_run_export_records(session=session, workspace_runs=workspace_runs)

    return ComparisonWorkspaceComparativeExportResponse(
        workspace_id=workspace.id,
        workspace_name=workspace.name,
        generated_at=datetime.now(timezone.utc).isoformat(),
        run_count=len(workspace_runs),
        aligned_points=aligned_points,
        metrics=metric_payloads,
        runs=run_records,
    )


def _build_mergeable_candidates_from_candidates(
    candidates: list[object],
    source: str,
) -> list[dict[str, object]]:
    payloads: list[dict[str, object]] = []

    def _normalize_trace(trace: object) -> dict[str, object] | None:
        if isinstance(trace, dict):
            kind = str(trace.get("kind", "")).strip()
            chapter_index = trace.get("chapter_index")
            span_start = trace.get("span_start")
            span_end = trace.get("span_end")
            excerpt = str(trace.get("excerpt", "")).strip()
            weight = trace.get("weight")
        else:
            kind = str(getattr(trace, "kind", "")).strip()
            chapter_index = getattr(trace, "chapter_index", None)
            span_start = getattr(trace, "span_start", None)
            span_end = getattr(trace, "span_end", None)
            excerpt = str(getattr(trace, "excerpt", "")).strip()
            weight = getattr(trace, "weight", None)

        if not kind or chapter_index is None or span_start is None or span_end is None or not excerpt:
            return None
        if not isinstance(weight, int | float):
            return None

        return {
            "kind": kind,
            "chapter_index": int(chapter_index),
            "span_start": int(span_start),
            "span_end": int(span_end),
            "excerpt": excerpt,
            "weight": float(weight),
        }

    for candidate in candidates:
        source_trace = [
            payload
            for payload in (
                _normalize_trace(trace)
                for trace in list(getattr(candidate, "source_trace", []))
            )
            if payload is not None
        ]
        inferred_gender = str(getattr(candidate, "inferred_gender", "unknown")).strip().lower() or "unknown"
        inferred_source_trace = [
            payload
            for payload in (
                _normalize_trace(trace)
                for trace in list(getattr(candidate, "inferred_source_trace", []))
            )
            if payload is not None
        ]
        payloads.append(
            {
                "name": candidate.name,
                "verbalized_form": getattr(candidate, "verbalized_form", candidate.name),
                "gender": getattr(candidate, "gender", "unknown"),
                "aliases": getattr(candidate, "aliases", []),
                "notes": getattr(candidate, "notes", None),
                "source": source,
                "confidence": getattr(candidate, "confidence", 1.0),
                "inferred_gender": inferred_gender,
                "inferred_confidence": getattr(candidate, "inferred_confidence", 0.0),
                "source_trace": source_trace,
                "inferred_source_trace": inferred_source_trace or source_trace,
            }
        )
    return payloads


def _character_lookup_payloads(session: Session, project_id: int) -> list[dict[str, object]]:
    rows = (
        session.query(Character)
        .filter(Character.project_id == project_id)
        .order_by(Character.name.asc())
        .all()
    )
    return [{"name": row.name, "aliases": row.aliases or []} for row in rows]


def _filter_new_character_payloads(
    payloads: list[dict[str, object]],
    canonical_name_keys: set[str],
) -> list[dict[str, object]]:
    filtered_payloads: list[dict[str, object]] = []
    for payload in payloads:
        candidate_name = str(payload.get("name") or "").strip()
        if not candidate_name:
            continue
        normalized_name = normalize_candidate_key(candidate_name)
        if normalized_name in canonical_name_keys:
            continue
        filtered_payloads.append(payload)
    return merge_character_candidates(filtered_payloads)


@app.post(
    "/api/projects/{project_id}/characters/lookup-alias",
    response_model=CharacterAliasLookupResponse,
    status_code=status.HTTP_200_OK,
)
def lookup_character_canonical_by_alias(
    project_id: int,
    payload: CharacterAliasLookupRequest,
    session: Session = Depends(get_session),
) -> CharacterAliasLookupResponse:
    _get_project_or_404(session, project_id)

    canonical_payloads = _character_lookup_payloads(session, project_id)
    canonical_name, match_source = resolve_alias_to_canonical_name(payload.alias, canonical_payloads)

    return CharacterAliasLookupResponse(
        project_id=project_id,
        alias=payload.alias.strip(),
        canonical_name=canonical_name,
        match_source=match_source,
    )


@app.get(
    "/api/projects/{project_id}/characters/alias-collisions",
    response_model=CharacterAliasCollisionResponse,
    status_code=status.HTTP_200_OK,
)
def list_character_alias_collisions(
    project_id: int,
    session: Session = Depends(get_session),
) -> CharacterAliasCollisionResponse:
    _get_project_or_404(session, project_id)

    canonical_payloads = _character_lookup_payloads(session, project_id)
    collisions = detect_alias_conflicts(canonical_payloads)

    return CharacterAliasCollisionResponse(
        project_id=project_id,
        collisions=[CharacterAliasCollisionItem(**payload) for payload in collisions],
    )


def _build_ambiguous_alias_collision_warnings(
    canonical_payloads: list[dict[str, object]],
    source: str,
) -> list[dict[str, object]]:
    warnings = build_ambiguous_alias_collision_warnings(
        canonical_payloads,
        source=source,
    )
    return warnings


def _build_low_confidence_character_warnings(
    candidate_payloads: list[dict[str, object]],
    source: str,
) -> list[dict[str, object]]:
    warnings = build_low_confidence_extracted_character_warnings(
        candidate_payloads,
        source=source,
        confidence_threshold=CHARACTER_EXTRACTION_LOW_CONFIDENCE_THRESHOLD,
    )
    return warnings


def _build_character_extraction_warnings(
    canonical_payloads: list[dict[str, object]],
    candidate_payloads: list[dict[str, object]],
    source: str,
) -> list[dict[str, object]]:
    warnings = _build_ambiguous_alias_collision_warnings(
        canonical_payloads=canonical_payloads,
        source=source,
    )
    warnings.extend(
        _build_low_confidence_character_warnings(
            candidate_payloads=candidate_payloads,
            source=source,
        )
    )
    warnings.extend(
        build_duplicate_canonical_candidate_warnings(
            candidate_payloads=candidate_payloads,
            source=source,
        )
    )
    return warnings


def _coerce_api_key_candidates(raw_value: object) -> list[str]:
    if raw_value is None:
        return []
    if isinstance(raw_value, (list, tuple, set)):
        candidates = [str(item).strip() for item in raw_value]
        return [candidate for candidate in candidates if candidate]
    if isinstance(raw_value, str):
        candidates = [item.strip() for item in raw_value.split(",")]
        return [candidate for candidate in candidates if candidate]
    value = str(raw_value).strip()
    return [value] if value else []


def _collect_character_extraction_provider_configs(
    *,
    session: Session,
    project: Project,
) -> tuple[LLMProviderConfig, ...]:
    settings = get_settings()
    project_provider_config = dict(project.llm_provider_config_json or {})

    provider_configs: list[LLMProviderConfig] = []
    seen_config_keys: set[tuple[str, str, str, str]] = set()

    for provider_name in get_provider_priority_order(settings=settings):
        normalized_provider = str(provider_name).strip().lower()
        if not normalized_provider or not is_supported_provider(normalized_provider):
            continue
        if not is_provider_enabled(session=session, provider=normalized_provider):
            continue

        base_url, model_identifier, runtime_api_key = get_provider_runtime_settings(
            settings=settings,
            provider_name=normalized_provider,
        )
        override_config = project_provider_config.get(normalized_provider)
        if isinstance(override_config, Mapping):
            override_base_url = str(override_config.get("base_url") or "").strip()
            if override_base_url:
                base_url = override_base_url
            override_model_identifier = str(override_config.get("model") or "").strip()
            if override_model_identifier:
                model_identifier = override_model_identifier

        if not str(base_url).strip() or not str(model_identifier).strip():
            continue

        provider_api_keys = get_provider_api_keys(settings=settings, provider_name=normalized_provider)
        if isinstance(override_config, Mapping):
            override_api_keys = _coerce_api_key_candidates(override_config.get("api_keys"))
            if not override_api_keys:
                override_api_keys = _coerce_api_key_candidates(override_config.get("api_key"))
            if override_api_keys:
                provider_api_keys = override_api_keys
        if not provider_api_keys and runtime_api_key:
            provider_api_keys = [str(runtime_api_key).strip()]

        normalized_keys = list(dict.fromkeys(key for key in provider_api_keys if str(key).strip()))
        if not normalized_keys:
            continue

        for api_key in normalized_keys:
            dedupe_key = (normalized_provider, str(base_url).strip(), str(model_identifier).strip(), api_key)
            if dedupe_key in seen_config_keys:
                continue
            seen_config_keys.add(dedupe_key)
            provider_configs.append(
                LLMProviderConfig(
                    provider_name=normalized_provider,
                    base_url=str(base_url).strip(),
                    model_identifier=str(model_identifier).strip(),
                    api_key=api_key,
                )
            )

    return tuple(provider_configs)


def _split_text_for_character_extraction_chunks(text: str, max_chars: int) -> list[str]:
    normalized = str(text or "").strip()
    if not normalized:
        return []

    segments: list[str] = []
    cursor = 0
    total_length = len(normalized)
    while cursor < total_length:
        limit = min(total_length, cursor + max_chars)
        if limit < total_length:
            window = normalized[cursor:limit]
            candidate_offsets = [
                window.rfind("\n\n"),
                window.rfind(". "),
                window.rfind("! "),
                window.rfind("? "),
                window.rfind("; "),
                window.rfind(", "),
                window.rfind(" "),
            ]
            valid_offsets = [offset for offset in candidate_offsets if offset > max_chars // 4]
            split_offset = max(valid_offsets) if valid_offsets else -1
            if split_offset > 0:
                limit = cursor + split_offset + 1

        chunk = normalized[cursor:limit].strip()
        if chunk:
            segments.append(chunk)
        cursor = max(limit, cursor + 1)

    return segments


def _build_llm_character_extraction_chunks(
    *,
    chapter_rows: list[tuple[int, str]],
    chunk_max_chars: int,
    max_chunks: int,
) -> list[dict[str, object]]:
    chunks: list[dict[str, object]] = []
    chunk_parts: list[str] = []
    chunk_chapter_indices: list[int] = []
    chunk_size = 0

    def _flush_chunk() -> None:
        nonlocal chunk_parts, chunk_chapter_indices, chunk_size
        if not chunk_parts or len(chunks) >= max_chunks:
            chunk_parts = []
            chunk_chapter_indices = []
            chunk_size = 0
            return

        ordered_indices = sorted(set(chunk_chapter_indices))
        chunks.append(
            {
                "chunk_index": len(chunks) + 1,
                "text": "\n\n".join(chunk_parts).strip(),
                "chapter_indices": ordered_indices,
            }
        )
        chunk_parts = []
        chunk_chapter_indices = []
        chunk_size = 0

    for chapter_index, chapter_text in chapter_rows:
        if len(chunks) >= max_chunks:
            break

        segments = _split_text_for_character_extraction_chunks(
            chapter_text,
            max_chars=max(chunk_max_chars // 2, 1200),
        )
        if not segments:
            continue

        for segment in segments:
            chunk_fragment = f"[Chapter {int(chapter_index)}]\n{segment}"
            fragment_size = len(chunk_fragment)
            if chunk_parts and chunk_size + fragment_size > chunk_max_chars:
                _flush_chunk()
                if len(chunks) >= max_chunks:
                    break

            chunk_parts.append(chunk_fragment)
            chunk_chapter_indices.append(int(chapter_index))
            chunk_size += fragment_size + 2

        if len(chunks) >= max_chunks:
            break

    if len(chunks) < max_chunks:
        _flush_chunk()

    return chunks[:max_chunks]


def _clamp_confidence(value: object, *, fallback: float = 0.0) -> float:
    if isinstance(value, bool):
        return fallback
    if not isinstance(value, (int, float)):
        return fallback
    return max(0.0, min(float(value), 1.0))


def _normalize_llm_character_name(raw_name: object) -> str | None:
    name = str(raw_name or "").strip()
    if not name:
        return None
    name = re.sub(r"\s+", " ", name).strip(" \"'`[](){}:;,.!?")
    if not name:
        return None
    if len(name) < CHARACTER_EXTRACTION_LLM_MIN_VALID_NAME_LENGTH:
        return None
    if len(name) > CHARACTER_EXTRACTION_LLM_MAX_VALID_NAME_LENGTH:
        return None
    if not re.search(r"[A-Za-z]", name):
        return None

    normalized_lower = name.lower()
    rejected_single_tokens = {
        "name",
        "rank",
        "aspect",
        "attribute",
        "attributes",
        "ability",
        "abilities",
        "description",
        "chapter",
        "section",
        "status",
        "system",
    }
    if " " not in normalized_lower and normalized_lower in rejected_single_tokens:
        return None

    return name


def _normalize_llm_aliases(raw_aliases: object, *, canonical_name: str) -> list[str]:
    if not isinstance(raw_aliases, list):
        return []
    aliases: list[str] = []
    for alias in raw_aliases:
        normalized = _normalize_llm_character_name(alias)
        if normalized is None:
            continue
        if normalize_candidate_key(normalized) == normalize_candidate_key(canonical_name):
            continue
        aliases.append(normalized)
    return list(dict.fromkeys(aliases))


def _build_source_trace_excerpt(text: str, *, start: int, end: int) -> str:
    safe_start = max(0, min(start, len(text)))
    safe_end = max(safe_start, min(end, len(text)))
    left = max(0, safe_start - 90)
    right = min(len(text), safe_end + 90)
    excerpt = text[left:right].replace("\n", " ").strip()
    return excerpt[:380] if excerpt else text[:380].replace("\n", " ").strip()


def _locate_candidate_in_chapter_text(
    *,
    candidate_name: str,
    evidence_excerpt: str,
    chapter_indices_hint: list[int],
    chapter_text_by_index: dict[int, str],
) -> tuple[int, int, int, str]:
    normalized_evidence = evidence_excerpt.strip()
    normalized_candidate = candidate_name.strip()

    ordered_chapter_indices: list[int] = []
    for chapter_index in chapter_indices_hint:
        if chapter_index in chapter_text_by_index and chapter_index not in ordered_chapter_indices:
            ordered_chapter_indices.append(chapter_index)
    for chapter_index in sorted(chapter_text_by_index.keys()):
        if chapter_index not in ordered_chapter_indices:
            ordered_chapter_indices.append(chapter_index)

    if not ordered_chapter_indices:
        return (1, 0, max(1, len(normalized_candidate)), normalized_candidate[:380])

    name_pattern = re.escape(normalized_candidate).replace(r"\ ", r"\s+")
    name_regex = re.compile(rf"(?<!\w){name_pattern}(?!\w)", re.IGNORECASE)

    def _locate_in_text(chapter_text: str) -> tuple[int, int] | None:
        if normalized_evidence and len(normalized_evidence) >= CHARACTER_EXTRACTION_LLM_MIN_EXCERPT_LENGTH:
            start = chapter_text.lower().find(normalized_evidence.lower())
            if start >= 0:
                return (start, start + len(normalized_evidence))
        match = name_regex.search(chapter_text)
        if match is not None:
            return (match.start(), match.end())
        return None

    for chapter_index in ordered_chapter_indices:
        chapter_text = chapter_text_by_index.get(chapter_index, "")
        if not chapter_text:
            continue
        located = _locate_in_text(chapter_text)
        if located is None:
            continue
        start, end = located
        excerpt = _build_source_trace_excerpt(chapter_text, start=start, end=end)
        return (chapter_index, start, end, excerpt)

    fallback_chapter = ordered_chapter_indices[0]
    fallback_text = chapter_text_by_index.get(fallback_chapter, "")
    if not fallback_text:
        return (fallback_chapter, 0, max(1, len(normalized_candidate)), normalized_candidate[:380])

    fallback_excerpt = fallback_text[:380].replace("\n", " ").strip()
    return (fallback_chapter, 0, min(len(fallback_text), max(1, len(normalized_candidate))), fallback_excerpt)


def _build_llm_source_trace(
    *,
    candidate_name: str,
    evidence_excerpt: object,
    chapter_index_hint: object,
    chapter_indices_hint: list[int],
    chapter_text_by_index: dict[int, str],
    confidence: float,
    kind: str,
) -> dict[str, object]:
    if isinstance(chapter_index_hint, bool):
        chapter_index_value = None
    elif isinstance(chapter_index_hint, int | float):
        chapter_index_value = int(chapter_index_hint)
    elif isinstance(chapter_index_hint, str) and chapter_index_hint.strip().isdigit():
        chapter_index_value = int(chapter_index_hint.strip())
    else:
        chapter_index_value = None

    chapter_hints = [chapter_index_value] if chapter_index_value is not None else []
    chapter_hints.extend(chapter_indices_hint)
    chapter_hints = [hint for hint in chapter_hints if isinstance(hint, int) and hint >= 1]

    chapter_index, span_start, span_end, excerpt = _locate_candidate_in_chapter_text(
        candidate_name=candidate_name,
        evidence_excerpt=str(evidence_excerpt or ""),
        chapter_indices_hint=chapter_hints,
        chapter_text_by_index=chapter_text_by_index,
    )
    trace_weight = max(0.2, min(1.0, confidence))
    return {
        "kind": kind,
        "chapter_index": int(chapter_index),
        "span_start": int(span_start),
        "span_end": int(max(span_start, span_end)),
        "excerpt": excerpt,
        "weight": round(trace_weight, 4),
    }


def _extract_llm_character_items(parsed_output: dict[str, object]) -> list[dict[str, object]]:
    raw_items = parsed_output.get("characters")
    if not isinstance(raw_items, list):
        return []

    extracted: list[dict[str, object]] = []
    for item in raw_items:
        if isinstance(item, dict):
            extracted.append(dict(item))
        elif isinstance(item, str):
            extracted.append({"name": item})
    return extracted


def _run_llm_primary_character_extraction(
    *,
    project_id: int,
    chapter_rows: list[tuple[int, str]],
    provider_configs: tuple[LLMProviderConfig, ...],
    config: CharacterExtractionRequest,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    if not provider_configs:
        return ([], [])

    chapter_text_by_index = {
        int(chapter_index): str(chapter_text or "")
        for chapter_index, chapter_text in chapter_rows
        if str(chapter_text or "").strip()
    }
    chunks = _build_llm_character_extraction_chunks(
        chapter_rows=chapter_rows,
        chunk_max_chars=config.llm_chunk_max_chars,
        max_chunks=config.llm_max_chunks,
    )
    if not chunks:
        return ([], [])

    settings = get_settings()
    router = LLMRouter(openrouter_base_url=settings.openrouter_base_url)
    raw_candidate_payloads: list[dict[str, object]] = []

    for chunk in chunks:
        chunk_text = str(chunk.get("text") or "").strip()
        if not chunk_text:
            continue

        prompt = (
            "Extract human novel characters from this excerpt.\n"
            "Return strict JSON with keys:\n"
            "- characters: array of objects.\n"
            "- confidence: number between 0 and 1.\n"
            "Each character object keys:\n"
            "- name: string (canonical if known).\n"
            "- aliases: array of strings.\n"
            "- confidence: number between 0 and 1.\n"
            "- chapter_index: integer chapter index from markers.\n"
            "- evidence: short quote from the text.\n"
            "Rules:\n"
            "- Include only people/characters (named individuals).\n"
            "- Exclude places, institutions, powers, items, skills, ranks, field labels.\n"
            "- Keep names concise and exact.\n\n"
            f"TEXT:\n{chunk_text}"
        )
        request = LLMRequest(
            request_id=str(uuid4()),
            project_id=project_id,
            task_type="character_extraction",
            input_text=prompt,
            expected_schema={
                "characters": "array",
                "confidence": "number",
            },
            configuration_snapshot_id=f"character-extraction-{project_id}",
            max_tokens=800,
        )
        response = router.call_with_failover(
            request=request,
            provider_configs=provider_configs,
        )
        if not response.success_flag:
            continue
        parsed_output = response.parsed_output if isinstance(response.parsed_output, dict) else {}
        llm_items = _extract_llm_character_items(parsed_output)
        chunk_indices = [int(value) for value in list(chunk.get("chapter_indices") or []) if isinstance(value, int)]
        for item in llm_items:
            candidate_name = _normalize_llm_character_name(
                item.get("name") or item.get("canonical_name") or item.get("character_name")
            )
            if candidate_name is None:
                continue

            candidate_confidence = _clamp_confidence(
                item.get("confidence"),
                fallback=max(0.45, _clamp_confidence(parsed_output.get("confidence"), fallback=0.55)),
            )
            aliases = _normalize_llm_aliases(item.get("aliases"), canonical_name=candidate_name)
            source_trace = _build_llm_source_trace(
                candidate_name=candidate_name,
                evidence_excerpt=item.get("evidence") or item.get("excerpt") or item.get("reason"),
                chapter_index_hint=item.get("chapter_index"),
                chapter_indices_hint=chunk_indices,
                chapter_text_by_index=chapter_text_by_index,
                confidence=candidate_confidence,
                kind="llm_extraction",
            )
            raw_candidate_payloads.append(
                {
                    "name": candidate_name,
                    "verbalized_form": candidate_name,
                    "gender": "unknown",
                    "aliases": aliases,
                    "notes": None,
                    "source": "auto",
                    "confidence": round(candidate_confidence, 4),
                    "inferred_gender": "unknown",
                    "inferred_confidence": 0.0,
                    "inferred_source_trace": [],
                    "source_trace": [source_trace],
                }
            )

    if not raw_candidate_payloads:
        return ([], [])

    return (raw_candidate_payloads, merge_character_candidates(raw_candidate_payloads))


def _build_llm_verification_trace(
    *,
    payload: dict[str, object],
    verification_reason: str,
    verification_confidence: float,
) -> dict[str, object]:
    source_trace = list(payload.get("source_trace") or [])
    if source_trace and isinstance(source_trace[0], dict):
        base_trace = source_trace[0]
        chapter_index = int(base_trace.get("chapter_index") or 1)
        span_start = int(base_trace.get("span_start") or 0)
        span_end = int(base_trace.get("span_end") or span_start)
        base_excerpt = str(base_trace.get("excerpt") or "").strip()
    else:
        chapter_index = 1
        span_start = 0
        span_end = max(1, len(str(payload.get("name") or "")))
        base_excerpt = str(payload.get("name") or "").strip()

    reason_excerpt = verification_reason.strip()
    if reason_excerpt:
        excerpt = f"{base_excerpt} | verify: {reason_excerpt}"[:380]
    else:
        excerpt = base_excerpt[:380]

    return {
        "kind": "llm_verification",
        "chapter_index": max(1, chapter_index),
        "span_start": max(0, span_start),
        "span_end": max(max(0, span_start), span_end),
        "excerpt": excerpt or str(payload.get("name") or "")[:380],
        "weight": round(max(0.2, min(1.0, verification_confidence)), 4),
    }


def _run_llm_character_verification(
    *,
    project_id: int,
    payloads: list[dict[str, object]],
    provider_configs: tuple[LLMProviderConfig, ...],
    batch_size: int,
) -> list[dict[str, object]]:
    if not payloads or not provider_configs:
        return payloads

    settings = get_settings()
    router = LLMRouter(openrouter_base_url=settings.openrouter_base_url)
    sorted_payloads = sorted(
        [dict(payload) for payload in payloads],
        key=lambda payload: (-float(payload.get("confidence", 0.0)), str(payload.get("name", "")).lower()),
    )
    verified_payloads: list[dict[str, object]] = []

    for index in range(0, len(sorted_payloads), batch_size):
        batch = sorted_payloads[index : index + batch_size]
        if not batch:
            continue

        candidate_lines: list[str] = []
        for item_index, payload in enumerate(batch, start=1):
            source_trace = list(payload.get("source_trace") or [])
            evidence_excerpt = ""
            chapter_index = None
            if source_trace and isinstance(source_trace[0], dict):
                evidence_excerpt = str(source_trace[0].get("excerpt") or "").strip()
                chapter_index = source_trace[0].get("chapter_index")
            candidate_lines.append(
                f"{item_index}. name={str(payload.get('name') or '').strip()} | "
                f"confidence={float(payload.get('confidence') or 0.0):.2f} | "
                f"chapter={chapter_index} | evidence={evidence_excerpt}"
            )

        prompt = (
            "Validate whether each candidate is a human character in a novel.\n"
            "Return strict JSON with keys:\n"
            "- results: array of objects.\n"
            "- confidence: number between 0 and 1.\n"
            "Each result object keys:\n"
            "- name: string (must match one candidate name).\n"
            "- is_character: boolean.\n"
            "- canonical_name: string.\n"
            "- aliases: array of strings.\n"
            "- confidence: number between 0 and 1.\n"
            "- reason: short string.\n"
            "Reject places, organizations, items, powers, stats, and field labels.\n\n"
            "CANDIDATES:\n"
            + "\n".join(candidate_lines)
        )
        request = LLMRequest(
            request_id=str(uuid4()),
            project_id=project_id,
            task_type="character_extraction",
            input_text=prompt,
            expected_schema={
                "results": "array",
                "confidence": "number",
            },
            configuration_snapshot_id=f"character-extraction-verify-{project_id}",
            max_tokens=600,
        )
        response = router.call_with_failover(
            request=request,
            provider_configs=provider_configs,
        )
        if not response.success_flag:
            verified_payloads.extend(batch)
            continue

        parsed_output = response.parsed_output if isinstance(response.parsed_output, dict) else {}
        raw_results = parsed_output.get("results")
        if not isinstance(raw_results, list):
            verified_payloads.extend(batch)
            continue

        verdict_by_name: dict[str, dict[str, object]] = {}
        for raw_verdict in raw_results:
            if not isinstance(raw_verdict, dict):
                continue
            verdict_name = _normalize_llm_character_name(raw_verdict.get("name"))
            if verdict_name is None:
                continue
            verdict_by_name[normalize_candidate_key(verdict_name)] = raw_verdict

        for payload in batch:
            payload_name = _normalize_llm_character_name(payload.get("name"))
            if payload_name is None:
                continue

            verdict = verdict_by_name.get(normalize_candidate_key(payload_name))
            if verdict is None:
                verified_payloads.append(payload)
                continue

            is_character = bool(verdict.get("is_character", True))
            verdict_confidence = _clamp_confidence(
                verdict.get("confidence"),
                fallback=float(payload.get("confidence") or 0.0),
            )
            if not is_character:
                continue

            canonical_name = _normalize_llm_character_name(verdict.get("canonical_name")) or payload_name
            updated_payload = dict(payload)
            if normalize_candidate_key(canonical_name) != normalize_candidate_key(payload_name):
                aliases = list(updated_payload.get("aliases") or [])
                aliases.append(payload_name)
                updated_payload["name"] = canonical_name
                updated_payload["verbalized_form"] = canonical_name
                updated_payload["aliases"] = list(dict.fromkeys(aliases))

            llm_aliases = _normalize_llm_aliases(verdict.get("aliases"), canonical_name=canonical_name)
            if llm_aliases:
                aliases = list(updated_payload.get("aliases") or [])
                aliases.extend(llm_aliases)
                updated_payload["aliases"] = list(dict.fromkeys(aliases))

            current_confidence = _clamp_confidence(updated_payload.get("confidence"), fallback=0.0)
            bounded_delta = max(-0.2, min(0.25, verdict_confidence - current_confidence))
            updated_payload["confidence"] = round(max(0.0, min(1.0, current_confidence + bounded_delta)), 4)

            verification_trace = _build_llm_verification_trace(
                payload=updated_payload,
                verification_reason=str(verdict.get("reason") or ""),
                verification_confidence=verdict_confidence,
            )
            updated_source_trace = list(updated_payload.get("source_trace") or [])
            updated_source_trace.append(verification_trace)
            updated_payload["source_trace"] = updated_source_trace
            verified_payloads.append(updated_payload)

    return verified_payloads


def _consolidate_character_extraction_payloads(
    *,
    payloads: list[dict[str, object]],
    min_confidence: float,
    max_candidates: int,
) -> list[dict[str, object]]:
    if not payloads:
        return []

    merged_payloads = merge_character_candidates(payloads)
    scored_payloads: list[tuple[dict[str, object], float, int, int]] = []

    for payload in merged_payloads:
        candidate_name = _normalize_llm_character_name(payload.get("name"))
        if candidate_name is None:
            continue

        normalized_payload = dict(payload)
        normalized_payload["name"] = candidate_name
        normalized_payload["verbalized_form"] = (
            _normalize_llm_character_name(payload.get("verbalized_form")) or candidate_name
        )
        normalized_payload["aliases"] = _normalize_llm_aliases(
            list(payload.get("aliases") or []),
            canonical_name=candidate_name,
        )

        source_trace = [
            trace
            for trace in list(normalized_payload.get("source_trace") or [])
            if isinstance(trace, dict) and str(trace.get("excerpt") or "").strip()
        ]
        source_trace = sorted(
            source_trace,
            key=lambda trace: (
                -_clamp_confidence(trace.get("weight"), fallback=0.0),
                int(trace.get("chapter_index") or 0),
                int(trace.get("span_start") or 0),
            ),
        )[:CHARACTER_EXTRACTION_LLM_TRACE_LIMIT]
        normalized_payload["source_trace"] = source_trace

        mention_count = len(source_trace)
        chapter_spread = len({int(trace.get("chapter_index") or 0) for trace in source_trace if int(trace.get("chapter_index") or 0) > 0})
        avg_weight = (
            sum(_clamp_confidence(trace.get("weight"), fallback=0.0) for trace in source_trace) / mention_count
            if mention_count > 0
            else 0.0
        )
        base_confidence = _clamp_confidence(normalized_payload.get("confidence"), fallback=0.0)
        alias_count = len(list(normalized_payload.get("aliases") or []))
        mention_feature = min(1.0, mention_count / 6.0)
        spread_feature = min(1.0, chapter_spread / 4.0)
        alias_feature = min(1.0, alias_count / 4.0)
        scored_confidence = (
            (0.35 * base_confidence)
            + (0.30 * mention_feature)
            + (0.20 * spread_feature)
            + (0.10 * avg_weight)
            + (0.05 * alias_feature)
        )
        normalized_payload["confidence"] = round(max(0.0, min(1.0, scored_confidence)), 4)
        if float(normalized_payload["confidence"]) < min_confidence:
            continue

        scored_payloads.append((normalized_payload, float(normalized_payload["confidence"]), mention_count, chapter_spread))

    scored_payloads.sort(
        key=lambda row: (
            -row[1],
            -row[2],
            -row[3],
            str(row[0].get("name") or "").lower(),
        )
    )
    return [row[0] for row in scored_payloads[:max_candidates]]


def _extract_character_candidates_llm_first(
    *,
    session: Session,
    project: Project,
    project_id: int,
    chapter_rows: list[tuple[int, str]],
    existing_name_keys: set[str],
    config: CharacterExtractionRequest,
) -> tuple[list[dict[str, object]], list[dict[str, object]]] | None:
    if not config.llm_primary_extraction_enabled:
        return None

    provider_configs = _collect_character_extraction_provider_configs(
        session=session,
        project=project,
    )
    if not provider_configs:
        return None

    raw_llm_payloads, candidate_payloads = _run_llm_primary_character_extraction(
        project_id=project_id,
        chapter_rows=chapter_rows,
        provider_configs=provider_configs,
        config=config,
    )
    if not candidate_payloads:
        return None

    if config.llm_verification_enabled:
        candidate_payloads = _run_llm_character_verification(
            project_id=project_id,
            payloads=candidate_payloads,
            provider_configs=provider_configs,
            batch_size=config.llm_verification_batch_size,
        )

    consolidated_payloads = _consolidate_character_extraction_payloads(
        payloads=candidate_payloads,
        min_confidence=config.min_confidence,
        max_candidates=config.max_candidates,
    )
    if not consolidated_payloads:
        return None

    filtered_consolidated_payloads = [
        payload
        for payload in consolidated_payloads
        if normalize_candidate_key(str(payload.get("name") or "")) not in existing_name_keys
    ]
    filtered_raw_payloads = [
        payload
        for payload in raw_llm_payloads
        if normalize_candidate_key(str(payload.get("name") or "")) not in existing_name_keys
    ]
    return (filtered_raw_payloads, filtered_consolidated_payloads)


def _resolve_character_extraction_api_key() -> str | None:
    settings = get_settings()
    if settings.openrouter_api_key:
        return settings.openrouter_api_key
    if settings.openrouter_api_keys:
        for key in settings.openrouter_api_keys:
            normalized_key = str(key).strip()
            if normalized_key:
                return normalized_key
    return None


def _refine_character_payloads_with_llm(
    *,
    project_id: int,
    payloads: list[dict[str, object]],
    config: CharacterExtractionRequest,
) -> list[dict[str, object]]:
    if not config.llm_refinement_enabled:
        return payloads

    settings = get_settings()
    provider_configs: list[LLMProviderConfig] = []
    for provider_name in get_provider_priority_order(settings=settings):
        normalized_provider = str(provider_name).strip().lower()
        if not normalized_provider or not is_supported_provider(normalized_provider):
            continue
        base_url, model_identifier, runtime_api_key = get_provider_runtime_settings(
            settings=settings,
            provider_name=normalized_provider,
        )
        if not str(base_url).strip() or not str(model_identifier).strip():
            continue
        api_keys = get_provider_api_keys(settings=settings, provider_name=normalized_provider)
        if not api_keys and runtime_api_key:
            api_keys = [str(runtime_api_key).strip()]
        if not api_keys:
            continue
        for api_key in api_keys:
            if not str(api_key).strip():
                continue
            provider_configs.append(
                LLMProviderConfig(
                    provider_name=normalized_provider,
                    base_url=str(base_url).strip(),
                    model_identifier=str(model_identifier).strip(),
                    api_key=str(api_key).strip(),
                )
            )
    if not provider_configs:
        return payloads

    router = LLMRouter(openrouter_base_url=settings.openrouter_base_url)
    refined_payloads = [dict(payload) for payload in payloads]
    candidates = sorted(
        [
            payload
            for payload in refined_payloads
            if config.llm_refinement_min_confidence <= float(payload.get("confidence", 0.0)) <= config.llm_refinement_max_confidence
        ],
        key=lambda payload: (-float(payload.get("confidence", 0.0)), str(payload.get("name", "")).lower()),
    )[: config.llm_refinement_max_candidates]

    for payload in candidates:
        candidate_name = str(payload.get("name") or "").strip()
        if not candidate_name:
            continue

        source_traces = list(payload.get("source_trace") or [])
        evidence_excerpt = ""
        if source_traces:
            first_trace = source_traces[0]
            if isinstance(first_trace, dict):
                evidence_excerpt = str(first_trace.get("excerpt") or "").strip()
        prompt = (
            f"Candidate name: {candidate_name}\n"
            f"Evidence excerpt: {evidence_excerpt}\n"
            "Return whether this is a character person/entity reference for a novel character map."
        )
        request = LLMRequest(
            request_id=str(uuid4()),
            project_id=project_id,
            task_type="character_extraction",
            input_text=prompt,
            expected_schema={
                "is_character": "boolean",
                "canonical_name": "string",
                "aliases": "array",
                "confidence": "number",
                "reason": "string",
            },
            configuration_snapshot_id=f"character-extraction-{project_id}",
            max_tokens=180,
        )
        response = router.call_with_failover(
            request=request,
            provider_configs=tuple(provider_configs),
        )
        if not response.success_flag:
            continue
        parsed_output = response.parsed_output
        if not isinstance(parsed_output, dict):
            continue

        current_confidence = float(payload.get("confidence") or 0.0)
        is_character = bool(parsed_output.get("is_character", True))
        if not is_character:
            payload["confidence"] = round(max(0.0, min(current_confidence, 0.2)), 4)
            continue

        llm_candidate_name = str(parsed_output.get("canonical_name") or "").strip()
        if llm_candidate_name and llm_candidate_name.lower() != candidate_name.lower():
            aliases = list(payload.get("aliases") or [])
            aliases.append(candidate_name)
            payload["name"] = llm_candidate_name
            payload["verbalized_form"] = llm_candidate_name
            payload["aliases"] = list(dict.fromkeys([alias.strip() for alias in aliases if str(alias).strip()]))

        llm_aliases = parsed_output.get("aliases")
        if isinstance(llm_aliases, list):
            aliases = list(payload.get("aliases") or [])
            aliases.extend([str(alias).strip() for alias in llm_aliases if str(alias).strip()])
            payload["aliases"] = list(dict.fromkeys(aliases))

        llm_confidence = parsed_output.get("confidence")
        if isinstance(llm_confidence, int | float):
            confidence_target = max(0.0, min(float(llm_confidence), 1.0))
            bounded_delta = max(-0.15, min(0.15, confidence_target - current_confidence))
            payload["confidence"] = round(max(0.0, min(1.0, current_confidence + bounded_delta)), 4)

    return refined_payloads


@app.post("/api/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, session: Session = Depends(get_session)) -> ProjectResponse:
    project = Project(
        title=payload.title.strip(),
        description=None,
        tags=[],
        lifecycle_state=PROJECT_LIFECYCLE_DRAFT,
        last_run_status=None,
        last_export_at=None,
        next_required_action="ingest",
        selected_mode=DEFAULT_MODE,
        selected_modes=[DEFAULT_MODE],
        llm_enabled=False,
        do_not_store_source_text=payload.do_not_store_source_text,
        voice_config_json=dict(DEFAULT_VOICE_CONFIG),
        default_narrator_voice=DEFAULT_VOICE_CONFIG["narrator_voice"],
        default_male_voice=DEFAULT_VOICE_CONFIG["male_default_voice"],
        default_female_voice=DEFAULT_VOICE_CONFIG["female_default_voice"],
        default_neutral_voice=DEFAULT_VOICE_CONFIG["neutral_default_voice"],
        default_unknown_voice=DEFAULT_VOICE_CONFIG["unknown_default_voice"],
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    project.configuration_snapshot_id = _build_initial_configuration_snapshot_id(project.id)
    session.add(project)
    session.commit()
    session.refresh(project)

    return ProjectResponse(
        id=project.id,
        title=project.title,
        selected_mode=project.selected_mode,
        selected_modes=project.selected_modes,
        llm_enabled=project.llm_enabled,
        do_not_store_source_text=project.do_not_store_source_text,
        character_map_finalized=project.character_map_finalized,
        configuration_snapshot_id=project.configuration_snapshot_id,
        ingestion_timestamp=project.ingestion_timestamp,
        created_at=project.created_at,
    )


@app.post("/api/projects/drafts", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project_draft(payload: ProjectCreate, session: Session = Depends(get_session)) -> ProjectResponse:
    return create_project(payload=payload, session=session)


def _build_project_detail_response(project: Project) -> ProjectDetailResponse:
    generated_at = datetime.now(timezone.utc).isoformat()
    normalized_lifecycle_state = str(project.lifecycle_state or PROJECT_LIFECYCLE_DRAFT).strip().lower()
    if normalized_lifecycle_state not in set(_CONTROL_PANEL_STATE_ORDER):
        normalized_lifecycle_state = PROJECT_LIFECYCLE_DRAFT

    normalized_last_run_status = (
        str(project.last_run_status).strip().lower()
        if project.last_run_status is not None
        else None
    )
    if normalized_last_run_status == "":
        normalized_last_run_status = None

    normalized_next_required_action = str(project.next_required_action or "").strip().lower()
    if normalized_next_required_action not in _CONTROL_PANEL_NEXT_REQUIRED_ACTION_VALUES:
        normalized_next_required_action = _resolve_project_control_panel_next_required_action(
            lifecycle_state=normalized_lifecycle_state,
            last_run_status=normalized_last_run_status,
        )

    updated_at_candidates = [
        project.created_at,
        project.ingestion_timestamp,
        project.last_export_at,
    ]
    updated_at = max(candidate for candidate in updated_at_candidates if candidate is not None)

    return ProjectDetailResponse(
        generated_at=generated_at,
        project_id=project.id,
        title=project.title,
        description=project.description,
        tags=list(project.tags or []),
        lifecycle_state=normalized_lifecycle_state,
        last_run_status=normalized_last_run_status,
        next_required_action=normalized_next_required_action,
        allowed_actions=_resolve_allowed_project_actions(
            lifecycle_state=normalized_lifecycle_state,
            last_run_status=normalized_last_run_status,
        ),
        selected_mode=str(project.selected_mode).strip().lower() or DEFAULT_MODE,
        selected_modes=[str(mode).strip().lower() for mode in list(project.selected_modes or []) if str(mode).strip()],
        llm_enabled=bool(project.llm_enabled),
        do_not_store_source_text=bool(project.do_not_store_source_text),
        character_map_finalized=bool(project.character_map_finalized),
        configuration_snapshot_id=project.configuration_snapshot_id,
        ingestion_timestamp=_serialize_datetime_to_utc_iso(project.ingestion_timestamp),
        last_export_at=_serialize_datetime_to_utc_iso(project.last_export_at),
        created_at=_serialize_datetime_to_utc_iso(project.created_at) or generated_at,
        updated_at=_serialize_datetime_to_utc_iso(updated_at) or generated_at,
    )


def _resolve_archived_project_restore_state(*, session: Session, project: Project) -> str:
    supported_restore_states = {
        PROJECT_LIFECYCLE_DRAFT,
        PROJECT_LIFECYCLE_INGESTED,
        PROJECT_LIFECYCLE_CONFIGURED,
        PROJECT_LIFECYCLE_COMPLETED,
        PROJECT_LIFECYCLE_FAILED,
    }

    log_json = dict(project.ingestion_log_json or {})
    archived_metadata = log_json.get(_PROJECT_ARCHIVE_METADATA_KEY)
    if isinstance(archived_metadata, dict):
        previous_state = str(archived_metadata.get("previous_lifecycle_state", "")).strip().lower()
        if previous_state in supported_restore_states:
            return previous_state

    chapter_count = session.query(Chapter).filter(Chapter.project_id == project.id).count()
    if chapter_count == 0:
        return PROJECT_LIFECYCLE_DRAFT

    normalized_last_run_status = (
        str(project.last_run_status).strip().lower()
        if project.last_run_status is not None
        else None
    )
    if normalized_last_run_status == RUN_STATUS_COMPLETED:
        return PROJECT_LIFECYCLE_COMPLETED
    if normalized_last_run_status == RUN_STATUS_FAILED:
        return PROJECT_LIFECYCLE_FAILED
    return PROJECT_LIFECYCLE_INGESTED


@app.get(
    "/api/projects/{project_id}",
    response_model=ProjectDetailResponse,
    status_code=status.HTTP_200_OK,
)
def get_project_detail(project_id: int, session: Session = Depends(get_session)) -> ProjectDetailResponse:
    project = _get_project_or_404(session, project_id)
    return _build_project_detail_response(project)


@app.post(
    "/api/projects/{project_id}/ingest/source",
    response_model=ProjectIngestionSourceAttachResponse,
    status_code=status.HTTP_200_OK,
)
def attach_initial_ingestion_source(
    project_id: int,
    payload: ProjectIngestionSourceAttachRequest,
    session: Session = Depends(get_session),
) -> ProjectIngestionSourceAttachResponse:
    project = _get_project_or_404(session, project_id)
    if project.lifecycle_state != PROJECT_LIFECYCLE_DRAFT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="First ingestion source can only be attached while project is in draft state.",
        )

    chapter_count = session.query(Chapter).filter(Chapter.project_id == project.id).count()
    if chapter_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="First ingestion source cannot be attached after ingestion has started.",
        )

    log_json = dict(project.ingestion_log_json or {})
    existing_first_source = str(log_json.get("first_source", "")).strip().lower()
    if existing_first_source:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"First ingestion source already attached: {existing_first_source}",
        )

    attached_at = datetime.now(timezone.utc)
    log_json["first_source"] = payload.source
    log_json["first_source_attached_at"] = attached_at.isoformat()
    if payload.source_filename is not None:
        log_json["first_source_filename"] = payload.source_filename
    project.ingestion_log_json = log_json
    session.add(project)
    session.commit()
    session.refresh(project)

    return ProjectIngestionSourceAttachResponse(
        project_id=project.id,
        source=payload.source,
        source_filename=payload.source_filename,
        attached_at=attached_at,
    )


@app.patch(
    "/api/projects/{project_id}/metadata",
    response_model=ProjectMetadataUpdateResponse,
    status_code=status.HTTP_200_OK,
)
def update_project_metadata(
    project_id: int,
    payload: ProjectMetadataUpdateRequest,
    session: Session = Depends(get_session),
) -> ProjectMetadataUpdateResponse:
    project = _get_project_or_404(session, project_id)
    provided_fields = set(payload.model_fields_set)

    if "title" in provided_fields and payload.title is not None:
        project.title = payload.title
    if "description" in provided_fields:
        project.description = payload.description
    if "tags" in provided_fields:
        project.tags = list(payload.tags or [])

    _append_project_activity_event(
        session=session,
        project_id=project.id,
        event_type="manual_edit",
        event_metadata={
            "updated_fields": sorted(
                field for field in provided_fields if field in {"title", "description", "tags"}
            )
        },
    )
    _refresh_project_dashboard_projection(session=session, project=project)
    updated_at = datetime.now(timezone.utc)
    session.add(project)
    session.commit()
    session.refresh(project)

    return ProjectMetadataUpdateResponse(
        project_id=project.id,
        title=project.title,
        description=project.description,
        tags=list(project.tags or []),
        updated_at=updated_at,
    )


@app.get(
    "/api/dashboard/project-control-panel/summary",
    response_model=ProjectControlPanelSummaryResponse,
    status_code=status.HTTP_200_OK,
)
def get_project_control_panel_summary(session: Session = Depends(get_session)) -> ProjectControlPanelSummaryResponse:
    generated_at = datetime.now(timezone.utc).isoformat()
    projects = session.query(Project).all()
    runs = session.query(Run).all()
    project_title_by_id = {project.id: project.title for project in projects}

    state_counts = {state: 0 for state in _CONTROL_PANEL_STATE_ORDER}
    blocked_project_ids: set[int] = set()
    for project in projects:
        lifecycle_state = str(project.lifecycle_state or PROJECT_LIFECYCLE_DRAFT).strip().lower()
        if lifecycle_state in state_counts:
            state_counts[lifecycle_state] += 1
        if lifecycle_state != PROJECT_LIFECYCLE_COMPLETED:
            blocked_project_ids.add(project.id)

    active_run_count = 0
    blocked_export_run_count = 0
    failed_runs: list[Run] = []
    for run in runs:
        if run.status in {RUN_STATUS_QUEUED, RUN_STATUS_RUNNING}:
            active_run_count += 1
        if run.status != RUN_STATUS_COMPLETED:
            blocked_export_run_count += 1
            blocked_project_ids.add(run.project_id)
        if run.status == RUN_STATUS_FAILED:
            failed_runs.append(run)

    failed_runs.sort(
        key=lambda run: (
            run.finished_at
            or run.started_at
            or datetime.min.replace(tzinfo=timezone.utc)
        ),
        reverse=True,
    )

    recent_failures: list[dict[str, object]] = []
    for run in failed_runs[:_CONTROL_PANEL_RECENT_FAILURE_LIMIT]:
        raw_config = run.config_json if isinstance(run.config_json, dict) else {}
        raw_recovery = raw_config.get(_PIPELINE_RECOVERY_CONFIG_KEY)
        recovery_state = raw_recovery if isinstance(raw_recovery, dict) else {}
        reason = recovery_state.get("reason")
        reason_text = str(reason).strip() if reason is not None else ""
        error_message = reason_text if reason_text else None
        recent_failures.append(
            {
                "project_id": run.project_id,
                "project_title": project_title_by_id.get(run.project_id, f"Project {run.project_id}"),
                "run_id": run.id,
                "failed_at": _serialize_datetime_to_utc_iso(run.finished_at) or _serialize_datetime_to_utc_iso(run.started_at) or generated_at,
                "error_code": "pipeline_failed",
                "error_message": error_message,
            }
        )

    return ProjectControlPanelSummaryResponse(
        generated_at=generated_at,
        total_projects=len(projects),
        project_counts_by_state=[
            {"lifecycle_state": lifecycle_state, "project_count": state_counts[lifecycle_state]}
            for lifecycle_state in _CONTROL_PANEL_STATE_ORDER
        ],
        active_run_count=active_run_count,
        blocked_export_project_count=len(blocked_project_ids),
        blocked_export_run_count=blocked_export_run_count,
        recent_failure_count=len(failed_runs),
        recent_failures=recent_failures,
    )


def _resolve_project_control_panel_next_required_action(
    *,
    lifecycle_state: str,
    last_run_status: str | None,
) -> str:
    normalized_lifecycle_state = str(lifecycle_state or PROJECT_LIFECYCLE_DRAFT).strip().lower()
    normalized_last_run_status = str(last_run_status).strip().lower() if last_run_status else None

    if normalized_lifecycle_state == PROJECT_LIFECYCLE_ARCHIVED:
        return "archived"
    if normalized_last_run_status == RUN_STATUS_FAILED:
        return "review_failure"
    if normalized_last_run_status == RUN_STATUS_CANCELLED:
        return "rerun"
    if normalized_last_run_status in {RUN_STATUS_QUEUED, RUN_STATUS_RUNNING}:
        return "none"
    if normalized_last_run_status == RUN_STATUS_COMPLETED:
        return "export"
    if normalized_lifecycle_state == PROJECT_LIFECYCLE_DRAFT:
        return "ingest"
    if normalized_lifecycle_state in {PROJECT_LIFECYCLE_INGESTED, PROJECT_LIFECYCLE_CONFIGURED}:
        return "run"
    if normalized_lifecycle_state == PROJECT_LIFECYCLE_FAILED:
        return "review_failure"
    if normalized_lifecycle_state == PROJECT_LIFECYCLE_COMPLETED:
        return "export"
    if normalized_lifecycle_state == PROJECT_LIFECYCLE_RUNNING:
        return "none"
    return "configure"


def _resolve_allowed_project_actions(
    *,
    lifecycle_state: str,
    last_run_status: str | None,
) -> list[str]:
    normalized_lifecycle_state = str(lifecycle_state or PROJECT_LIFECYCLE_DRAFT).strip().lower()
    normalized_last_run_status = str(last_run_status).strip().lower() if last_run_status else None

    if normalized_lifecycle_state == PROJECT_LIFECYCLE_ARCHIVED:
        return ["restore"]

    if normalized_lifecycle_state == PROJECT_LIFECYCLE_RUNNING:
        return []

    allowed_actions: set[str] = {"ingest", "select_mode", "configure", "archive"}
    if normalized_lifecycle_state in {
        PROJECT_LIFECYCLE_INGESTED,
        PROJECT_LIFECYCLE_CONFIGURED,
        PROJECT_LIFECYCLE_COMPLETED,
        PROJECT_LIFECYCLE_FAILED,
    }:
        allowed_actions.add("run")

    if normalized_last_run_status in {RUN_STATUS_FAILED, RUN_STATUS_CANCELLED, "interrupted"}:
        allowed_actions.add("rerun")

    if (
        normalized_lifecycle_state == PROJECT_LIFECYCLE_COMPLETED
        and normalized_last_run_status == RUN_STATUS_COMPLETED
    ):
        allowed_actions.add("export")

    return [action for action in _PROJECT_ALLOWED_ACTION_ORDER if action in allowed_actions]


def _resolve_project_action_gating_metadata(
    *,
    lifecycle_state: str,
    next_required_action: str,
) -> tuple[str | None, str | None]:
    normalized_lifecycle_state = str(lifecycle_state or PROJECT_LIFECYCLE_DRAFT).strip().lower()
    normalized_next_required_action = str(next_required_action or "configure").strip().lower()

    if normalized_lifecycle_state == PROJECT_LIFECYCLE_ARCHIVED:
        return ("Project is archived. Restore the project to continue workflow actions.", "restore")

    if normalized_lifecycle_state == PROJECT_LIFECYCLE_RUNNING:
        return ("A run is currently in progress. Wait for completion before changing workflow actions.", "initial_run")

    if normalized_next_required_action == "ingest":
        return ("Source ingestion is required before setup and run actions are available.", "ingestion")
    if normalized_next_required_action in {"select_mode", "configure"}:
        return ("Mode selection and configuration must be completed before running the pipeline.", "mode_selection")
    if normalized_next_required_action in {"run", "rerun", "review_failure"}:
        return ("An initial run is required (or must be rerun) before downstream actions are unlocked.", "initial_run")
    if normalized_next_required_action in {"export", "none"}:
        return (None, None)

    return ("Project setup is incomplete for the current state.", "initial_run")


def _refresh_project_dashboard_projection(
    *,
    session: Session,
    project: Project,
    export_recorded_at: datetime | None = None,
) -> None:
    session.flush()
    latest_run = (
        session.query(Run)
        .filter(Run.project_id == project.id)
        .order_by(Run.id.desc())
        .first()
    )
    if latest_run is None:
        resolved_last_run_status: str | None = None
    else:
        normalized_last_run_status = str(latest_run.status or "").strip().lower()
        resolved_last_run_status = normalized_last_run_status or None

    lifecycle_state = str(project.lifecycle_state or PROJECT_LIFECYCLE_DRAFT).strip().lower()
    if lifecycle_state not in set(_CONTROL_PANEL_STATE_ORDER):
        lifecycle_state = PROJECT_LIFECYCLE_DRAFT

    project.last_run_status = resolved_last_run_status
    if export_recorded_at is not None:
        project.last_export_at = export_recorded_at
    project.next_required_action = _resolve_project_control_panel_next_required_action(
        lifecycle_state=lifecycle_state,
        last_run_status=resolved_last_run_status,
    )
    session.add(project)


@app.get(
    "/api/projects/{project_id}/actions",
    response_model=ProjectAllowedActionsResponse,
    status_code=status.HTTP_200_OK,
)
def get_project_allowed_actions(
    project_id: int,
    session: Session = Depends(get_session),
) -> ProjectAllowedActionsResponse:
    project = _get_project_or_404(session, project_id)
    normalized_lifecycle_state = str(project.lifecycle_state or PROJECT_LIFECYCLE_DRAFT).strip().lower()
    if normalized_lifecycle_state not in set(_CONTROL_PANEL_STATE_ORDER):
        normalized_lifecycle_state = PROJECT_LIFECYCLE_DRAFT

    normalized_last_run_status = (
        str(project.last_run_status).strip().lower()
        if project.last_run_status is not None
        else None
    )
    if normalized_last_run_status == "":
        normalized_last_run_status = None

    normalized_next_required_action = str(project.next_required_action or "").strip().lower()
    if normalized_next_required_action not in _CONTROL_PANEL_NEXT_REQUIRED_ACTION_VALUES:
        normalized_next_required_action = _resolve_project_control_panel_next_required_action(
            lifecycle_state=normalized_lifecycle_state,
            last_run_status=normalized_last_run_status,
        )

    allowed_actions = _resolve_allowed_project_actions(
        lifecycle_state=normalized_lifecycle_state,
        last_run_status=normalized_last_run_status,
    )
    blocked_reason, required_step = _resolve_project_action_gating_metadata(
        lifecycle_state=normalized_lifecycle_state,
        next_required_action=normalized_next_required_action,
    )

    return ProjectAllowedActionsResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        project_id=project.id,
        lifecycle_state=normalized_lifecycle_state,
        last_run_status=normalized_last_run_status,
        next_required_action=normalized_next_required_action,
        allowed_actions=allowed_actions,
        blocked_reason=blocked_reason,
        required_step=required_step,
    )


@app.get(
    "/api/projects/{project_id}/setup-status",
    response_model=ProjectSetupStatusResponse,
    status_code=status.HTTP_200_OK,
)
def get_project_setup_status(
    project_id: int,
    session: Session = Depends(get_session),
) -> ProjectSetupStatusResponse:
    project = _get_project_or_404(session, project_id)
    return build_project_setup_status_response(
        session=session,
        project=project,
        next_required_action_resolver=_resolve_project_control_panel_next_required_action,
    )


@app.get(
    "/api/projects/{project_id}/workspace-summary",
    response_model=ProjectWorkspaceSummaryResponse,
    status_code=status.HTTP_200_OK,
)
def get_project_workspace_summary(
    project_id: int,
    session: Session = Depends(get_session),
) -> ProjectWorkspaceSummaryResponse:
    project = _get_project_or_404(session, project_id)
    normalized_lifecycle_state = str(project.lifecycle_state or PROJECT_LIFECYCLE_DRAFT).strip().lower()
    if normalized_lifecycle_state not in set(_CONTROL_PANEL_STATE_ORDER):
        normalized_lifecycle_state = PROJECT_LIFECYCLE_DRAFT

    normalized_last_run_status = (
        str(project.last_run_status).strip().lower()
        if project.last_run_status is not None
        else None
    )
    if normalized_last_run_status == "":
        normalized_last_run_status = None

    normalized_next_required_action = str(project.next_required_action or "").strip().lower()
    if normalized_next_required_action not in _CONTROL_PANEL_NEXT_REQUIRED_ACTION_VALUES:
        normalized_next_required_action = _resolve_project_control_panel_next_required_action(
            lifecycle_state=normalized_lifecycle_state,
            last_run_status=normalized_last_run_status,
        )

    chapters_count = session.query(Chapter.id).filter(Chapter.project_id == project.id).count()
    characters_count = session.query(Character.id).filter(Character.project_id == project.id).count()
    voice_mappings_count = session.query(CharacterVoiceMap.id).filter(CharacterVoiceMap.project_id == project.id).count()
    runs_total_count = session.query(Run.id).filter(Run.project_id == project.id).count()
    runs_completed_count = (
        session.query(Run.id)
        .filter(Run.project_id == project.id, Run.status == RUN_STATUS_COMPLETED)
        .count()
    )
    runs_failed_count = (
        session.query(Run.id)
        .filter(Run.project_id == project.id, Run.status == RUN_STATUS_FAILED)
        .count()
    )

    ingestion_ready = project.ingestion_timestamp is not None or chapters_count > 0
    mode_selection_ready = is_valid_mode(str(project.selected_mode or "").strip().lower())
    initial_run_ready = (
        runs_total_count > 0
        or normalized_last_run_status
        in {
            RUN_STATUS_QUEUED,
            RUN_STATUS_RUNNING,
            RUN_STATUS_COMPLETED,
            RUN_STATUS_FAILED,
            RUN_STATUS_CANCELLED,
            "interrupted",
        }
        or normalized_lifecycle_state
        in {
            PROJECT_LIFECYCLE_RUNNING,
            PROJECT_LIFECYCLE_COMPLETED,
            PROJECT_LIFECYCLE_FAILED,
        }
    )

    return ProjectWorkspaceSummaryResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        project_id=project.id,
        lifecycle_state=normalized_lifecycle_state,
        last_run_status=normalized_last_run_status,
        next_required_action=normalized_next_required_action,
        is_setup_complete=all([ingestion_ready, mode_selection_ready, initial_run_ready]),
        chapters_count=chapters_count,
        characters_count=characters_count,
        voice_mappings_count=voice_mappings_count,
        runs_total_count=runs_total_count,
        runs_completed_count=runs_completed_count,
        runs_failed_count=runs_failed_count,
        last_export_at=_serialize_datetime_to_utc_iso(project.last_export_at),
    )


@app.post(
    "/api/projects/{project_id}/archive",
    response_model=ProjectLifecycleStateChangeResponse,
    status_code=status.HTTP_200_OK,
)
def archive_project(
    project_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> ProjectLifecycleStateChangeResponse:
    project = _get_project_or_404(session, project_id)
    normalized_lifecycle_state = str(project.lifecycle_state or PROJECT_LIFECYCLE_DRAFT).strip().lower()
    if normalized_lifecycle_state not in set(_CONTROL_PANEL_STATE_ORDER):
        normalized_lifecycle_state = PROJECT_LIFECYCLE_DRAFT
    normalized_last_run_status = (
        str(project.last_run_status).strip().lower()
        if project.last_run_status is not None
        else None
    )
    if normalized_last_run_status == "":
        normalized_last_run_status = None
    normalized_next_required_action = str(project.next_required_action or "").strip().lower()
    if normalized_next_required_action not in _CONTROL_PANEL_NEXT_REQUIRED_ACTION_VALUES:
        normalized_next_required_action = _resolve_project_control_panel_next_required_action(
            lifecycle_state=normalized_lifecycle_state,
            last_run_status=normalized_last_run_status,
        )

    allowed_actions = _resolve_allowed_project_actions(
        lifecycle_state=normalized_lifecycle_state,
        last_run_status=normalized_last_run_status,
    )
    if "archive" not in allowed_actions:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project cannot be archived in its current state.",
        )

    project_principal = _resolve_project_access_headers(request=request)
    if project_principal is None:
        principal_type = None
        principal_id = None
    else:
        principal_type, principal_id = project_principal
    activity_actor = _resolve_project_activity_actor(
        principal_type=principal_type,
        principal_id=principal_id,
    )

    archived_at = datetime.now(timezone.utc).isoformat()
    log_json = dict(project.ingestion_log_json or {})
    log_json[_PROJECT_ARCHIVE_METADATA_KEY] = {
        "previous_lifecycle_state": normalized_lifecycle_state,
        "previous_last_run_status": normalized_last_run_status,
        "previous_next_required_action": normalized_next_required_action,
        "archived_at": archived_at,
    }
    project.ingestion_log_json = log_json

    _transition_project_lifecycle_state(
        project,
        PROJECT_LIFECYCLE_ARCHIVED,
        session=session,
        actor=activity_actor,
    )
    _append_project_activity_event(
        session=session,
        project_id=project.id,
        event_type="manual_edit",
        actor=activity_actor,
        event_metadata={
            "action": "archive",
            "from_lifecycle_state": normalized_lifecycle_state,
            "to_lifecycle_state": PROJECT_LIFECYCLE_ARCHIVED,
        },
    )
    _refresh_project_dashboard_projection(session=session, project=project)
    session.add(project)
    session.commit()
    session.refresh(project)

    normalized_project_last_run_status = (
        str(project.last_run_status).strip().lower()
        if project.last_run_status is not None
        else None
    )
    if normalized_project_last_run_status == "":
        normalized_project_last_run_status = None
    resolved_next_required_action = str(project.next_required_action or "").strip().lower()
    if resolved_next_required_action not in _CONTROL_PANEL_NEXT_REQUIRED_ACTION_VALUES:
        resolved_next_required_action = _resolve_project_control_panel_next_required_action(
            lifecycle_state=PROJECT_LIFECYCLE_ARCHIVED,
            last_run_status=normalized_project_last_run_status,
        )

    return ProjectLifecycleStateChangeResponse(
        generated_at=archived_at,
        project_id=project.id,
        action="archive",
        previous_lifecycle_state=normalized_lifecycle_state,
        lifecycle_state=PROJECT_LIFECYCLE_ARCHIVED,
        last_run_status=normalized_project_last_run_status,
        next_required_action=resolved_next_required_action,
        allowed_actions=_resolve_allowed_project_actions(
            lifecycle_state=PROJECT_LIFECYCLE_ARCHIVED,
            last_run_status=normalized_project_last_run_status,
        ),
    )


@app.post(
    "/api/projects/{project_id}/restore",
    response_model=ProjectLifecycleStateChangeResponse,
    status_code=status.HTTP_200_OK,
)
def restore_project(
    project_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> ProjectLifecycleStateChangeResponse:
    project = _get_project_or_404(session, project_id)
    normalized_lifecycle_state = str(project.lifecycle_state or PROJECT_LIFECYCLE_DRAFT).strip().lower()
    if normalized_lifecycle_state not in set(_CONTROL_PANEL_STATE_ORDER):
        normalized_lifecycle_state = PROJECT_LIFECYCLE_DRAFT
    if normalized_lifecycle_state != PROJECT_LIFECYCLE_ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only archived projects can be restored.",
        )

    restore_target_state = _resolve_archived_project_restore_state(session=session, project=project)
    if restore_target_state == PROJECT_LIFECYCLE_ARCHIVED:
        restore_target_state = PROJECT_LIFECYCLE_DRAFT

    project_principal = _resolve_project_access_headers(request=request)
    if project_principal is None:
        principal_type = None
        principal_id = None
    else:
        principal_type, principal_id = project_principal
    activity_actor = _resolve_project_activity_actor(
        principal_type=principal_type,
        principal_id=principal_id,
    )

    _transition_project_lifecycle_state(
        project,
        restore_target_state,
        session=session,
        actor=activity_actor,
    )
    restored_at = datetime.now(timezone.utc).isoformat()
    log_json = dict(project.ingestion_log_json or {})
    archived_metadata = log_json.get(_PROJECT_ARCHIVE_METADATA_KEY)
    if isinstance(archived_metadata, dict):
        next_archive_metadata = dict(archived_metadata)
    else:
        next_archive_metadata = {}
    next_archive_metadata["restored_at"] = restored_at
    next_archive_metadata["restored_lifecycle_state"] = restore_target_state
    log_json[_PROJECT_ARCHIVE_METADATA_KEY] = next_archive_metadata
    project.ingestion_log_json = log_json
    _append_project_activity_event(
        session=session,
        project_id=project.id,
        event_type="manual_edit",
        actor=activity_actor,
        event_metadata={
            "action": "restore",
            "from_lifecycle_state": PROJECT_LIFECYCLE_ARCHIVED,
            "to_lifecycle_state": restore_target_state,
        },
    )
    _refresh_project_dashboard_projection(session=session, project=project)
    session.add(project)
    session.commit()
    session.refresh(project)

    normalized_project_last_run_status = (
        str(project.last_run_status).strip().lower()
        if project.last_run_status is not None
        else None
    )
    if normalized_project_last_run_status == "":
        normalized_project_last_run_status = None
    resolved_next_required_action = str(project.next_required_action or "").strip().lower()
    if resolved_next_required_action not in _CONTROL_PANEL_NEXT_REQUIRED_ACTION_VALUES:
        resolved_next_required_action = _resolve_project_control_panel_next_required_action(
            lifecycle_state=restore_target_state,
            last_run_status=normalized_project_last_run_status,
        )

    return ProjectLifecycleStateChangeResponse(
        generated_at=restored_at,
        project_id=project.id,
        action="restore",
        previous_lifecycle_state=PROJECT_LIFECYCLE_ARCHIVED,
        lifecycle_state=restore_target_state,
        last_run_status=normalized_project_last_run_status,
        next_required_action=resolved_next_required_action,
        allowed_actions=_resolve_allowed_project_actions(
            lifecycle_state=restore_target_state,
            last_run_status=normalized_project_last_run_status,
        ),
    )


@app.get(
    "/api/projects/{project_id}/timeline",
    response_model=ProjectActivityTimelineResponse,
    status_code=status.HTTP_200_OK,
)
def get_project_activity_timeline(
    project_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    session: Session = Depends(get_session),
) -> ProjectActivityTimelineResponse:
    _get_project_or_404(session, project_id)
    generated_at = datetime.now(timezone.utc).isoformat()
    query = session.query(ProjectActivityEvent).filter(ProjectActivityEvent.project_id == project_id)
    total_items = query.count()
    start_index = (page - 1) * page_size
    end_index = start_index + page_size
    events = (
        query.order_by(ProjectActivityEvent.created_at.desc(), ProjectActivityEvent.id.desc())
        .offset(start_index)
        .limit(page_size)
        .all()
    )

    items: list[dict[str, object]] = []
    for event in events:
        metadata_payload = event.event_metadata if isinstance(event.event_metadata, dict) else {}
        items.append(
            {
                "event_id": event.id,
                "event_type": event.event_type,
                "actor": str(event.actor).strip() or "system",
                "run_id": event.run_id,
                "created_at": _serialize_datetime_to_utc_iso(event.created_at) or generated_at,
                "event_metadata": dict(metadata_payload),
            }
        )

    return ProjectActivityTimelineResponse(
        generated_at=generated_at,
        project_id=project_id,
        total_items=total_items,
        page=page,
        page_size=page_size,
        has_next_page=end_index < total_items,
        items=items,
    )


@app.get(
    "/api/dashboard/project-control-panel/projects",
    response_model=ProjectControlPanelProjectListResponse,
    status_code=status.HTTP_200_OK,
)
def get_project_control_panel_project_list(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    lifecycle_state: str | None = Query(default=None, alias="status"),
    selected_mode: str | None = Query(default=None),
    last_run_status: str | None = Query(default=None),
    next_required_action: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> ProjectControlPanelProjectListResponse:
    generated_at = datetime.now(timezone.utc).isoformat()
    normalized_status = str(lifecycle_state).strip().lower() if lifecycle_state is not None else None
    if normalized_status is not None and normalized_status not in set(_CONTROL_PANEL_STATE_ORDER):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "status must be one of: "
                f"{', '.join(_CONTROL_PANEL_STATE_ORDER)}"
            ),
        )

    normalized_selected_mode = str(selected_mode).strip().lower() if selected_mode is not None else None
    if normalized_selected_mode == "":
        normalized_selected_mode = None
    normalized_last_run_status = str(last_run_status).strip().lower() if last_run_status is not None else None
    if normalized_last_run_status == "":
        normalized_last_run_status = None
    if normalized_last_run_status is not None and normalized_last_run_status not in {
        RUN_STATUS_QUEUED,
        RUN_STATUS_RUNNING,
        RUN_STATUS_COMPLETED,
        RUN_STATUS_FAILED,
        RUN_STATUS_CANCELLED,
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="last_run_status must be one of: queued, running, completed, failed, cancelled",
        )

    normalized_next_required_action = (
        str(next_required_action).strip().lower()
        if next_required_action is not None
        else None
    )
    if normalized_next_required_action == "":
        normalized_next_required_action = None
    if (
        normalized_next_required_action is not None
        and normalized_next_required_action not in _CONTROL_PANEL_NEXT_REQUIRED_ACTION_VALUES
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "next_required_action must be one of: "
                "ingest, select_mode, configure, run, rerun, export, review_failure, archived, none"
            ),
        )

    query = session.query(Project)
    if normalized_status is not None:
        query = query.filter(Project.lifecycle_state == normalized_status)
    if normalized_selected_mode is not None:
        query = query.filter(Project.selected_mode == normalized_selected_mode)
    if normalized_last_run_status is not None:
        query = query.filter(Project.last_run_status == normalized_last_run_status)
    if normalized_next_required_action is not None:
        query = query.filter(Project.next_required_action == normalized_next_required_action)

    total_items = query.count()
    start_index = (page - 1) * page_size
    end_index = start_index + page_size
    projects = (
        query.order_by(Project.created_at.desc(), Project.id.desc())
        .offset(start_index)
        .limit(page_size)
        .all()
    )

    paged_rows: list[dict[str, object]] = []
    for project in projects:
        normalized_project_status = str(project.lifecycle_state or PROJECT_LIFECYCLE_DRAFT).strip().lower()
        if normalized_project_status not in set(_CONTROL_PANEL_STATE_ORDER):
            normalized_project_status = PROJECT_LIFECYCLE_DRAFT

        normalized_project_last_run_status = (
            str(project.last_run_status).strip().lower()
            if project.last_run_status is not None
            else None
        )
        if normalized_project_last_run_status == "":
            normalized_project_last_run_status = None

        normalized_project_next_action = str(project.next_required_action or "").strip().lower()
        if normalized_project_next_action not in _CONTROL_PANEL_NEXT_REQUIRED_ACTION_VALUES:
            normalized_project_next_action = _resolve_project_control_panel_next_required_action(
                lifecycle_state=normalized_project_status,
                last_run_status=normalized_project_last_run_status,
            )

        updated_at_candidates = [
            project.created_at,
            project.ingestion_timestamp,
            project.last_export_at,
        ]
        updated_at = max(candidate for candidate in updated_at_candidates if candidate is not None)
        paged_rows.append(
            {
                "project_id": project.id,
                "status": normalized_project_status,
                "selected_mode": str(project.selected_mode).strip().lower() or DEFAULT_MODE,
                "last_run_status": normalized_project_last_run_status,
                "updated_at": _serialize_datetime_to_utc_iso(updated_at) or generated_at,
                "next_required_action": normalized_project_next_action,
            }
        )

    return ProjectControlPanelProjectListResponse(
        generated_at=generated_at,
        total_items=total_items,
        page=page,
        page_size=page_size,
        has_next_page=end_index < total_items,
        items=paged_rows,
    )


@app.get(
    "/api/projects/{project_id}/llm",
    response_model=ProjectLLMSettingsResponse,
    status_code=status.HTTP_200_OK,
)
def get_project_llm_settings(
    project_id: int,
    session: Session = Depends(get_session),
) -> ProjectLLMSettingsResponse:
    project = _get_project_or_404(session, project_id)
    return ProjectLLMSettingsResponse(
        project_id=project.id,
        llm_enabled=project.llm_enabled,
        provider_config=_sanitize_provider_config_for_frontend(project.llm_provider_config_json),
    )


@app.put(
    "/api/projects/{project_id}/llm",
    response_model=ProjectLLMSettingsResponse,
    status_code=status.HTTP_200_OK,
)
def update_project_llm_settings(
    project_id: int,
    payload: ProjectLLMSettingsRequest,
    session: Session = Depends(get_session),
) -> ProjectLLMSettingsResponse:
    project = _get_project_or_404(session, project_id)
    project.llm_enabled = payload.llm_enabled
    if payload.provider_config is not None:
        merged_provider_config: dict[str, dict[str, object]] = dict(project.llm_provider_config_json or {})
        merged_provider_config.update(payload.provider_config)
        project.llm_provider_config_json = merged_provider_config
    session.add(project)
    session.commit()
    session.refresh(project)

    return ProjectLLMSettingsResponse(
        project_id=project.id,
        llm_enabled=project.llm_enabled,
        provider_config=_sanitize_provider_config_for_frontend(project.llm_provider_config_json),
    )


@app.get(
    "/api/llm/providers",
    response_model=LLMProvidersResponse,
    status_code=status.HTTP_200_OK,
)
def get_llm_provider_statuses(
    session: Session = Depends(get_session),
) -> LLMProvidersResponse:
    settings = get_settings()
    providers = get_provider_statuses(session=session, settings=settings)
    return LLMProvidersResponse(
        providers=[LLMProviderStatus(provider=provider, enabled=enabled) for provider, enabled in providers]
    )


@app.put(
    "/api/llm/providers/{provider_name}",
    response_model=LLMProviderStatus,
    status_code=status.HTTP_200_OK,
)
def update_llm_provider_toggle(
    provider_name: str,
    payload: LLMProviderStatusUpdateRequest,
    session: Session = Depends(get_session),
) -> LLMProviderStatus:
    provider = provider_name.strip().lower()
    if not provider:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="provider_name must not be blank")

    if not is_supported_provider(provider):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown provider")

    enabled = set_provider_enabled(session=session, provider=provider, enabled=payload.enabled)
    session.commit()
    return LLMProviderStatus(provider=provider, enabled=enabled)


@app.put(
    "/api/projects/{project_id}/mode",
    response_model=ProjectModeSwitchResponse,
    status_code=status.HTTP_200_OK,
)
def switch_project_mode(
    project_id: int,
    payload: ProjectModeSwitchRequest,
    session: Session = Depends(get_session),
) -> ProjectModeSwitchResponse:
    project = _get_project_or_404(session, project_id)
    previous_mode = project.selected_mode

    chapter_count = session.query(Chapter).filter(Chapter.project_id == project.id).count()
    stale_runs_marked = 0
    if previous_mode != payload.mode:
        project_runs = session.query(Run).filter(Run.project_id == project.id).all()
        stale_runs_marked = mark_runs_stale_for_mode_switch(project_runs, payload.mode)

    _transition_project_lifecycle_state(project, PROJECT_LIFECYCLE_CONFIGURED, session=session)
    project.selected_mode = payload.mode
    project.selected_modes = _merge_selected_modes(project.selected_modes, payload.mode)
    _append_project_activity_event(
        session=session,
        project_id=project.id,
        event_type="mode_change",
        event_metadata={
            "previous_mode": previous_mode,
            "selected_mode": payload.mode,
            "stale_runs_marked": stale_runs_marked,
        },
    )
    session.add(project)
    session.commit()
    session.refresh(project)

    return ProjectModeSwitchResponse(
        project_id=project.id,
        previous_mode=previous_mode,
        selected_mode=project.selected_mode,
        selected_modes=project.selected_modes,
        chapter_count=chapter_count,
        reused_ingested_corpus=chapter_count > 0,
        stale_runs_marked=stale_runs_marked,
    )


@app.post(
    "/api/projects/{project_id}/ingest/txt",
    response_model=IngestResponse,
    status_code=status.HTTP_200_OK,
)
def ingest_txt(
    project_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> IngestResponse:
    project = _get_project_or_404(session, project_id)
    _lock_project_for_ingestion(session, project_id)

    filename = file.filename or ""
    if not filename.lower().endswith(".txt"):
        raise UnsupportedFormatIngestionError(detail="Only .txt files are supported")

    payload = file.file.read()
    raw_text, encoding, confidence = decode_text_with_metadata(payload)
    if is_likely_unsupported_encoding(raw_text):
        raise UnsupportedEncodingIngestionError(
            detail="Unable to decode TXT content reliably with supported encodings",
        )
    detected_title = detect_title_with_fallback(raw_text, filename=filename)
    detected_chapters, is_ambiguous_boundaries = detect_chapters_with_metadata(raw_text)
    chapters = [(title, content) for title, content in detected_chapters if content.strip()]
    if not chapters:
        raise MissingChaptersIngestionError(detail="No non-empty chapters found in TXT input")
    warnings: list[dict[str, object]] = []
    chapter_normalization_reports: list[dict[str, object]] = []
    encoding_warnings: list[dict[str, object]] = []
    txt_warning = build_encoding_warning("txt", encoding, confidence)
    if txt_warning is not None:
        warnings.append(txt_warning)
        encoding_warnings.append(txt_warning)
    if is_ambiguous_boundaries:
        warnings.append(build_ambiguous_chapter_boundary_warning("txt", len(chapters)))
    duplicate_title_warnings = build_duplicate_title_warnings("txt", chapters)
    warnings.extend(duplicate_title_warnings)
    suspected_duplicate_content_warnings = build_suspected_duplicate_content_warnings(
        "txt",
        detect_suspected_duplicate_content(chapters),
    )
    warnings.extend(suspected_duplicate_content_warnings)
    dedup_actions = build_duplicate_title_dedup_actions("txt", chapters)

    session.query(Chapter).filter(Chapter.project_id == project_id).delete()

    for idx, (title, content) in enumerate(chapters, start=1):
        chapter_title = to_internal_utf8(title)
        chapter_content = to_internal_utf8(content)
        normalized, quote_warnings, chapter_report = normalize_text_with_report(
            chapter_content,
            source="txt",
        )
        chapter_normalization_reports.append(chapter_report)
        chapter_offset_map = build_original_to_normalized_offset_map(chapter_content, normalized)
        stored_raw_text, stored_original_snapshot, stored_offset_map = _build_ingested_chapter_text_payload(
            project=project,
            source_text=chapter_content,
            original_to_normalized_offset_map=chapter_offset_map,
        )
        warnings.extend(quote_warnings)
        session.add(
            Chapter(
                project_id=project_id,
                chapter_index=idx,
                chapter_internal_id=build_internal_chapter_id(idx),
                chapter_title=chapter_title,
                raw_text=stored_raw_text,
                original_text_snapshot=stored_original_snapshot,
                normalized_text=normalized,
                normalized_text_snapshot=normalized,
                original_to_normalized_offset_map=stored_offset_map,
            )
        )
    normalization_report = build_normalization_report(
        source="txt",
        chapter_count=len(chapter_normalization_reports),
        chapter_reports=chapter_normalization_reports,
        suspected_duplicate_title_count=len(duplicate_title_warnings),
        suspected_duplicate_content_count=len(suspected_duplicate_content_warnings),
        encoding_issue_count=len(encoding_warnings),
    )

    if _project_title_needs_fallback(project.title):
        project.title = to_internal_utf8(detected_title)
    if _project_allows_source_text_storage(project):
        _persist_raw_corpus_blob(
            session=session,
            project_id=project_id,
            source="txt",
            raw_corpus=raw_text,
            source_filename=filename,
        )
    _update_project_ingestion_log(
        project,
        source="txt",
        warnings=warnings,
        dedup_actions=dedup_actions,
        normalization_report=normalization_report,
    )
    _transition_project_lifecycle_state(project, PROJECT_LIFECYCLE_INGESTED, session=session)
    _append_project_activity_event(
        session=session,
        project_id=project.id,
        event_type="ingest",
        event_metadata={
            "source": "txt",
            "chapter_count": len(chapters),
        },
    )
    project.ingestion_timestamp = datetime.now(timezone.utc)
    session.add(project)
    _commit_ingestion_session(session)

    return IngestResponse(
        project_id=project_id,
        chapter_count=len(chapters),
        warnings=warnings,
        normalization_report=normalization_report,
    )


@app.post(
    "/api/projects/{project_id}/ingest/markdown",
    response_model=IngestResponse,
    status_code=status.HTTP_200_OK,
)
def ingest_markdown(
    project_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> IngestResponse:
    project = _get_project_or_404(session, project_id)
    _lock_project_for_ingestion(session, project_id)

    filename = file.filename or ""
    lower_filename = filename.lower()
    if not (lower_filename.endswith(".md") or lower_filename.endswith(".markdown")):
        raise UnsupportedFormatIngestionError(detail="Only .md or .markdown files are supported")

    payload = file.file.read()
    markdown_text, encoding, confidence = decode_text_with_metadata(payload)
    if is_likely_unsupported_encoding(markdown_text):
        raise UnsupportedEncodingIngestionError(
            detail="Unable to decode Markdown content reliably with supported encodings",
        )
    normalized_source = normalize_markdown_for_ingestion(markdown_text)
    detected_title = detect_title_with_fallback(normalized_source, filename=filename)
    detected_chapters, is_ambiguous_boundaries = detect_chapters_with_metadata(normalized_source)
    chapters = [(title, content) for title, content in detected_chapters if content.strip()]
    if not chapters:
        raise MissingChaptersIngestionError(detail="No non-empty chapters found in Markdown input")
    warnings: list[dict[str, object]] = []
    chapter_normalization_reports: list[dict[str, object]] = []
    encoding_warnings: list[dict[str, object]] = []
    markdown_warning = build_encoding_warning("markdown", encoding, confidence)
    if markdown_warning is not None:
        warnings.append(markdown_warning)
        encoding_warnings.append(markdown_warning)
    if is_ambiguous_boundaries:
        warnings.append(build_ambiguous_chapter_boundary_warning("markdown", len(chapters)))
    duplicate_title_warnings = build_duplicate_title_warnings("markdown", chapters)
    warnings.extend(duplicate_title_warnings)
    suspected_duplicate_content_warnings = build_suspected_duplicate_content_warnings(
        "markdown",
        detect_suspected_duplicate_content(chapters),
    )
    warnings.extend(suspected_duplicate_content_warnings)
    dedup_actions = build_duplicate_title_dedup_actions("markdown", chapters)

    session.query(Chapter).filter(Chapter.project_id == project_id).delete()

    for chapter_index, (chapter_title, chapter_content) in enumerate(chapters, start=1):
        stored_chapter_title = to_internal_utf8(chapter_title)
        stored_chapter_content = to_internal_utf8(chapter_content)
        normalized, quote_warnings, chapter_report = normalize_text_with_report(
            stored_chapter_content,
            source="markdown",
        )
        chapter_normalization_reports.append(chapter_report)
        chapter_offset_map = build_original_to_normalized_offset_map(
            stored_chapter_content,
            normalized,
        )
        stored_raw_text, stored_original_snapshot, stored_offset_map = _build_ingested_chapter_text_payload(
            project=project,
            source_text=stored_chapter_content,
            original_to_normalized_offset_map=chapter_offset_map,
        )
        warnings.extend(quote_warnings)
        session.add(
            Chapter(
                project_id=project_id,
                chapter_index=chapter_index,
                chapter_internal_id=build_internal_chapter_id(chapter_index),
                chapter_title=stored_chapter_title,
                raw_text=stored_raw_text,
                original_text_snapshot=stored_original_snapshot,
                normalized_text=normalized,
                normalized_text_snapshot=normalized,
                original_to_normalized_offset_map=stored_offset_map,
            )
        )
    normalization_report = build_normalization_report(
        source="markdown",
        chapter_count=len(chapter_normalization_reports),
        chapter_reports=chapter_normalization_reports,
        suspected_duplicate_title_count=len(duplicate_title_warnings),
        suspected_duplicate_content_count=len(suspected_duplicate_content_warnings),
        encoding_issue_count=len(encoding_warnings),
    )

    if _project_title_needs_fallback(project.title):
        project.title = to_internal_utf8(detected_title)
    if _project_allows_source_text_storage(project):
        _persist_raw_corpus_blob(
            session=session,
            project_id=project_id,
            source="markdown",
            raw_corpus=markdown_text,
            source_filename=filename,
        )
    _update_project_ingestion_log(
        project,
        source="markdown",
        warnings=warnings,
        dedup_actions=dedup_actions,
        normalization_report=normalization_report,
    )
    _transition_project_lifecycle_state(project, PROJECT_LIFECYCLE_INGESTED, session=session)
    _append_project_activity_event(
        session=session,
        project_id=project.id,
        event_type="ingest",
        event_metadata={
            "source": "markdown",
            "chapter_count": len(chapters),
        },
    )
    project.ingestion_timestamp = datetime.now(timezone.utc)
    session.add(project)
    _commit_ingestion_session(session)

    return IngestResponse(
        project_id=project_id,
        chapter_count=len(chapters),
        warnings=warnings,
        normalization_report=normalization_report,
    )


@app.post(
    "/api/projects/{project_id}/ingest/epub",
    response_model=IngestResponse,
    status_code=status.HTTP_200_OK,
)
def ingest_epub(
    project_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> IngestResponse:
    settings = get_settings()
    if not settings.enable_epub_ingestion:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="EPUB ingestion is disabled by configuration",
        )

    project = _get_project_or_404(session, project_id)
    _lock_project_for_ingestion(session, project_id)
    filename = file.filename or ""
    if not filename.lower().endswith(".epub"):
        raise UnsupportedFormatIngestionError(detail="Only .epub files are supported")

    payload = file.file.read()
    try:
        chapters = extract_epub_chapters(payload)
    except NotImplementedError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc)) from exc

    if not chapters:
        raise MissingChaptersIngestionError(detail="No chapter content found in EPUB")

    warnings: list[dict[str, object]] = []
    chapter_normalization_reports: list[dict[str, object]] = []
    duplicate_title_warnings = build_duplicate_title_warnings("epub", chapters)
    warnings.extend(duplicate_title_warnings)
    suspected_duplicate_content_warnings = build_suspected_duplicate_content_warnings(
        "epub",
        detect_suspected_duplicate_content(chapters),
    )
    warnings.extend(suspected_duplicate_content_warnings)
    encoding_issue_count = 0
    session.query(Chapter).filter(Chapter.project_id == project_id).delete()

    for chapter_index, (chapter_title, chapter_content) in enumerate(chapters, start=1):
        title = to_internal_utf8(chapter_title.strip() or f"Chapter {chapter_index}")
        content = to_internal_utf8(chapter_content.strip())
        if not content:
            continue
        normalized, quote_warnings, chapter_report = normalize_text_with_report(
            content,
            source="epub",
        )
        chapter_normalization_reports.append(chapter_report)
        chapter_offset_map = build_original_to_normalized_offset_map(content, normalized)
        stored_raw_text, stored_original_snapshot, stored_offset_map = _build_ingested_chapter_text_payload(
            project=project,
            source_text=content,
            original_to_normalized_offset_map=chapter_offset_map,
        )
        warnings.extend(quote_warnings)
        session.add(
            Chapter(
                project_id=project_id,
                chapter_index=chapter_index,
                chapter_internal_id=build_internal_chapter_id(chapter_index),
                chapter_title=title,
                raw_text=stored_raw_text,
                original_text_snapshot=stored_original_snapshot,
                normalized_text=normalized,
                normalized_text_snapshot=normalized,
                original_to_normalized_offset_map=stored_offset_map,
            )
        )

    if _project_title_needs_fallback(project.title):
        project.title = to_internal_utf8(
            chapters[0][0].strip() or detect_title_with_fallback("", filename=filename)
        )
    normalization_report = build_normalization_report(
        source="epub",
        chapter_count=len(chapter_normalization_reports),
        chapter_reports=chapter_normalization_reports,
        suspected_duplicate_title_count=len(duplicate_title_warnings),
        suspected_duplicate_content_count=len(suspected_duplicate_content_warnings),
        encoding_issue_count=encoding_issue_count,
    )
    if _project_allows_source_text_storage(project):
        _persist_raw_corpus_blob(
            session=session,
            project_id=project_id,
            source="epub",
            raw_corpus=_build_full_corpus_text(
                [
                    (index, chapter_title, chapter_content)
                    for index, (chapter_title, chapter_content) in enumerate(chapters, start=1)
                ]
            ),
            source_filename=filename,
        )
    _update_project_ingestion_log(
        project,
        source="epub",
        warnings=warnings,
        dedup_actions=build_duplicate_title_dedup_actions("epub", chapters),
        normalization_report=normalization_report,
    )
    _transition_project_lifecycle_state(project, PROJECT_LIFECYCLE_INGESTED, session=session)
    _append_project_activity_event(
        session=session,
        project_id=project.id,
        event_type="ingest",
        event_metadata={
            "source": "epub",
            "chapter_count": len(chapter_normalization_reports),
        },
    )
    project.ingestion_timestamp = datetime.now(timezone.utc)
    session.add(project)
    _commit_ingestion_session(session)

    chapter_count = session.query(Chapter).filter(Chapter.project_id == project_id).count()
    if chapter_count == 0:
        raise MissingChaptersIngestionError(detail="No non-empty chapter content found in EPUB")
    return IngestResponse(
        project_id=project_id,
        chapter_count=chapter_count,
        warnings=warnings,
        normalization_report=normalization_report,
    )


@app.post(
    "/api/projects/{project_id}/ingest/chapters-dir",
    response_model=IngestResponse,
    status_code=status.HTTP_200_OK,
)
def ingest_chapters_dir(
    project_id: int,
    files: list[UploadFile] = File(...),
    session: Session = Depends(get_session),
) -> IngestResponse:
    project = _get_project_or_404(session, project_id)
    _lock_project_for_ingestion(session, project_id)
    if not files:
        raise MissingChaptersIngestionError(detail="At least one chapter file is required")

    sorted_files = sorted(files, key=lambda upload: chapter_filename_sort_key(upload.filename or ""))

    file_boundaries: list[tuple[str, str]] = []
    warnings: list[dict[str, object]] = []
    encoding_warnings: list[dict[str, object]] = []
    chapter_normalization_reports: list[dict[str, object]] = []
    for upload in sorted_files:
        filename = upload.filename or ""
        if not filename.lower().endswith(".txt"):
            raise UnsupportedFormatIngestionError(detail="Chapter directory only supports .txt files")

        payload = upload.file.read()
        content = decode_text(payload).strip()
        if is_likely_unsupported_encoding(content):
            raise UnsupportedEncodingIngestionError(
                detail=f"Unable to decode chapter file reliably: {filename}",
            )
        encoding, confidence = detect_text_encoding(payload)
        directory_warning = build_encoding_warning(f"chapters-dir:{filename}", encoding, confidence)
        if directory_warning is not None:
            warnings.append(directory_warning)
            encoding_warnings.append(directory_warning)
        if not content:
            continue

        file_boundaries.append((filename, to_internal_utf8(content)))

    chapter_rows = [
        (to_internal_utf8(chapter_title), to_internal_utf8(chapter_content))
        for chapter_title, chapter_content in detect_chapters_from_file_boundaries(file_boundaries)
    ]
    duplicate_title_warnings = build_duplicate_title_warnings("chapters-dir", chapter_rows)
    warnings.extend(duplicate_title_warnings)
    suspected_duplicate_content_warnings = build_suspected_duplicate_content_warnings(
        "chapters-dir",
        detect_suspected_duplicate_content(chapter_rows),
    )
    warnings.extend(suspected_duplicate_content_warnings)
    dedup_actions = build_duplicate_title_dedup_actions("chapters-dir", chapter_rows)

    if not chapter_rows:
        raise MissingChaptersIngestionError(detail="No non-empty chapter content found")

    session.query(Chapter).filter(Chapter.project_id == project_id).delete()

    for chapter_index, (chapter_title, chapter_content) in enumerate(chapter_rows, start=1):
        normalized, quote_warnings, chapter_report = normalize_text_with_report(
            chapter_content,
            source="chapters-dir",
        )
        chapter_normalization_reports.append(chapter_report)
        chapter_offset_map = build_original_to_normalized_offset_map(chapter_content, normalized)
        stored_raw_text, stored_original_snapshot, stored_offset_map = _build_ingested_chapter_text_payload(
            project=project,
            source_text=chapter_content,
            original_to_normalized_offset_map=chapter_offset_map,
        )
        warnings.extend(quote_warnings)
        session.add(
            Chapter(
                project_id=project_id,
                chapter_index=chapter_index,
                chapter_internal_id=build_internal_chapter_id(chapter_index),
                chapter_title=chapter_title,
                raw_text=stored_raw_text,
                original_text_snapshot=stored_original_snapshot,
                normalized_text=normalized,
                normalized_text_snapshot=normalized,
                original_to_normalized_offset_map=stored_offset_map,
            )
        )

    if _project_title_needs_fallback(project.title):
        project.title = to_internal_utf8(chapter_rows[0][0])
    normalization_report = build_normalization_report(
        source="chapters-dir",
        chapter_count=len(chapter_normalization_reports),
        chapter_reports=chapter_normalization_reports,
        suspected_duplicate_title_count=len(duplicate_title_warnings),
        suspected_duplicate_content_count=len(suspected_duplicate_content_warnings),
        encoding_issue_count=len(encoding_warnings),
    )
    if _project_allows_source_text_storage(project):
        _persist_raw_corpus_blob(
            session=session,
            project_id=project_id,
            source="chapters-dir",
            raw_corpus=_build_full_corpus_text(
                [
                    (index, chapter_title, chapter_content)
                    for index, (chapter_title, chapter_content) in enumerate(chapter_rows, start=1)
                ]
            ),
            source_filename=None,
        )
    _update_project_ingestion_log(
        project,
        source="chapters-dir",
        warnings=warnings,
        dedup_actions=dedup_actions,
        normalization_report=normalization_report,
    )
    _transition_project_lifecycle_state(project, PROJECT_LIFECYCLE_INGESTED, session=session)
    _append_project_activity_event(
        session=session,
        project_id=project.id,
        event_type="ingest",
        event_metadata={
            "source": "chapters-dir",
            "chapter_count": len(chapter_rows),
        },
    )
    project.ingestion_timestamp = datetime.now(timezone.utc)
    session.add(project)
    _commit_ingestion_session(session)

    return IngestResponse(
        project_id=project_id,
        chapter_count=len(chapter_rows),
        warnings=warnings,
        normalization_report=normalization_report,
    )


@app.post(
    "/api/projects/{project_id}/ingest/append-chapter",
    response_model=IngestResponse,
    status_code=status.HTTP_200_OK,
)
def append_chapter(
    project_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> IngestResponse:
    project = _get_project_or_404(session, project_id)
    _lock_project_for_ingestion(session, project_id)

    filename = file.filename or ""
    if not filename.lower().endswith(".txt"):
        raise UnsupportedFormatIngestionError(detail="Append chapter only supports .txt files")

    payload = file.file.read()
    raw_text, encoding, confidence = decode_text_with_metadata(payload)
    if is_likely_unsupported_encoding(raw_text):
        raise UnsupportedEncodingIngestionError(
            detail="Unable to decode appended chapter reliably with supported encodings",
        )
    has_explicit_header = contains_explicit_chapter_header(raw_text)
    parsed_chapters = detect_chapters(raw_text)
    fallback_title = chapter_title_from_filename(filename, chapter_index=_get_next_chapter_index(session, project_id))
    try:
        parsed_title, parsed_content = extract_single_append_chapter(parsed_chapters, fallback_title=fallback_title)
    except ValueError as exc:
        raise MissingChaptersIngestionError(detail=str(exc)) from exc

    next_chapter_index = _get_next_chapter_index(session, project_id)
    chapter_title = to_internal_utf8(parsed_title if has_explicit_header else fallback_title)
    chapter_content = to_internal_utf8(parsed_content)
    existing_chapters = (
        session.query(
            Chapter.chapter_index,
            Chapter.chapter_title,
            Chapter.raw_text,
            Chapter.normalized_text,
        )
        .filter(Chapter.project_id == project_id)
        .order_by(Chapter.chapter_index.asc())
        .all()
    )
    overlap_match = detect_append_overlap_or_duplicate(
        new_title=chapter_title,
        new_content=chapter_content,
        existing_chapters=[
            (
                row[0],
                row[1],
                row[2] if row[2] else row[3],
            )
            for row in existing_chapters
        ],
    )
    if overlap_match is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Append chapter rejected: "
                f"{overlap_match['kind']} against chapter {overlap_match['chapter_index']}"
            ),
    )

    warning = build_encoding_warning("append-chapter", encoding, confidence)
    chapter_normalization_reports: list[dict[str, object]] = []
    encoding_warnings: list[dict[str, object]] = []
    if warning is not None:
        encoding_warnings.append(warning)
    normalized, quote_warnings, chapter_report = normalize_text_with_report(
        chapter_content,
        source="append-chapter",
    )
    chapter_normalization_reports.append(chapter_report)
    chapter_offset_map = build_original_to_normalized_offset_map(chapter_content, normalized)
    stored_raw_text, stored_original_snapshot, stored_offset_map = _build_ingested_chapter_text_payload(
        project=project,
        source_text=chapter_content,
        original_to_normalized_offset_map=chapter_offset_map,
    )
    warnings: list[dict[str, object]] = [warning] if warning is not None else []
    warnings.extend(quote_warnings)
    combined_titles = [
        (row[1], row[2] if row[2] else row[3]) for row in existing_chapters
    ] + [(chapter_title, chapter_content)]
    duplicate_title_warnings = build_duplicate_title_warnings("append-chapter", combined_titles)
    warnings.extend(duplicate_title_warnings)
    suspected_duplicate_content_warnings = build_suspected_duplicate_content_warnings(
        "append-chapter",
        detect_suspected_duplicate_content(
            combined_titles,
            minimum_chars=120,
            similarity_threshold=0.94,
        ),
    )
    warnings.extend(suspected_duplicate_content_warnings)
    dedup_actions = build_duplicate_title_dedup_actions("append-chapter", combined_titles)

    session.add(
        Chapter(
            project_id=project_id,
            chapter_index=next_chapter_index,
            chapter_internal_id=build_internal_chapter_id(next_chapter_index),
            chapter_title=chapter_title,
            raw_text=stored_raw_text,
            original_text_snapshot=stored_original_snapshot,
            normalized_text=normalized,
            normalized_text_snapshot=normalized,
            original_to_normalized_offset_map=stored_offset_map,
        )
    )

    affected_range = calculate_delta_affected_range(
        changed_chapter_indices=[next_chapter_index],
        total_chapter_count=len(existing_chapters) + 1,
    )
    normalization_report = build_normalization_report(
        source="append-chapter",
        chapter_count=1,
        chapter_reports=chapter_normalization_reports,
        suspected_duplicate_title_count=len(duplicate_title_warnings),
        suspected_duplicate_content_count=len(suspected_duplicate_content_warnings),
        encoding_issue_count=len(encoding_warnings),
    )
    _update_project_ingestion_log(
        project,
        source="append-chapter",
        warnings=warnings,
        dedup_actions=dedup_actions,
        affected_range=affected_range,
        normalization_report=normalization_report,
    )
    if _project_allows_source_text_storage(project):
        _persist_raw_corpus_blob(
            session=session,
            project_id=project_id,
            source="append-chapter",
            raw_corpus=_build_full_corpus_text(
                [
                    (row[0], row[1], row[2])
                    for row in existing_chapters
                ]
                + [(next_chapter_index, chapter_title, chapter_content)]
            ),
            source_filename=filename,
        )
    _transition_project_lifecycle_state(project, PROJECT_LIFECYCLE_INGESTED, session=session)
    _append_project_activity_event(
        session=session,
        project_id=project.id,
        event_type="ingest",
        event_metadata={
            "source": "append-chapter",
            "chapter_index": next_chapter_index,
        },
    )
    project.ingestion_timestamp = datetime.now(timezone.utc)
    session.add(project)
    _commit_ingestion_session(session)

    chapter_count = session.query(Chapter).filter(Chapter.project_id == project_id).count()
    return IngestResponse(
        project_id=project_id,
        chapter_count=chapter_count,
        warnings=warnings,
        normalization_report=normalization_report,
    )


@app.post(
    "/api/projects/{project_id}/ingest/jobs",
    response_model=ProjectIngestionJobStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_project_ingestion_job(
    project_id: int,
    source: str = Form(...),
    file: UploadFile | None = File(default=None),
    files: list[UploadFile] | None = File(default=None),
    session: Session = Depends(get_session),
) -> ProjectIngestionJobStartResponse:
    _get_project_or_404(session, project_id)
    normalized_source = str(source).strip().lower()
    if normalized_source == "directory":
        normalized_source = "chapters-dir"
    if normalized_source not in PROJECT_INGESTION_ALLOWED_SOURCES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source must be one of: txt, markdown, epub, chapters-dir, append-chapter",
        )

    existing_active_job = (
        session.query(ProjectIngestionJob)
        .filter(
            ProjectIngestionJob.project_id == project_id,
            ProjectIngestionJob.status.in_(
                [
                    PROJECT_INGESTION_JOB_STATUS_QUEUED,
                    PROJECT_INGESTION_JOB_STATUS_RUNNING,
                ]
            ),
        )
        .order_by(ProjectIngestionJob.created_at.desc(), ProjectIngestionJob.id.desc())
        .first()
    )
    if existing_active_job is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Ingestion is already running for this project. "
                f"Wait for job {existing_active_job.job_id} to complete before starting a new upload."
            ),
        )

    selected_files: list[UploadFile] = []
    if normalized_source == "chapters-dir":
        selected_files.extend(files or [])
        if file is not None:
            selected_files.append(file)
        if not selected_files:
            raise MissingChaptersIngestionError(detail="At least one chapter file is required")
    else:
        selected_file = file
        if selected_file is None and files:
            selected_file = files[0]
        if selected_file is None:
            raise MissingChaptersIngestionError(detail="A source file is required")
        selected_files.append(selected_file)

    file_payload_rows: list[tuple[int, str, str | None, bytes]] = []
    for file_index, upload in enumerate(selected_files):
        file_payload_rows.append(
            (
                file_index,
                str(upload.filename or "").strip() or f"upload-{file_index + 1}.txt",
                str(upload.content_type).strip() if upload.content_type else None,
                upload.file.read(),
            )
        )

    request_payload = {
        "source": normalized_source,
        "file_count": len(file_payload_rows),
        "filenames": [row[1] for row in file_payload_rows],
    }
    job_row = ProjectIngestionJob(
        job_id=uuid4().hex,
        project_id=project_id,
        source=normalized_source,
        status=PROJECT_INGESTION_JOB_STATUS_QUEUED,
        progress=0,
        message="Queued for ingestion",
        executor_name="thread",
        task_id=None,
        request_payload_json=request_payload,
        result_payload_json=None,
        error_message=None,
    )
    session.add(job_row)
    session.flush()

    for file_index, filename, content_type, payload_blob in file_payload_rows:
        session.add(
            ProjectIngestionJobFile(
                job_id=job_row.id,
                file_index=file_index,
                filename=filename,
                content_type=content_type,
                payload_blob=payload_blob,
            )
        )

    session.commit()
    session.refresh(job_row)

    executor_name, task_id = _dispatch_project_ingestion_job(job_row.job_id)
    job_row.executor_name = executor_name
    job_row.task_id = task_id
    session.add(job_row)
    session.commit()
    session.refresh(job_row)

    return ProjectIngestionJobStartResponse(
        project_id=job_row.project_id,
        source=job_row.source,
        job_id=job_row.job_id,
        status=job_row.status,
        executor_name=job_row.executor_name,
        task_id=job_row.task_id,
        created_at=job_row.created_at,
    )


@app.get(
    "/api/projects/{project_id}/ingest/jobs/{job_id}",
    response_model=ProjectIngestionJobStatusResponse,
    status_code=status.HTTP_200_OK,
)
def get_project_ingestion_job_status(
    project_id: int,
    job_id: str,
    session: Session = Depends(get_session),
) -> ProjectIngestionJobStatusResponse:
    _get_project_or_404(session, project_id)
    normalized_job_id = str(job_id).strip()
    if not normalized_job_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="job_id must not be blank.",
        )

    job_row = (
        session.query(ProjectIngestionJob)
        .filter(
            ProjectIngestionJob.project_id == project_id,
            ProjectIngestionJob.job_id == normalized_job_id,
        )
        .one_or_none()
    )
    if job_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project ingestion job not found.",
        )

    return _build_project_ingestion_job_status_response(job_row)


@app.post(
    "/api/projects/{project_id}/characters/import",
    response_model=CharacterImportResponse,
    status_code=status.HTTP_200_OK,
)
def import_characters(
    project_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> CharacterImportResponse:
    project = _get_project_or_404(session, project_id)

    payload = file.file.read()
    try:
        parsed = parse_character_file(file.filename or "characters.json", payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    session.query(Character).filter(Character.project_id == project_id).delete()
    session.query(CharacterProposal).filter(
        CharacterProposal.project_id == project_id,
        CharacterProposal.status == "proposed",
    ).delete()

    for row in parsed:
        session.add(
            Character(
                project_id=project_id,
                name=row.name,
                verbalized_form=row.verbalized_form,
                gender=row.gender,
                aliases=row.aliases,
                notes=row.notes,
                source=row.source,
                confidence=row.confidence,
                voice_id=row.voice_id,
                inferred_gender=row.inferred_gender,
                inferred_confidence=row.inferred_confidence,
                inferred_source_trace=row.inferred_source_trace,
            )
        )
    project.character_map_finalized = False
    session.add(project)
    project_runs = session.query(Run).filter(Run.project_id == project.id).all()
    mark_runs_stale_for_gender_edit(project_runs)
    recompute_voice_previews_for_runs(session, project=project, runs=project_runs)
    session.add(
        _persist_character_map_snapshot(
            session=session,
            project_id=project_id,
            source="import",
        )
    )
    session.add(
        _persist_voice_map_snapshot(
            session=session,
            project_id=project_id,
            source="import",
        )
    )

    session.commit()

    return CharacterImportResponse(project_id=project_id, imported_count=len(parsed))


@app.get(
    "/api/projects/{project_id}/characters",
    response_model=CharacterMapResponse,
    status_code=status.HTTP_200_OK,
)
def list_characters(
    project_id: int,
    session: Session = Depends(get_session),
) -> CharacterMapResponse:
    project = _get_project_or_404(session, project_id)

    character_rows = (
        session.query(Character)
        .filter(Character.project_id == project_id)
        .order_by(Character.name.asc())
        .all()
    )
    return CharacterMapResponse(
        project_id=project_id,
        character_map_finalized=project.character_map_finalized,
        characters=[
            _build_character_map_item_payload_from_row(character)
            for character in character_rows
        ],
    )


@app.get(
    "/api/projects/{project_id}/characters/proposals",
    response_model=CharacterProposalListResponse,
    status_code=status.HTTP_200_OK,
)
def list_character_proposals(
    project_id: int,
    statuses: str | None = Query(default="proposed"),
    session: Session = Depends(get_session),
) -> CharacterProposalListResponse:
    _get_project_or_404(session, project_id)

    allowed_statuses = {"proposed", "approved", "rejected"}
    selected_statuses = {
        status_value.strip().lower()
        for status_value in (statuses or "").split(",")
        if status_value.strip()
    }
    if not selected_statuses:
        selected_statuses = {"proposed"}
    invalid_statuses = sorted(selected_statuses - allowed_statuses)
    if invalid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Invalid statuses requested. Supported values are: proposed, approved, rejected. "
                f"Invalid values: {', '.join(invalid_statuses)}"
            ),
        )

    proposal_rows = (
        session.query(CharacterProposal)
        .filter(
            CharacterProposal.project_id == project_id,
            CharacterProposal.status.in_(sorted(selected_statuses)),
        )
        .order_by(CharacterProposal.created_at.desc(), CharacterProposal.id.desc())
        .all()
    )

    proposal_items = [_build_character_proposal_item_payload_from_row(row) for row in proposal_rows]
    return CharacterProposalListResponse(
        project_id=project_id,
        proposal_count=len(proposal_items),
        proposals=proposal_items,
    )


@app.post(
    "/api/projects/{project_id}/characters/proposals/review",
    response_model=CharacterProposalReviewResponse,
    status_code=status.HTTP_200_OK,
)
def review_character_proposals(
    project_id: int,
    payload: CharacterProposalReviewRequest,
    session: Session = Depends(get_session),
) -> CharacterProposalReviewResponse:
    project = _get_project_or_404(session, project_id)

    approve_ids = set(payload.approve_ids)
    reject_ids = set(payload.reject_ids) - approve_ids
    selected_ids = sorted(approve_ids | reject_ids)
    if not selected_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one proposal ID must be provided in approve_ids or reject_ids.",
        )

    proposal_rows = (
        session.query(CharacterProposal)
        .filter(
            CharacterProposal.project_id == project_id,
            CharacterProposal.id.in_(selected_ids),
        )
        .all()
    )
    found_ids = {row.id for row in proposal_rows}
    missing_ids = [proposal_id for proposal_id in selected_ids if proposal_id not in found_ids]
    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Character proposal IDs not found for this project: {', '.join(str(value) for value in missing_ids)}",
        )

    reviewed_at = datetime.now(timezone.utc)
    reviewed_by = payload.reviewed_by.strip() if payload.reviewed_by else "user"
    approved_rows: list[CharacterProposal] = []
    rejected_rows: list[CharacterProposal] = []
    for row in proposal_rows:
        if row.id in approve_ids:
            row.status = "approved"
            approved_rows.append(row)
        elif row.id in reject_ids:
            row.status = "rejected"
            rejected_rows.append(row)
        else:
            continue
        row.reviewed_at = reviewed_at
        row.reviewed_by = reviewed_by
        session.add(row)

    approved_count = len(approved_rows)
    rejected_count = len(rejected_rows)
    if approved_count > 0:
        existing_rows = (
            session.query(Character)
            .filter(Character.project_id == project_id)
            .order_by(Character.name.asc())
            .all()
        )
        merged_payloads = merge_character_candidates(
            [
                _build_character_map_item_payload(
                    row=row,
                    source=row.source,
                    confidence=row.confidence,
                    source_trace=[],
                )
                for row in existing_rows
            ]
            + [_build_character_payload_from_proposal(row) for row in approved_rows]
        )

        session.query(Character).filter(Character.project_id == project_id).delete()
        for row in merged_payloads:
            session.add(
                Character(
                    project_id=project_id,
                    name=str(row.get("name") or "").strip(),
                    verbalized_form=str(row.get("verbalized_form") or row.get("name") or "").strip(),
                    gender=str(row.get("gender") or "unknown").strip().lower() or "unknown",
                    aliases=list(row.get("aliases") or []),
                    notes=(str(row.get("notes")).strip() if row.get("notes") is not None else None),
                    source=str(row.get("source") or "auto").strip() or "auto",
                    confidence=float(row.get("confidence") or 0.0),
                    inferred_gender=str(row.get("inferred_gender") or "unknown").strip().lower() or "unknown",
                    inferred_confidence=float(row.get("inferred_confidence") or 0.0),
                    inferred_source_trace=list(row.get("inferred_source_trace") or []),
                )
            )

        project.character_map_finalized = False
        project_runs = session.query(Run).filter(Run.project_id == project.id).all()
        mark_runs_stale_for_gender_edit(project_runs)
        recompute_voice_previews_for_runs(session, project=project, runs=project_runs)
        session.add(project)
        session.add(
            _persist_character_map_snapshot(
                session=session,
                project_id=project_id,
                source="proposal_review",
            )
        )
        session.add(
            _persist_voice_map_snapshot(
                session=session,
                project_id=project_id,
                source="proposal_review",
            )
        )

    session.commit()

    character_rows = (
        session.query(Character)
        .filter(Character.project_id == project_id)
        .order_by(Character.name.asc())
        .all()
    )
    proposal_rows = (
        session.query(CharacterProposal)
        .filter(
            CharacterProposal.project_id == project_id,
            CharacterProposal.status == "proposed",
        )
        .order_by(CharacterProposal.created_at.desc(), CharacterProposal.id.desc())
        .all()
    )

    return CharacterProposalReviewResponse(
        project_id=project_id,
        approved_count=approved_count,
        rejected_count=rejected_count,
        character_map_finalized=project.character_map_finalized,
        characters=[_build_character_map_item_payload_from_row(row) for row in character_rows],
        proposal_count=len(proposal_rows),
        proposals=[_build_character_proposal_item_payload_from_row(row) for row in proposal_rows],
    )


@app.post(
    "/api/projects/{project_id}/characters/finalize",
    response_model=CharacterMapFinalizeResponse,
    status_code=status.HTTP_200_OK,
)
def finalize_character_map(project_id: int, session: Session = Depends(get_session)) -> CharacterMapFinalizeResponse:
    project = _get_project_or_404(session, project_id)
    project.character_map_finalized = True
    session.add(project)
    session.commit()
    session.refresh(project)

    return CharacterMapFinalizeResponse(
        project_id=project.id,
        character_map_finalized=project.character_map_finalized,
    )


def _build_project_ingestion_job_status_response(
    row: ProjectIngestionJob,
) -> ProjectIngestionJobStatusResponse:
    ingestion_result: IngestResponse | None = None
    if row.status == PROJECT_INGESTION_JOB_STATUS_COMPLETED and isinstance(row.result_payload_json, dict):
        try:
            ingestion_result = IngestResponse(**row.result_payload_json)
        except Exception:  # noqa: BLE001
            ingestion_result = None

    return ProjectIngestionJobStatusResponse(
        project_id=row.project_id,
        source=row.source,
        job_id=row.job_id,
        status=row.status,
        progress=max(0, min(int(row.progress), 100)),
        message=row.message,
        executor_name=row.executor_name,
        task_id=row.task_id,
        error_message=row.error_message,
        result=ingestion_result,
        created_at=row.created_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
        updated_at=row.updated_at,
    )


def _update_project_ingestion_job_state(
    *,
    job_id: str,
    status_value: str | None = None,
    progress_value: int | None = None,
    message_value: str | None = None,
    error_message_value: str | None = None,
    result_payload_json: dict[str, object] | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> None:
    update_session = get_session_factory()()
    try:
        job_row = (
            update_session.query(ProjectIngestionJob)
            .filter(ProjectIngestionJob.job_id == job_id)
            .one_or_none()
        )
        if job_row is None:
            return

        if status_value is not None:
            job_row.status = status_value
        if progress_value is not None:
            job_row.progress = max(0, min(int(progress_value), 100))
        if message_value is not None:
            job_row.message = message_value[:255] if message_value else None
        if error_message_value is not None:
            job_row.error_message = error_message_value.strip() or None
        if result_payload_json is not None:
            job_row.result_payload_json = dict(result_payload_json)
        if started_at is not None:
            job_row.started_at = started_at
        if finished_at is not None:
            job_row.finished_at = finished_at

        job_row.updated_at = datetime.now(timezone.utc)
        update_session.add(job_row)
        update_session.commit()
    finally:
        update_session.close()


def _run_project_ingestion_pipeline(
    *,
    session: Session,
    project_id: int,
    source: str,
    upload_files: list[UploadFile],
    progress_callback: Callable[[int, str], None] | None,
) -> IngestResponse:
    def _report(progress: int, message: str) -> None:
        if progress_callback is None:
            return
        progress_callback(max(0, min(progress, 100)), message.strip())

    _report(8, "Validating source payload")
    if source == "txt":
        if not upload_files:
            raise MissingChaptersIngestionError(detail="A TXT file is required")
        _report(35, "Parsing TXT source")
        response = ingest_txt(project_id=project_id, file=upload_files[0], session=session)
    elif source == "markdown":
        if not upload_files:
            raise MissingChaptersIngestionError(detail="A Markdown file is required")
        _report(35, "Parsing Markdown source")
        response = ingest_markdown(project_id=project_id, file=upload_files[0], session=session)
    elif source == "epub":
        if not upload_files:
            raise MissingChaptersIngestionError(detail="An EPUB file is required")
        _report(35, "Parsing EPUB source")
        response = ingest_epub(project_id=project_id, file=upload_files[0], session=session)
    elif source == "chapters-dir":
        if not upload_files:
            raise MissingChaptersIngestionError(detail="At least one chapter file is required")
        _report(35, "Parsing chapter directory")
        response = ingest_chapters_dir(project_id=project_id, files=upload_files, session=session)
    elif source == "append-chapter":
        if not upload_files:
            raise MissingChaptersIngestionError(detail="A chapter file is required")
        _report(35, "Appending chapter")
        response = append_chapter(project_id=project_id, file=upload_files[0], session=session)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported ingestion source: {source}",
        )

    _report(95, "Finalizing ingestion result")
    return response


def run_project_ingestion_job_by_id(job_id: str) -> None:
    normalized_job_id = str(job_id).strip()
    if not normalized_job_id:
        return

    worker_session = get_session_factory()()
    upload_files: list[UploadFile] = []
    try:
        job_row = (
            worker_session.query(ProjectIngestionJob)
            .filter(ProjectIngestionJob.job_id == normalized_job_id)
            .one_or_none()
        )
        if job_row is None:
            return
        if job_row.status in {
            PROJECT_INGESTION_JOB_STATUS_RUNNING,
            PROJECT_INGESTION_JOB_STATUS_COMPLETED,
        }:
            return

        _update_project_ingestion_job_state(
            job_id=normalized_job_id,
            status_value=PROJECT_INGESTION_JOB_STATUS_RUNNING,
            progress_value=3,
            message_value="Starting ingestion",
            error_message_value="",
            started_at=datetime.now(timezone.utc),
        )

        file_rows = (
            worker_session.query(ProjectIngestionJobFile)
            .filter(ProjectIngestionJobFile.job_id == job_row.id)
            .order_by(ProjectIngestionJobFile.file_index.asc())
            .all()
        )
        for file_row in file_rows:
            upload_files.append(
                UploadFile(
                    filename=(str(file_row.filename or "").strip() or "upload.txt"),
                    file=io.BytesIO(bytes(file_row.payload_blob or b"")),
                )
            )

        ingestion_result = _run_project_ingestion_pipeline(
            session=worker_session,
            project_id=job_row.project_id,
            source=job_row.source,
            upload_files=upload_files,
            progress_callback=lambda progress, message: _update_project_ingestion_job_state(
                job_id=normalized_job_id,
                status_value=PROJECT_INGESTION_JOB_STATUS_RUNNING,
                progress_value=progress,
                message_value=message,
            ),
        )
        _update_project_ingestion_job_state(
            job_id=normalized_job_id,
            status_value=PROJECT_INGESTION_JOB_STATUS_COMPLETED,
            progress_value=100,
            message_value="Ingestion completed",
            error_message_value="",
            result_payload_json=ingestion_result.model_dump(mode="json"),
            finished_at=datetime.now(timezone.utc),
        )
    except Exception as exc:  # noqa: BLE001
        worker_session.rollback()
        if isinstance(exc, HTTPException):
            detail = str(exc.detail)
        else:
            detail = str(exc)
        _update_project_ingestion_job_state(
            job_id=normalized_job_id,
            status_value=PROJECT_INGESTION_JOB_STATUS_FAILED,
            progress_value=100,
            message_value="Ingestion failed",
            error_message_value=detail[:4000],
            finished_at=datetime.now(timezone.utc),
        )
    finally:
        for upload_file in upload_files:
            try:
                upload_file.file.close()
            except Exception:  # noqa: BLE001
                pass
        worker_session.close()


def _dispatch_project_ingestion_job(job_id: str) -> tuple[str, str | None]:
    settings = get_settings()
    preferred_executor = str(settings.ingestion_async_executor or "thread").strip().lower()
    if (
        preferred_executor == "celery"
        and is_celery_available()
        and celery_app is not None
    ):
        try:
            async_result = celery_app.send_task(
                "project_ingestion.execute_job",
                kwargs={"job_id": job_id},
            )
            task_id = str(getattr(async_result, "id", "")).strip() or None
            return ("celery", task_id)
        except Exception:  # noqa: BLE001
            pass

    worker = Thread(
        target=run_project_ingestion_job_by_id,
        args=(job_id,),
        daemon=True,
        name=f"project-ingestion-{job_id[:10]}",
    )
    worker.start()
    return ("thread", None)


def run_pipeline_run_by_id(
    run_id: int,
    *,
    principal_type: str | None = None,
    principal_id: str | None = None,
) -> None:
    try:
        normalized_run_id = int(run_id)
    except (TypeError, ValueError):
        return
    if normalized_run_id <= 0:
        return

    worker_session = get_session_factory()()
    try:
        run = worker_session.query(Run).filter(Run.id == normalized_run_id).one_or_none()
        if run is None:
            return
        if run.status in {RUN_STATUS_COMPLETED, RUN_STATUS_FAILED, RUN_STATUS_CANCELLED}:
            return

        project = worker_session.query(Project).filter(Project.id == run.project_id).one_or_none()
        if project is None:
            return

        if run.status == RUN_STATUS_QUEUED:
            run.status = RUN_STATUS_RUNNING
            if run.started_at is None:
                run.started_at = datetime.now(timezone.utc)
            run.finished_at = None
            worker_session.add(run)
            worker_session.commit()
            worker_session.refresh(run)

        try:
            _execute_pipeline_and_finalize_run(
                session=worker_session,
                project=project,
                run=run,
                principal_type=principal_type,
                principal_id=principal_id,
            )
        except HTTPException:
            return
    finally:
        worker_session.close()


def _dispatch_pipeline_run_execution(
    *,
    run_id: int,
    principal_type: str | None,
    principal_id: str | None,
) -> tuple[str, str | None]:
    settings = get_settings()
    preferred_executor = str(settings.pipeline_async_executor or "thread").strip().lower()
    if (
        preferred_executor == "celery"
        and is_celery_available()
        and celery_app is not None
    ):
        try:
            async_result = celery_app.send_task(
                "pipeline.execute_run",
                kwargs={
                    "run_id": int(run_id),
                    "principal_type": principal_type,
                    "principal_id": principal_id,
                },
            )
            task_id = str(getattr(async_result, "id", "")).strip() or None
            return ("celery", task_id)
        except Exception:  # noqa: BLE001
            pass

    worker = Thread(
        target=run_pipeline_run_by_id,
        args=(int(run_id),),
        kwargs={
            "principal_type": principal_type,
            "principal_id": principal_id,
        },
        daemon=True,
        name=f"pipeline-run-{int(run_id)}",
    )
    worker.start()
    return ("thread", None)


def _execute_character_extraction_pipeline(
    *,
    session: Session,
    project: Project,
    project_id: int,
    extraction_config: CharacterExtractionRequest,
    progress_callback: Callable[[int, str], None] | None,
) -> CharacterExtractionResponse:
    def _report(progress: int, message: str) -> None:
        if progress_callback is None:
            return
        progress_callback(max(0, min(progress, 100)), message.strip())

    _report(5, "Loading chapters")
    chapter_rows = (
        session.query(Chapter.chapter_index, Chapter.normalized_text)
        .filter(Chapter.project_id == project_id)
        .order_by(Chapter.chapter_index.asc())
        .all()
    )
    if not chapter_rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No chapters available for character auto-extraction.",
        )

    _report(15, "Collecting existing canonical names")
    existing_name_keys = {
        normalize_candidate_key(row.name)
        for row in session.query(Character.name).filter(Character.project_id == project_id).all()
        if str(row.name or "").strip()
    }

    _report(35, "Extracting candidates")
    llm_first_result = _extract_character_candidates_llm_first(
        session=session,
        project=project,
        project_id=project_id,
        chapter_rows=[(int(row.chapter_index), str(row.normalized_text or "")) for row in chapter_rows],
        existing_name_keys=existing_name_keys,
        config=extraction_config,
    )
    if llm_first_result is None:
        _report(50, "Running deterministic fallback extraction")
        candidates = extract_character_candidates_from_texts(
            [str(row.normalized_text or "") for row in chapter_rows],
            known_names=existing_name_keys,
            min_confidence=extraction_config.min_confidence,
            max_candidates=extraction_config.max_candidates,
        )
        raw_candidate_payloads = _build_mergeable_candidates_from_candidates(
            candidates,
            source="auto",
        )
        candidate_payloads = merge_character_candidates(raw_candidate_payloads)
        candidate_payloads = _refine_character_payloads_with_llm(
            project_id=project_id,
            payloads=candidate_payloads,
            config=extraction_config,
        )
        candidate_payloads = merge_character_candidates(candidate_payloads)
    else:
        raw_candidate_payloads, candidate_payloads = llm_first_result

    extraction_batch_id: str | None = None
    proposal_count = 0
    auto_applied_count = 0
    if extraction_config.persist_proposals:
        _report(75, "Persisting extraction proposals")
        extraction_batch_id = uuid4().hex
        proposal_rows = _persist_character_proposals(
            session=session,
            project_id=project_id,
            candidate_payloads=candidate_payloads,
            extraction_batch_id=extraction_batch_id,
            replace_existing_proposed=True,
        )
        proposal_count = len(proposal_rows)

    if extraction_config.auto_apply_to_character_map:
        _report(88, "Applying high-confidence candidates")
        auto_applied_count = _auto_apply_character_candidates(
            session=session,
            project_id=project_id,
            candidate_payloads=candidate_payloads,
            min_confidence=extraction_config.auto_apply_min_confidence,
        )

    if extraction_config.persist_proposals or auto_applied_count > 0:
        session.commit()

    _report(95, "Building extraction response")
    mapped_candidates = [
        CharacterMapItem(**candidate_payload)
        for candidate_payload in candidate_payloads
    ]
    warnings = _build_character_extraction_warnings(
        canonical_payloads=candidate_payloads,
        candidate_payloads=raw_candidate_payloads,
        source="characters.extract",
    )

    return CharacterExtractionResponse(
        project_id=project_id,
        status="complete",
        candidate_count=len(mapped_candidates),
        auto_applied_count=auto_applied_count,
        candidates=mapped_candidates,
        extraction_batch_id=extraction_batch_id,
        proposal_count=proposal_count,
        proposed_characters=mapped_candidates,
        warnings=warnings,
    )


def _build_character_extraction_job_status_response(
    row: CharacterExtractionJob,
) -> CharacterExtractionJobStatusResponse:
    extraction_result: CharacterExtractionResponse | None = None
    if row.status == CHARACTER_EXTRACTION_JOB_STATUS_COMPLETED and isinstance(row.result_payload_json, dict):
        try:
            extraction_result = CharacterExtractionResponse(**row.result_payload_json)
        except Exception:  # noqa: BLE001
            extraction_result = None

    return CharacterExtractionJobStatusResponse(
        project_id=row.project_id,
        job_id=row.job_id,
        status=row.status,
        progress=max(0, min(int(row.progress), 100)),
        message=row.message,
        executor_name=row.executor_name,
        task_id=row.task_id,
        error_message=row.error_message,
        result=extraction_result,
        created_at=row.created_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
        updated_at=row.updated_at,
    )


def _update_character_extraction_job_state(
    *,
    job_id: str,
    status_value: str | None = None,
    progress_value: int | None = None,
    message_value: str | None = None,
    error_message_value: str | None = None,
    result_payload_json: dict[str, object] | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> None:
    update_session = get_session_factory()()
    try:
        job_row = (
            update_session.query(CharacterExtractionJob)
            .filter(CharacterExtractionJob.job_id == job_id)
            .one_or_none()
        )
        if job_row is None:
            return

        if status_value is not None:
            job_row.status = status_value
        if progress_value is not None:
            job_row.progress = max(0, min(int(progress_value), 100))
        if message_value is not None:
            job_row.message = message_value[:255] if message_value else None
        if error_message_value is not None:
            job_row.error_message = error_message_value.strip() or None
        if result_payload_json is not None:
            job_row.result_payload_json = dict(result_payload_json)
        if started_at is not None:
            job_row.started_at = started_at
        if finished_at is not None:
            job_row.finished_at = finished_at

        job_row.updated_at = datetime.now(timezone.utc)
        update_session.add(job_row)
        update_session.commit()
    finally:
        update_session.close()


def run_character_extraction_job_by_id(job_id: str) -> None:
    normalized_job_id = str(job_id).strip()
    if not normalized_job_id:
        return

    worker_session = get_session_factory()()
    try:
        job_row = (
            worker_session.query(CharacterExtractionJob)
            .filter(CharacterExtractionJob.job_id == normalized_job_id)
            .one_or_none()
        )
        if job_row is None:
            return
        if job_row.status in {
            CHARACTER_EXTRACTION_JOB_STATUS_RUNNING,
            CHARACTER_EXTRACTION_JOB_STATUS_COMPLETED,
        }:
            return

        request_payload = dict(job_row.request_payload_json or {})
        project = worker_session.query(Project).filter(Project.id == job_row.project_id).one_or_none()
        if project is None:
            raise ValueError("Project not found for extraction job.")

        extraction_config = CharacterExtractionRequest(**request_payload)
        _update_character_extraction_job_state(
            job_id=normalized_job_id,
            status_value=CHARACTER_EXTRACTION_JOB_STATUS_RUNNING,
            progress_value=3,
            message_value="Starting extraction",
            error_message_value="",
            started_at=datetime.now(timezone.utc),
        )

        extraction_result = _execute_character_extraction_pipeline(
            session=worker_session,
            project=project,
            project_id=job_row.project_id,
            extraction_config=extraction_config,
            progress_callback=lambda progress, message: _update_character_extraction_job_state(
                job_id=normalized_job_id,
                status_value=CHARACTER_EXTRACTION_JOB_STATUS_RUNNING,
                progress_value=progress,
                message_value=message,
            ),
        )
        _update_character_extraction_job_state(
            job_id=normalized_job_id,
            status_value=CHARACTER_EXTRACTION_JOB_STATUS_COMPLETED,
            progress_value=100,
            message_value="Character extraction completed",
            error_message_value="",
            result_payload_json=extraction_result.model_dump(mode="json"),
            finished_at=datetime.now(timezone.utc),
        )
    except Exception as exc:  # noqa: BLE001
        worker_session.rollback()
        if isinstance(exc, HTTPException):
            detail = str(exc.detail)
        else:
            detail = str(exc)
        _update_character_extraction_job_state(
            job_id=normalized_job_id,
            status_value=CHARACTER_EXTRACTION_JOB_STATUS_FAILED,
            progress_value=100,
            message_value="Character extraction failed",
            error_message_value=detail[:4000],
            finished_at=datetime.now(timezone.utc),
        )
    finally:
        worker_session.close()


def _dispatch_character_extraction_job(job_id: str) -> tuple[str, str | None]:
    settings = get_settings()
    preferred_executor = str(settings.character_extraction_async_executor or "thread").strip().lower()
    if (
        preferred_executor == "celery"
        and is_celery_available()
        and celery_app is not None
    ):
        try:
            async_result = celery_app.send_task(
                "character_extraction.execute_job",
                kwargs={"job_id": job_id},
            )
            task_id = str(getattr(async_result, "id", "")).strip() or None
            return ("celery", task_id)
        except Exception:  # noqa: BLE001
            pass

    worker = Thread(
        target=run_character_extraction_job_by_id,
        args=(job_id,),
        daemon=True,
        name=f"character-extraction-{job_id[:10]}",
    )
    worker.start()
    return ("thread", None)


@app.post(
    "/api/projects/{project_id}/characters/extract/jobs",
    response_model=CharacterExtractionJobStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_character_extraction_job(
    project_id: int,
    payload: CharacterExtractionRequest | None = None,
    session: Session = Depends(get_session),
) -> CharacterExtractionJobStartResponse:
    _get_project_or_404(session, project_id)
    extraction_config = payload or CharacterExtractionRequest()

    job_row = CharacterExtractionJob(
        job_id=uuid4().hex,
        project_id=project_id,
        status=CHARACTER_EXTRACTION_JOB_STATUS_QUEUED,
        progress=0,
        message="Queued for extraction",
        executor_name="thread",
        task_id=None,
        request_payload_json=extraction_config.model_dump(mode="json"),
        result_payload_json=None,
        error_message=None,
    )
    session.add(job_row)
    session.commit()
    session.refresh(job_row)

    executor_name, task_id = _dispatch_character_extraction_job(job_row.job_id)
    job_row.executor_name = executor_name
    job_row.task_id = task_id
    session.add(job_row)
    session.commit()
    session.refresh(job_row)

    return CharacterExtractionJobStartResponse(
        project_id=job_row.project_id,
        job_id=job_row.job_id,
        status=job_row.status,
        executor_name=job_row.executor_name,
        task_id=job_row.task_id,
        created_at=job_row.created_at,
    )


@app.get(
    "/api/projects/{project_id}/characters/extract/jobs/{job_id}",
    response_model=CharacterExtractionJobStatusResponse,
    status_code=status.HTTP_200_OK,
)
def get_character_extraction_job_status(
    project_id: int,
    job_id: str,
    session: Session = Depends(get_session),
) -> CharacterExtractionJobStatusResponse:
    _get_project_or_404(session, project_id)
    normalized_job_id = str(job_id).strip()
    if not normalized_job_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="job_id must not be blank.",
        )

    job_row = (
        session.query(CharacterExtractionJob)
        .filter(
            CharacterExtractionJob.project_id == project_id,
            CharacterExtractionJob.job_id == normalized_job_id,
        )
        .one_or_none()
    )
    if job_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character extraction job not found.",
        )

    return _build_character_extraction_job_status_response(job_row)


@app.post(
    "/api/projects/{project_id}/characters/extract",
    response_model=CharacterExtractionResponse,
    status_code=status.HTTP_200_OK,
)
def auto_extract_characters(
    project_id: int,
    payload: CharacterExtractionRequest | None = None,
    session: Session = Depends(get_session),
) -> CharacterExtractionResponse:
    project = _get_project_or_404(session, project_id)
    extraction_config = payload or CharacterExtractionRequest()
    return _execute_character_extraction_pipeline(
        session=session,
        project=project,
        project_id=project_id,
        extraction_config=extraction_config,
        progress_callback=None,
    )


@app.post(
    "/api/projects/{project_id}/characters/scrape",
    response_model=CharacterExtractionResponse,
    status_code=status.HTTP_200_OK,
)
def scrape_characters(
    project_id: int,
    payload: CharacterScrapeRequest,
    session: Session = Depends(get_session),
) -> CharacterExtractionResponse:
    _get_project_or_404(session, project_id)

    if not payload.acknowledge_source_risk:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must acknowledge scrape risk before proceeding.",
        )

    existing_names = {
        row.name.strip().lower()
        for row in session.query(Character.name).filter(Character.project_id == project_id).all()
    }

    try:
        candidates = extract_character_candidates_from_scrape_url(
            payload.source_url,
            known_names=existing_names,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    candidate_payloads = _build_mergeable_candidates_from_candidates(
        candidates,
        source="scrape",
    )
    mapped_candidates = [
        CharacterMapItem(**candidate_payload)
        for candidate_payload in candidate_payloads
    ]
    warnings = _build_character_extraction_warnings(
        canonical_payloads=candidate_payloads,
        candidate_payloads=candidate_payloads,
        source="characters.scrape",
    )

    return CharacterExtractionResponse(
        project_id=project_id,
        status="complete",
        candidate_count=len(mapped_candidates),
        candidates=mapped_candidates,
        warnings=warnings,
    )


@app.post(
    "/api/projects/{project_id}/characters/merged-candidates",
    response_model=CharacterExtractionResponse,
    status_code=status.HTTP_200_OK,
)
def merged_candidate_characters(
    project_id: int,
    payload: CharacterCandidatesMergeRequest,
    session: Session = Depends(get_session),
) -> CharacterExtractionResponse:
    _get_project_or_404(session, project_id)

    merged_payloads: list[dict[str, object]] = []
    proposed_source_payloads: list[dict[str, object]] = []
    existing_character_rows = (
        session.query(Character)
        .filter(Character.project_id == project_id)
        .order_by(Character.name.asc())
        .all()
    )
    canonical_name_keys = {normalize_candidate_key(row.name) for row in existing_character_rows if row.name.strip()}

    merged_payloads.extend(
        [
            _build_character_map_item_payload(
                row=row,
                source=row.source,
                confidence=row.confidence,
                source_trace=[],
            )
            for row in existing_character_rows
        ]
    )

    if payload.include_auto:
        chapter_rows = (
            session.query(Chapter.normalized_text)
            .filter(Chapter.project_id == project_id)
            .order_by(Chapter.chapter_index.asc())
            .all()
        )
        if chapter_rows:
            auto_candidates = extract_character_candidates_from_texts([row.normalized_text for row in chapter_rows])
            auto_payloads = _build_mergeable_candidates_from_candidates(
                candidates=auto_candidates,
                source="auto",
            )
            merged_payloads.extend(auto_payloads)
            proposed_source_payloads.extend(auto_payloads)

    if payload.source_url is not None:
        if not payload.acknowledge_source_risk:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You must acknowledge scrape risk before proceeding.",
            )
        try:
            scrape_candidates = extract_character_candidates_from_scrape_url(payload.source_url)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        scrape_payloads = _build_mergeable_candidates_from_candidates(
            candidates=scrape_candidates,
            source="scrape",
        )
        merged_payloads.extend(scrape_payloads)
        proposed_source_payloads.extend(scrape_payloads)

    warnings = _build_character_extraction_warnings(
        canonical_payloads=merged_payloads,
        candidate_payloads=proposed_source_payloads,
        source="characters.merged-candidates",
    )
    merged_candidates = [CharacterMapItem(**payload) for payload in merge_character_candidates(merged_payloads)]
    proposed_candidates = [CharacterMapItem(**payload) for payload in _filter_new_character_payloads(
        payloads=proposed_source_payloads,
        canonical_name_keys=canonical_name_keys,
    )]
    canonical_merge_suggestions = build_canonical_name_merge_suggestions(
        candidate_payloads=merged_payloads,
        canonical_names={row.name for row in existing_character_rows},
    )

    return CharacterExtractionResponse(
        project_id=project_id,
        status="complete",
        candidate_count=len(merged_candidates),
        candidates=merged_candidates,
        proposed_characters=proposed_candidates,
        canonical_merge_suggestions=canonical_merge_suggestions,
        warnings=warnings,
    )


@app.put(
    "/api/projects/{project_id}/characters",
    response_model=CharacterMapResponse,
    status_code=status.HTTP_200_OK,
)
def upsert_characters(
    project_id: int,
    payload: CharacterMapUpdateRequest,
    session: Session = Depends(get_session),
) -> CharacterMapResponse:
    project = _get_project_or_404(session, project_id)

    deduped: dict[str, CharacterMapItem] = {}
    for row in payload.characters:
        deduped[row.name.strip().lower()] = row

    session.query(Character).filter(Character.project_id == project_id).delete()
    session.query(CharacterProposal).filter(
        CharacterProposal.project_id == project_id,
        CharacterProposal.status == "proposed",
    ).delete()
    for row in deduped.values():
        session.add(
            Character(
                project_id=project_id,
                name=row.name.strip(),
                verbalized_form=row.verbalized_form.strip(),
                gender=row.gender.strip().lower(),
                voice_id=(row.voice_id.strip() if row.voice_id else None),
                aliases=row.aliases,
                notes=row.notes and row.notes.strip() or None,
                source=row.source,
                confidence=row.confidence,
                inferred_gender=row.inferred_gender,
                inferred_confidence=row.inferred_confidence,
                inferred_source_trace=row.inferred_source_trace,
            )
        )
    project.character_map_finalized = False
    project_runs = session.query(Run).filter(Run.project_id == project.id).all()
    mark_runs_stale_for_gender_edit(project_runs)
    recompute_voice_previews_for_runs(session, project=project, runs=project_runs)
    session.add(project)
    session.add(
        _persist_character_map_snapshot(
            session=session,
            project_id=project_id,
            source="upsert",
        )
    )
    session.add(
        _persist_voice_map_snapshot(
            session=session,
            project_id=project_id,
            source="upsert",
        )
    )
    session.commit()

    return CharacterMapResponse(
        project_id=project_id,
        character_map_finalized=project.character_map_finalized,
        characters=[
            CharacterMapItem(
                name=row.name.strip(),
                verbalized_form=row.verbalized_form.strip(),
                gender=row.gender.strip().lower(),
                voice_id=(row.voice_id.strip() if row.voice_id else None),
                aliases=row.aliases,
                notes=row.notes and row.notes.strip() or None,
                source=row.source,
                confidence=row.confidence,
                inferred_gender=row.inferred_gender,
                inferred_confidence=row.inferred_confidence,
                inferred_source_trace=row.inferred_source_trace or [],
            )
            for row in deduped.values()
        ],
    )


@app.get(
    "/api/projects/{project_id}/pronunciation-dictionary/artifacts",
    response_model=PronunciationDictionaryResponse,
    status_code=status.HTTP_200_OK,
)
def get_artifact_pronunciation_dictionary(
    project_id: int,
    session: Session = Depends(get_session),
) -> PronunciationDictionaryResponse:
    _get_project_or_404(session, project_id)

    entries = (
        session.query(PronunciationDictionary)
        .filter(PronunciationDictionary.project_id == project_id, PronunciationDictionary.scope == "artifact")
        .order_by(PronunciationDictionary.term.asc())
        .all()
    )
    return PronunciationDictionaryResponse(
        project_id=project_id,
        scope="artifact",
        entries=[_build_pronunciation_dictionary_payload(entry) for entry in entries],
    )


@app.put(
    "/api/projects/{project_id}/pronunciation-dictionary/artifacts",
    response_model=PronunciationDictionaryResponse,
    status_code=status.HTTP_200_OK,
)
def set_artifact_pronunciation_dictionary(
    project_id: int,
    payload: PronunciationDictionaryUpdateRequest,
    session: Session = Depends(get_session),
) -> PronunciationDictionaryResponse:
    project = _get_project_or_404(session, project_id)

    deduped: dict[str, PronunciationDictionaryItem] = {}
    for row in payload.entries:
        deduped[row.term.strip().lower()] = row

    session.query(PronunciationDictionary).filter(
        PronunciationDictionary.project_id == project_id,
        PronunciationDictionary.scope == "artifact",
    ).delete()

    for row in deduped.values():
        session.add(
            PronunciationDictionary(
                project_id=project_id,
                scope="artifact",
                character_name="",
                term=row.term.strip(),
                verbalized_form=row.verbalized_form.strip(),
                source=row.source,
                confidence=row.confidence,
            )
        )
    session.add(
        _persist_pronunciation_dictionary_snapshot(
            session=session,
            project_id=project_id,
            source="artifact",
        )
    )

    session.commit()
    saved_entries = (
        session.query(PronunciationDictionary)
        .filter(
            PronunciationDictionary.project_id == project_id,
            PronunciationDictionary.scope == "artifact",
        )
        .order_by(PronunciationDictionary.term.asc())
        .all()
    )

    return PronunciationDictionaryResponse(
        project_id=project.id,
        scope="artifact",
        entries=[_build_pronunciation_dictionary_payload(entry) for entry in saved_entries],
    )


@app.get(
    "/api/projects/{project_id}/pronunciation-dictionary/invented",
    response_model=PronunciationDictionaryResponse,
    status_code=status.HTTP_200_OK,
)
def get_invented_pronunciation_dictionary(
    project_id: int,
    session: Session = Depends(get_session),
) -> PronunciationDictionaryResponse:
    _get_project_or_404(session, project_id)

    entries = (
        session.query(PronunciationDictionary)
        .filter(PronunciationDictionary.project_id == project_id, PronunciationDictionary.scope == "invented")
        .order_by(PronunciationDictionary.term.asc())
        .all()
    )
    return PronunciationDictionaryResponse(
        project_id=project_id,
        scope="invented",
        entries=[_build_pronunciation_dictionary_payload(entry) for entry in entries],
    )


@app.put(
    "/api/projects/{project_id}/pronunciation-dictionary/invented",
    response_model=PronunciationDictionaryResponse,
    status_code=status.HTTP_200_OK,
)
def set_invented_pronunciation_dictionary(
    project_id: int,
    payload: PronunciationDictionaryUpdateRequest,
    session: Session = Depends(get_session),
) -> PronunciationDictionaryResponse:
    project = _get_project_or_404(session, project_id)

    deduped: dict[str, PronunciationDictionaryItem] = {}
    for row in payload.entries:
        deduped[row.term.strip().lower()] = row

    session.query(PronunciationDictionary).filter(
        PronunciationDictionary.project_id == project_id,
        PronunciationDictionary.scope == "invented",
    ).delete()

    for row in deduped.values():
        session.add(
            PronunciationDictionary(
                project_id=project_id,
                scope="invented",
                character_name="",
                term=row.term.strip(),
                verbalized_form=row.verbalized_form.strip(),
                source=row.source,
                confidence=row.confidence,
            )
        )
    session.add(
        _persist_pronunciation_dictionary_snapshot(
            session=session,
            project_id=project_id,
            source="invented",
        )
    )

    session.commit()
    saved_entries = (
        session.query(PronunciationDictionary)
        .filter(
            PronunciationDictionary.project_id == project_id,
            PronunciationDictionary.scope == "invented",
        )
        .order_by(PronunciationDictionary.term.asc())
        .all()
    )

    return PronunciationDictionaryResponse(
        project_id=project.id,
        scope="invented",
        entries=[_build_pronunciation_dictionary_payload(entry) for entry in saved_entries],
    )


@app.get(
    "/api/projects/{project_id}/pronunciation-dictionary/global",
    response_model=PronunciationDictionaryResponse,
    status_code=status.HTTP_200_OK,
)
def get_global_pronunciation_dictionary(
    project_id: int,
    session: Session = Depends(get_session),
) -> PronunciationDictionaryResponse:
    _get_project_or_404(session, project_id)

    entries = (
        session.query(PronunciationDictionary)
        .filter(PronunciationDictionary.project_id == project_id, PronunciationDictionary.scope == "global")
        .order_by(PronunciationDictionary.term.asc())
        .all()
    )
    return PronunciationDictionaryResponse(
        project_id=project_id,
        scope="global",
        entries=[_build_pronunciation_dictionary_payload(entry) for entry in entries],
    )


@app.put(
    "/api/projects/{project_id}/pronunciation-dictionary/global",
    response_model=PronunciationDictionaryResponse,
    status_code=status.HTTP_200_OK,
)
def set_global_pronunciation_dictionary(
    project_id: int,
    payload: PronunciationDictionaryUpdateRequest,
    session: Session = Depends(get_session),
) -> PronunciationDictionaryResponse:
    project = _get_project_or_404(session, project_id)

    deduped: dict[str, PronunciationDictionaryItem] = {}
    for row in payload.entries:
        deduped[row.term.strip().lower()] = row

    session.query(PronunciationDictionary).filter(
        PronunciationDictionary.project_id == project_id,
        PronunciationDictionary.scope == "global",
    ).delete()

    for row in deduped.values():
        session.add(
            PronunciationDictionary(
                project_id=project_id,
                scope="global",
                character_name="",
                term=row.term.strip(),
                verbalized_form=row.verbalized_form.strip(),
                source=row.source,
                confidence=row.confidence,
            )
        )
    session.add(
        _persist_pronunciation_dictionary_snapshot(
            session=session,
            project_id=project_id,
            source="global",
        )
    )

    session.commit()
    saved_entries = (
        session.query(PronunciationDictionary)
        .filter(PronunciationDictionary.project_id == project_id, PronunciationDictionary.scope == "global")
        .order_by(PronunciationDictionary.term.asc())
        .all()
    )

    return PronunciationDictionaryResponse(
        project_id=project.id,
        scope="global",
        entries=[_build_pronunciation_dictionary_payload(entry) for entry in saved_entries],
    )


@app.get(
    "/api/projects/{project_id}/pronunciation-dictionary/places",
    response_model=PronunciationDictionaryResponse,
    status_code=status.HTTP_200_OK,
)
def get_place_pronunciation_dictionary(
    project_id: int,
    session: Session = Depends(get_session),
) -> PronunciationDictionaryResponse:
    _get_project_or_404(session, project_id)

    entries = (
        session.query(PronunciationDictionary)
        .filter(PronunciationDictionary.project_id == project_id, PronunciationDictionary.scope == "place")
        .order_by(PronunciationDictionary.term.asc())
        .all()
    )
    return PronunciationDictionaryResponse(
        project_id=project_id,
        scope="place",
        entries=[_build_pronunciation_dictionary_payload(entry) for entry in entries],
    )


@app.put(
    "/api/projects/{project_id}/pronunciation-dictionary/places",
    response_model=PronunciationDictionaryResponse,
    status_code=status.HTTP_200_OK,
)
def set_place_pronunciation_dictionary(
    project_id: int,
    payload: PronunciationDictionaryUpdateRequest,
    session: Session = Depends(get_session),
) -> PronunciationDictionaryResponse:
    project = _get_project_or_404(session, project_id)

    deduped: dict[str, PronunciationDictionaryItem] = {}
    for row in payload.entries:
        deduped[row.term.strip().lower()] = row

    session.query(PronunciationDictionary).filter(
        PronunciationDictionary.project_id == project_id,
        PronunciationDictionary.scope == "place",
    ).delete()

    for row in deduped.values():
        session.add(
            PronunciationDictionary(
                project_id=project_id,
                scope="place",
                character_name="",
                term=row.term.strip(),
                verbalized_form=row.verbalized_form.strip(),
                source=row.source,
                confidence=row.confidence,
            )
        )
    session.add(
        _persist_pronunciation_dictionary_snapshot(
            session=session,
            project_id=project_id,
            source="place",
        )
    )

    session.commit()
    saved_entries = (
        session.query(PronunciationDictionary)
        .filter(
            PronunciationDictionary.project_id == project_id,
            PronunciationDictionary.scope == "place",
        )
        .order_by(PronunciationDictionary.term.asc())
        .all()
    )

    return PronunciationDictionaryResponse(
        project_id=project.id,
        scope="place",
        entries=[_build_pronunciation_dictionary_payload(entry) for entry in saved_entries],
    )


@app.get(
    "/api/projects/{project_id}/pronunciation-dictionary/character/{character_name}",
    response_model=PronunciationDictionaryResponse,
    status_code=status.HTTP_200_OK,
)
def get_character_pronunciation_dictionary(
    project_id: int,
    character_name: str,
    session: Session = Depends(get_session),
) -> PronunciationDictionaryResponse:
    _get_project_or_404(session, project_id)
    normalized_name = _normalize_character_reference_name(character_name)

    entries = (
        session.query(PronunciationDictionary)
        .filter(
            PronunciationDictionary.project_id == project_id,
            PronunciationDictionary.scope == "character",
            PronunciationDictionary.character_name == normalized_name,
        )
        .order_by(PronunciationDictionary.term.asc())
        .all()
    )
    return PronunciationDictionaryResponse(
        project_id=project_id,
        scope="character",
        entries=[_build_pronunciation_dictionary_payload(entry) for entry in entries],
    )


@app.put(
    "/api/projects/{project_id}/pronunciation-dictionary/character/{character_name}",
    response_model=PronunciationDictionaryResponse,
    status_code=status.HTTP_200_OK,
)
def set_character_pronunciation_dictionary(
    project_id: int,
    character_name: str,
    payload: PronunciationDictionaryUpdateRequest,
    session: Session = Depends(get_session),
) -> PronunciationDictionaryResponse:
    project = _get_project_or_404(session, project_id)
    normalized_name = _normalize_character_reference_name(character_name)

    deduped: dict[str, PronunciationDictionaryItem] = {}
    for row in payload.entries:
        deduped[row.term.strip().lower()] = row

    session.query(PronunciationDictionary).filter(
        PronunciationDictionary.project_id == project_id,
        PronunciationDictionary.scope == "character",
        PronunciationDictionary.character_name == normalized_name,
    ).delete()

    for row in deduped.values():
        session.add(
            PronunciationDictionary(
                project_id=project_id,
                scope="character",
                character_name=normalized_name,
                term=row.term.strip(),
                verbalized_form=row.verbalized_form.strip(),
                source=row.source,
                confidence=row.confidence,
            )
        )
    session.add(
        _persist_pronunciation_dictionary_snapshot(
            session=session,
            project_id=project_id,
            source="character",
        )
    )

    session.commit()

    saved_entries = (
        session.query(PronunciationDictionary)
        .filter(
            PronunciationDictionary.project_id == project_id,
            PronunciationDictionary.scope == "character",
            PronunciationDictionary.character_name == normalized_name,
        )
        .order_by(PronunciationDictionary.term.asc())
        .all()
    )
    return PronunciationDictionaryResponse(
        project_id=project.id,
        scope="character",
        entries=[_build_pronunciation_dictionary_payload(entry) for entry in saved_entries],
    )


def _build_pronunciation_preview_scope_map(
    project_id: int,
    session: Session,
    scope: str,
    character_name: str | None = None,
) -> dict[str, str]:
    query = session.query(PronunciationDictionary).filter(
        PronunciationDictionary.project_id == project_id,
        PronunciationDictionary.scope == scope,
    )

    if scope == "character" and character_name is not None:
        query = query.filter(PronunciationDictionary.character_name == character_name)

    entries = query.all()
    return {entry.term.strip(): entry.verbalized_form.strip() for entry in entries}


def _build_pronunciation_preview_alias_map(
    project_id: int,
    session: Session,
    character_name: str | None = None,
) -> dict[str, str]:
    if character_name is None:
        return {}

    query = session.query(Character).filter(
        Character.project_id == project_id,
        Character.name == character_name,
    )
    alias_map: dict[str, str] = {}
    for character in query:
        verbalized_form = character.verbalized_form.strip()
        for alias in character.aliases:
            cleaned_alias = str(alias).strip()
            if not cleaned_alias or cleaned_alias in alias_map:
                continue
            alias_map[cleaned_alias] = verbalized_form

    return alias_map


def _normalize_pronunciation_term_key(term: str, case_sensitive: bool) -> str:
    normalized = term.strip()
    if case_sensitive:
        return normalized
    return normalized.lower()


def _build_pronunciation_preview_ambiguity_warnings(
    candidates: list[tuple[str, str, str]],
    case_sensitive: bool,
) -> list[dict[str, object]]:
    collisions: dict[str, list[tuple[str, str, str]]] = {}
    for term, verbalized, scope in candidates:
        key = _normalize_pronunciation_term_key(term, case_sensitive)
        collisions.setdefault(key, []).append((term.strip(), verbalized.strip(), scope))

    warnings: list[dict[str, object]] = []
    for values in collisions.values():
        competing_verbalized = sorted({verbalized for _, verbalized, _ in values})
        if len(competing_verbalized) <= 1:
            continue

        normalized_scopes = sorted({scope for _, _, scope in values})
        canonical_term = values[0][0]
        warnings.append(
            {
                "type": "ambiguous_replacement",
                "term": canonical_term,
                "message": (
                    f"Ambiguous replacement for '{canonical_term}' from scopes: "
                    f"{', '.join(normalized_scopes)}."
                ),
                "scopes": normalized_scopes,
                "competing_verbalized_forms": competing_verbalized,
            }
        )

    return warnings


@app.post(
    "/api/projects/{project_id}/pronunciation-dictionary/preview",
    response_model=PronunciationDictionaryPreviewResponse,
    status_code=status.HTTP_200_OK,
)
def preview_pronunciation_dictionary(
    project_id: int,
    payload: PronunciationDictionaryPreviewRequest,
    session: Session = Depends(get_session),
) -> PronunciationDictionaryPreviewResponse:
    _get_project_or_404(session, project_id)

    if (
        not payload.include_global_scope
        and not payload.include_character_scope
        and not payload.include_place_scope
        and not payload.include_artifact_scope
        and not payload.include_invented_scope
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Set at least one of include_global_scope, include_character_scope, "
                "include_place_scope, include_artifact_scope, or include_invented_scope to true."
            ),
        )

    normalized_character_name = payload.character_name.strip() if payload.character_name else None

    global_map: dict[str, str] = {}
    character_map: dict[str, str] = {}
    place_map: dict[str, str] = {}
    artifact_map: dict[str, str] = {}
    invented_map: dict[str, str] = {}
    alias_map: dict[str, str] = {}
    replacement_term_scopes: dict[str, str] = {}
    included_scopes: list[str] = []

    if payload.include_global_scope:
        global_map = _build_pronunciation_preview_scope_map(project_id, session, "global")
        if global_map:
            included_scopes.append("global")
        for term in global_map:
            replacement_term_scopes[term] = "global"
            replacement_term_scopes[term.lower()] = "global"

    if payload.include_character_scope and normalized_character_name is not None:
        character_map = _build_pronunciation_preview_scope_map(
            project_id,
            session,
            "character",
            normalized_character_name,
        )
        if character_map:
            included_scopes.append("character")
        for term in character_map:
            replacement_term_scopes[term] = "character"
            replacement_term_scopes[term.lower()] = "character"

    if payload.include_character_scope and normalized_character_name is not None and payload.alias_aware:
        alias_map = _build_pronunciation_preview_alias_map(
            project_id,
            session,
            normalized_character_name,
        )
        if alias_map:
            if "character" not in included_scopes:
                included_scopes.append("character")
            for term in alias_map:
                replacement_term_scopes[term] = "character"
                replacement_term_scopes[term.lower()] = "character"

    if payload.include_place_scope:
        place_map = _build_pronunciation_preview_scope_map(project_id, session, "place")
        if place_map:
            included_scopes.append("place")
        for term in place_map:
            replacement_term_scopes[term] = "place"
            replacement_term_scopes[term.lower()] = "place"

    if payload.include_artifact_scope:
        artifact_map = _build_pronunciation_preview_scope_map(project_id, session, "artifact")
        if artifact_map:
            included_scopes.append("artifact")
        for term in artifact_map:
            replacement_term_scopes[term] = "artifact"
            replacement_term_scopes[term.lower()] = "artifact"

    if payload.include_invented_scope:
        invented_map = _build_pronunciation_preview_scope_map(project_id, session, "invented")
        if invented_map:
            included_scopes.append("invented")
        for term in invented_map:
            replacement_term_scopes[term] = "invented"
            replacement_term_scopes[term.lower()] = "invented"

    replacement_map = {**global_map}
    replacement_map.update(place_map)
    replacement_map.update(character_map)
    replacement_map.update(alias_map)
    replacement_map.update(artifact_map)
    replacement_map.update(invented_map)
    replacement_candidates: list[tuple[str, str, str]] = []
    replacement_candidates.extend((term, verbalized, "global") for term, verbalized in global_map.items())
    replacement_candidates.extend((term, verbalized, "place") for term, verbalized in place_map.items())
    replacement_candidates.extend((term, verbalized, "character") for term, verbalized in character_map.items())
    replacement_candidates.extend((term, verbalized, "character") for term, verbalized in alias_map.items())
    replacement_candidates.extend((term, verbalized, "artifact") for term, verbalized in artifact_map.items())
    replacement_candidates.extend((term, verbalized, "invented") for term, verbalized in invented_map.items())

    warnings = _build_pronunciation_preview_ambiguity_warnings(
        candidates=replacement_candidates,
        case_sensitive=payload.case_sensitive,
    )

    after_text, counts = replace_pronunciations_with_counts(
        payload.text,
        replacement_map,
        match_whole_words=payload.match_whole_words,
        case_sensitive=payload.case_sensitive,
    )
    replacement_items = []
    for term, count in sorted(counts.items(), key=lambda item: item[0].lower()):
        verbalized = replacement_map.get(term)
        if verbalized is None or count <= 0:
            continue
        scope = replacement_term_scopes.get(term) or replacement_term_scopes.get(term.lower(), "global")
        replacement_items.append(
            PronunciationDictionaryPreviewItem(
                term=term,
                verbalized_form=verbalized,
                count=count,
                scope=scope,
            )
        )

    return PronunciationDictionaryPreviewResponse(
        project_id=project_id,
        before=payload.text,
        after=after_text,
        character_name=normalized_character_name,
        replacements=replacement_items,
        included_scopes=included_scopes,
        warnings=warnings,
    )


@app.put(
    "/api/projects/{project_id}/voices",
    response_model=VoiceConfigResponse,
    status_code=status.HTTP_200_OK,
)
def update_voice_config(
    project_id: int,
    payload: VoiceConfigRequest,
    session: Session = Depends(get_session),
) -> VoiceConfigResponse:
    project = _get_project_or_404(session, project_id)

    narrator_voice = payload.narrator_voice.strip()
    male_voice = payload.male_default_voice.strip()
    female_voice = payload.female_default_voice.strip()
    neutral_voice = payload.neutral_default_voice.strip()
    unknown_voice = payload.unknown_default_voice.strip()
    if not narrator_voice:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="narrator_voice must not be blank",
        )

    voice_config = dict(project.voice_config_json or {})
    voice_config.update(
        {
        "narrator_voice": narrator_voice,
        "male_default_voice": male_voice,
        "female_default_voice": female_voice,
        "neutral_default_voice": neutral_voice,
        "unknown_default_voice": unknown_voice,
        "internal_thought_voice_policy": payload.internal_thought_voice_policy,
        }
    )
    if payload.internal_thought_voice is not None:
        voice_config["thought_voice"] = payload.internal_thought_voice
    else:
        voice_config.pop("thought_voice", None)

    project.voice_config_json = voice_config
    project.default_narrator_voice = narrator_voice
    project.default_male_voice = male_voice
    project.default_female_voice = female_voice
    project.default_neutral_voice = neutral_voice
    project.default_unknown_voice = unknown_voice
    session.add(project)
    session.commit()
    session.refresh(project)

    return VoiceConfigResponse(project_id=project.id, voice_config=project.voice_config_json)


def _create_and_dispatch_run(
    *,
    session: Session,
    project: Project,
    run_config: Mapping[str, object],
    request: Request,
    rerun_lineage_metadata: dict[str, object] | None = None,
    async_dispatch: bool = False,
) -> RunResponse:
    resolved_run_config: dict[str, object] = dict(run_config)
    correlation_id = _resolve_request_correlation_id(request)
    resolved_run_config["correlation_id"] = correlation_id
    project.selected_mode = str(resolved_run_config.get("mode", DEFAULT_MODE))
    project.selected_modes = _merge_selected_modes(project.selected_modes, project.selected_mode)
    _transition_project_lifecycle_state(project, PROJECT_LIFECYCLE_RUNNING, session=session)
    run = Run(
        project_id=project.id,
        status=RUN_STATUS_QUEUED,
        deterministic_seed=(
            int(resolved_run_config["deterministic_seed"])
            if bool(resolved_run_config.get("deterministic_mode"))
            else None
        ),
        deterministic_model_identifier=(
            str(resolved_run_config.get("deterministic_model_identifier")).strip()
            if bool(resolved_run_config.get("deterministic_mode"))
            else None
        ),
        deterministic_randomization_config=(
            dict(resolved_run_config.get("randomization_config"))
            if bool(resolved_run_config.get("deterministic_mode"))
            else None
        ),
        config_json=resolved_run_config,
        started_at=datetime.now(timezone.utc),
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    _append_run_changelog_entry(
        session=session,
        run=run,
        event_type="run_created",
        event_message="Run record created",
        event_metadata={
            "mode": resolved_run_config["mode"],
            "llm_enabled": bool(resolved_run_config.get("llm_enabled")),
            "provider_name": str(resolved_run_config.get("provider_name")),
        },
    )
    run_config_with_snapshot = dict(run.config_json or {})
    run_configuration_snapshot = _persist_run_configuration_snapshot(
        session=session,
        project_id=project.id,
        run_id=run.id,
        source="run_capture",
        run_config=run_config_with_snapshot,
    )
    session.add(run_configuration_snapshot)
    session.flush()
    project_principal = _resolve_project_access_headers(request=request)
    if project_principal is None:
        principal_type = None
        principal_id = None
    else:
        principal_type, principal_id = project_principal
    activity_actor = _resolve_project_activity_actor(
        principal_type=principal_type,
        principal_id=principal_id,
    )
    run_start_metadata: dict[str, object] = {
        "mode": str(resolved_run_config.get("mode", DEFAULT_MODE)),
        "recovery": False,
    }
    if rerun_lineage_metadata is not None:
        run_start_metadata["rerun"] = True
    _append_project_activity_event(
        session=session,
        project_id=project.id,
        run_id=run.id,
        event_type="run_start",
        actor=activity_actor,
        event_metadata=run_start_metadata,
    )
    if rerun_lineage_metadata is not None:
        rerun_event_metadata = dict(rerun_lineage_metadata)
        rerun_event_metadata["rerun_run_id"] = run.id
        _append_project_activity_event(
            session=session,
            project_id=project.id,
            run_id=run.id,
            event_type="rerun",
            actor=activity_actor,
            event_metadata=rerun_event_metadata,
        )
    _append_run_changelog_entry(
        session=session,
        run=run,
        event_type="run_configuration_snapshot_created",
        event_message="Run configuration snapshot created",
        event_metadata={
            "snapshot_id": run_configuration_snapshot.id,
            "snapshot_version": run_configuration_snapshot.version,
            "source": run_configuration_snapshot.source,
        },
    )
    run_config_with_snapshot["configuration_snapshot_id"] = (
        _build_run_configuration_snapshot_id(run.id, run_configuration_snapshot.version)
    )
    run_config_with_snapshot["configuration_snapshot_version"] = run_configuration_snapshot.version
    run.config_json = run_config_with_snapshot
    session.add(run)
    character_map_snapshot = _persist_character_map_snapshot(
        session=session,
        project_id=project.id,
        run_id=run.id,
        source="run_capture",
    )
    session.add(character_map_snapshot)
    pronunciation_dictionary_snapshot = _persist_pronunciation_dictionary_snapshot(
        session=session,
        project_id=project.id,
        run_id=run.id,
        source="run_capture",
    )
    session.add(pronunciation_dictionary_snapshot)
    voice_map_snapshot = _persist_voice_map_snapshot(
        session=session,
        project_id=project.id,
        run_id=run.id,
        source="run_capture",
    )
    session.add(voice_map_snapshot)
    session.flush()
    _append_run_changelog_entry(
        session=session,
        run=run,
        event_type="character_map_snapshot_created",
        event_message="Character map snapshot created",
        event_metadata={
            "snapshot_id": character_map_snapshot.id,
            "snapshot_version": character_map_snapshot.version,
            "source": character_map_snapshot.source,
        },
    )
    _append_run_changelog_entry(
        session=session,
        run=run,
        event_type="pronunciation_dictionary_snapshot_created",
        event_message="Pronunciation dictionary snapshot created",
        event_metadata={
            "snapshot_id": pronunciation_dictionary_snapshot.id,
            "snapshot_version": pronunciation_dictionary_snapshot.version,
            "source": pronunciation_dictionary_snapshot.source,
        },
    )
    _append_run_changelog_entry(
        session=session,
        run=run,
        event_type="voice_map_snapshot_created",
        event_message="Voice map snapshot created",
        event_metadata={
            "snapshot_id": voice_map_snapshot.id,
            "snapshot_version": voice_map_snapshot.version,
            "source": voice_map_snapshot.source,
        },
    )
    run_config_with_snapshot = dict(run.config_json or {})
    run_config_with_snapshot["character_map_snapshot_id"] = character_map_snapshot.id
    run_config_with_snapshot["character_map_snapshot_version"] = character_map_snapshot.version
    run_config_with_snapshot["pronunciation_dictionary_snapshot_id"] = pronunciation_dictionary_snapshot.id
    run_config_with_snapshot["pronunciation_dictionary_snapshot_version"] = pronunciation_dictionary_snapshot.version
    run_config_with_snapshot["voice_map_snapshot_id"] = voice_map_snapshot.id
    run_config_with_snapshot["voice_map_snapshot_version"] = voice_map_snapshot.version
    run.config_json = run_config_with_snapshot
    session.add(run)
    _append_run_changelog_entry(
        session=session,
        run=run,
        event_type="pipeline_execution_queued",
        event_message="Pipeline execution queued",
        event_metadata={"mode": resolved_run_config["mode"]},
    )
    run.status = RUN_STATUS_RUNNING
    session.add(run)
    _append_run_changelog_entry(
        session=session,
        run=run,
        event_type="pipeline_execution_started",
        event_message="Pipeline execution started",
        event_metadata={"mode": resolved_run_config["mode"]},
    )
    recovery_state = _coerce_recovery_state(run.config_json).get(_PIPELINE_RECOVERY_CONFIG_KEY)
    if not isinstance(recovery_state, dict) or not recovery_state:
        run_config_with_recovery = dict(run.config_json or {})
        run_config_with_recovery[_PIPELINE_RECOVERY_CONFIG_KEY] = {
            "status": "running",
            "attempt": 0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "reason": "initial_execution",
        }
        run.config_json = run_config_with_recovery
    _refresh_project_dashboard_projection(session=session, project=project)
    session.commit()
    session.refresh(run)
    _emit_service_log(
        service="run_orchestration",
        event="run_execution_dispatched",
        message="Run execution dispatched",
        project_id=project.id,
        run_id=run.id,
        correlation_id=correlation_id,
        metadata={
            "mode": str(resolved_run_config.get("mode", DEFAULT_MODE)),
            "recovery": False,
        },
    )
    if async_dispatch:
        executor_name, task_id = _dispatch_pipeline_run_execution(
            run_id=run.id,
            principal_type=principal_type,
            principal_id=principal_id,
        )
        segment_count = session.query(Segment).filter(Segment.run_id == run.id).count()
    else:
        segment_count = submit_background_job(
            job_name="pipeline_execute_run",
            execute=lambda: _execute_pipeline_and_finalize_run(
                session=session,
                project=project,
                run=run,
                principal_type=principal_type,
                principal_id=principal_id,
            ),
            correlation_id=correlation_id,
        )
        executor_name = "inline"
        task_id = None
    _emit_service_log(
        service="run_orchestration",
        event="run_execution_submit_completed",
        message="Run execution submit completed",
        project_id=project.id,
        run_id=run.id,
        correlation_id=correlation_id,
        metadata={
            "mode": str(resolved_run_config.get("mode", DEFAULT_MODE)),
            "segment_count": segment_count,
            "recovery": False,
            "async_dispatch": async_dispatch,
            "executor_name": executor_name,
            "task_id": task_id,
        },
    )

    return RunResponse(
        run_id=run.id,
        project_id=project.id,
        status=run.status,
        segment_count=segment_count,
    )


@app.post(
    "/api/projects/{project_id}/runs",
    response_model=RunResponse,
    status_code=status.HTTP_200_OK,
)
def create_run(
    project_id: int,
    payload: RunCreateRequest,
    request: Request,
    run_async: bool = Query(default=False, alias="async"),
    session: Session = Depends(get_session),
) -> RunResponse:
    project = _get_project_or_404(session, project_id)
    if (
        not payload.allow_unfinalized_character_map
        and not project.character_map_finalized
        and session.query(Character).filter(Character.project_id == project.id).count() > 0
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Character map is not finalized. Set `allow_unfinalized_character_map` to true to run with an "
                "unfinalized map."
            ),
        )

    explicit_overrides = payload.model_dump(exclude={"mode"}, exclude_unset=True)
    explicit_overrides.setdefault("llm_enabled", project.llm_enabled)
    project_provider_config = dict(project.llm_provider_config_json or {})
    if project_provider_config:
        explicit_overrides.setdefault("provider_config", project_provider_config)
    _coalesce_internal_thought_policy(project=project, explicit_overrides=explicit_overrides)
    run_config = build_run_config_snapshot(
        mode=payload.mode,
        overrides=explicit_overrides,
    )
    run_config["emotion_taxonomy"] = str(explicit_overrides.get("emotion_taxonomy", "basic"))

    run_config["ingestion_warnings"] = list((project.ingestion_log_json or {}).get("warnings", []))
    run_config["normalization_report"] = (
        project.ingestion_log_json or {}
    ).get("normalization_report", {})
    run_config_extra_fields = {
        key: value
        for key, value in explicit_overrides.items()
        if key not in PROFILE_CONFIG_KEYS and key != "allow_unfinalized_character_map"
    }
    run_config.update(run_config_extra_fields)
    if bool(run_config.get("deterministic_mode")):
        pinned_model = str(run_config.get("deterministic_model_identifier") or "").strip()
        if not pinned_model:
            _, pinned_model, _ = get_provider_runtime_settings(
                settings=get_settings(),
                provider_name=str(run_config.get("provider_name", "openrouter")),
            )
        run_config["deterministic_model_identifier"] = pinned_model

        deterministic_seed = run_config.get("deterministic_seed")
        if deterministic_seed is None:
            deterministic_seed = 0
        deterministic_seed_int = int(deterministic_seed)
        run_config["deterministic_seed"] = deterministic_seed_int

        resolved_randomization_config = run_config.get("randomization_config")
        if not isinstance(resolved_randomization_config, dict):
            resolved_randomization_config = {}
        resolved_randomization_config = dict(resolved_randomization_config)
        resolved_randomization_config.setdefault("seed", deterministic_seed_int)
        resolved_randomization_config.setdefault("strategy", "stable")
        resolved_randomization_config.setdefault("shuffle_enabled", False)
        run_config["randomization_config"] = resolved_randomization_config
    else:
        run_config.pop("deterministic_model_identifier", None)
        run_config.pop("deterministic_seed", None)
        run_config.pop("randomization_config", None)

    idempotency_key = payload.idempotency_key
    if idempotency_key is not None:
        idempotency_signature = _build_idempotent_rerun_signature(
            session=session,
            project=project,
            run_config=run_config,
        )
        matching_run = _find_matching_idempotent_run(
            session=session,
            project_id=project.id,
            idempotency_key=idempotency_key,
            idempotency_signature=idempotency_signature,
        )
        if matching_run is not None:
            return _build_run_response_from_existing(session=session, run=matching_run)
        run_config["idempotency_key"] = idempotency_key
        run_config["idempotency_signature"] = idempotency_signature

    return _create_and_dispatch_run(
        session=session,
        project=project,
        run_config=run_config,
        request=request,
        async_dispatch=run_async,
    )


def _build_rerun_run_config_from_source(
    *,
    project: Project,
    source_run: Run,
) -> tuple[dict[str, object], dict[str, object]]:
    source_snapshot = source_run.run_configuration_snapshot
    source_snapshot_payload = (
        dict(source_snapshot.snapshot_json)
        if source_snapshot is not None and isinstance(source_snapshot.snapshot_json, dict)
        else {}
    )
    source_snapshot_configuration = source_snapshot_payload.get("configuration")
    if isinstance(source_snapshot_configuration, dict):
        cloned_config = dict(source_snapshot_configuration)
    elif isinstance(source_run.config_json, dict):
        cloned_config = dict(source_run.config_json)
    else:
        cloned_config = {}

    for runtime_key in (
        "correlation_id",
        "idempotency_key",
        "idempotency_signature",
        "configuration_snapshot_id",
        "configuration_snapshot_version",
        "character_map_snapshot_id",
        "character_map_snapshot_version",
        "pronunciation_dictionary_snapshot_id",
        "pronunciation_dictionary_snapshot_version",
        "voice_map_snapshot_id",
        "voice_map_snapshot_version",
        "time_series_snapshot_id",
        "time_series_snapshot_version",
        "artifact_integrity",
        _PIPELINE_RECOVERY_CONFIG_KEY,
    ):
        cloned_config.pop(runtime_key, None)

    configured_mode = str(cloned_config.get("mode", project.selected_mode or DEFAULT_MODE)).strip().lower()
    if not configured_mode or not is_valid_mode(configured_mode):
        fallback_mode = str(project.selected_mode or DEFAULT_MODE).strip().lower()
        configured_mode = fallback_mode if is_valid_mode(fallback_mode) else DEFAULT_MODE
    cloned_config["mode"] = configured_mode

    requested_at = datetime.now(timezone.utc).isoformat()
    rerun_lineage_metadata: dict[str, object] = {
        "source_run_id": source_run.id,
        "source_status": str(source_run.status or "").strip().lower() or "unknown",
        "source_configuration_snapshot_id": source_snapshot.id if source_snapshot is not None else None,
        "source_configuration_snapshot_version": source_snapshot.version if source_snapshot is not None else None,
        "lineage_type": "snapshot_clone",
        "requested_at": requested_at,
    }

    cloned_config["rerun_source_run_id"] = source_run.id
    if source_snapshot is not None:
        cloned_config["rerun_source_configuration_snapshot_id"] = source_snapshot.id
        cloned_config["rerun_source_configuration_snapshot_version"] = source_snapshot.version
    cloned_config["rerun_source_status"] = rerun_lineage_metadata["source_status"]
    cloned_config["rerun_lineage_type"] = "snapshot_clone"
    cloned_config["rerun_requested_at"] = requested_at
    return cloned_config, rerun_lineage_metadata


@app.post(
    "/api/projects/{project_id}/runs/{run_id}/rerun",
    response_model=RunResponse,
    status_code=status.HTTP_200_OK,
)
def rerun_from_snapshot(
    project_id: int,
    run_id: int,
    request: Request,
    run_async: bool = Query(default=False, alias="async"),
    session: Session = Depends(get_session),
) -> RunResponse:
    project = _get_project_or_404(session, project_id)
    source_run = _get_run_or_404(session, project_id, run_id)
    source_status = str(source_run.status or "").strip().lower()
    if source_status in {RUN_STATUS_QUEUED, RUN_STATUS_RUNNING}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only completed, failed, cancelled, or interrupted runs can be rerun from snapshot.",
        )

    cloned_run_config, rerun_lineage_metadata = _build_rerun_run_config_from_source(
        project=project,
        source_run=source_run,
    )
    return _create_and_dispatch_run(
        session=session,
        project=project,
        run_config=cloned_run_config,
        request=request,
        rerun_lineage_metadata=rerun_lineage_metadata,
        async_dispatch=run_async,
    )


@app.post(
    "/api/projects/{project_id}/runs/{run_id}/recover",
    response_model=RunResponse,
    status_code=status.HTTP_200_OK,
)
def recover_run(
    project_id: int,
    run_id: int,
    request: Request,
    run_async: bool = Query(default=False, alias="async"),
    session: Session = Depends(get_session),
) -> RunResponse:
    project = _get_project_or_404(session, project_id)
    run = _get_run_or_404(session, project_id, run_id)
    correlation_id = _resolve_request_correlation_id(request)

    if run.status == RUN_STATUS_COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Completed run cannot be recovered.",
        )

    if not _is_run_recoverable(run):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Run is not yet eligible for recovery.",
        )

    previous_status = run.status
    recovery_state = _coerce_recovery_state(run.config_json).get(_PIPELINE_RECOVERY_CONFIG_KEY)
    previous_attempt = recovery_state.get("attempt") if isinstance(recovery_state, dict) else None
    try:
        next_attempt = int(previous_attempt) + 1
    except (TypeError, ValueError):
        next_attempt = 1

    run_config_with_recovery = _prepare_run_recovery_config(
        run_config=dict(run.config_json or {}),
        attempt=next_attempt,
    )
    run_config_with_recovery["correlation_id"] = correlation_id
    run.config_json = run_config_with_recovery
    run.status = RUN_STATUS_QUEUED
    run.started_at = datetime.now(timezone.utc)
    run.finished_at = None
    session.add(run)
    _append_run_changelog_entry(
        session=session,
        run=run,
        event_type="pipeline_recovery_requested",
        event_message="Pipeline recovery requested",
        event_metadata={
            "attempt": next_attempt,
            "previous_status": previous_status,
        },
    )
    _clear_run_pipeline_artifacts(session=session, run=run)
    run.status = RUN_STATUS_RUNNING
    _transition_project_lifecycle_state(project, PROJECT_LIFECYCLE_RUNNING, session=session)
    session.add(project)
    session.add(run)
    _append_run_changelog_entry(
        session=session,
        run=run,
        event_type="pipeline_execution_started",
        event_message="Pipeline execution started",
        event_metadata={
            "mode": str((run.config_json or {}).get("mode", DEFAULT_MODE)),
            "recovery": True,
        },
    )
    session.commit()
    session.refresh(run)
    _emit_service_log(
        service="run_orchestration",
        event="run_recovery_dispatched",
        message="Run recovery dispatched",
        project_id=project.id,
        run_id=run.id,
        correlation_id=correlation_id,
        metadata={
            "attempt": next_attempt,
            "mode": str((run.config_json or {}).get("mode", DEFAULT_MODE)),
            "recovery": True,
        },
    )

    project_principal = _resolve_project_access_headers(request=request)
    if project_principal is None:
        principal_type = None
        principal_id = None
    else:
        principal_type, principal_id = project_principal
    activity_actor = _resolve_project_activity_actor(
        principal_type=principal_type,
        principal_id=principal_id,
    )
    _append_project_activity_event(
        session=session,
        project_id=project.id,
        run_id=run.id,
        event_type="rerun",
        actor=activity_actor,
        event_metadata={
            "attempt": next_attempt,
            "previous_status": previous_status,
        },
    )
    session.commit()

    if run_async:
        executor_name, task_id = _dispatch_pipeline_run_execution(
            run_id=run.id,
            principal_type=principal_type,
            principal_id=principal_id,
        )
        segment_count = session.query(Segment).filter(Segment.run_id == run.id).count()
    else:
        segment_count = submit_background_job(
            job_name="pipeline_recover_run",
            execute=lambda: _execute_pipeline_and_finalize_run(
                session=session,
                project=project,
                run=run,
                principal_type=principal_type,
                principal_id=principal_id,
            ),
            correlation_id=correlation_id,
        )
        executor_name = "inline"
        task_id = None
    _emit_service_log(
        service="run_orchestration",
        event="run_recovery_submit_completed",
        message="Run recovery submit completed",
        project_id=project.id,
        run_id=run.id,
        correlation_id=correlation_id,
        metadata={
            "attempt": next_attempt,
            "segment_count": segment_count,
            "recovery": True,
            "async_dispatch": run_async,
            "executor_name": executor_name,
            "task_id": task_id,
        },
    )

    return RunResponse(
        run_id=run.id,
        project_id=project.id,
        status=run.status,
        segment_count=segment_count,
    )


@app.post(
    "/api/projects/{project_id}/runs/{run_id}/cancel",
    response_model=RunResponse,
    status_code=status.HTTP_200_OK,
)
def cancel_run(
    project_id: int,
    run_id: int,
    session: Session = Depends(get_session),
) -> RunResponse:
    project = _get_project_or_404(session, project_id)
    run = _get_run_or_404(session, project_id, run_id)

    if run.status not in {RUN_STATUS_QUEUED, RUN_STATUS_RUNNING}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only queued or running runs can be cancelled.",
        )

    previous_status = run.status
    run.status = RUN_STATUS_CANCELLED
    if run.finished_at is None:
        run.finished_at = datetime.now(timezone.utc)
    _transition_project_lifecycle_state(project, PROJECT_LIFECYCLE_CONFIGURED, session=session)
    _set_pipeline_recovery_state(
        run,
        session=session,
        status=RUN_STATUS_CANCELLED,
        metadata={
            "reason": "manual_cancellation",
            "previous_status": previous_status,
        },
    )
    session.add(run)
    session.add(project)
    _append_run_changelog_entry(
        session=session,
        run=run,
        event_type="pipeline_cancel_requested",
        event_message="Pipeline cancellation requested",
        event_metadata={
            "previous_status": previous_status,
        },
    )
    session.commit()
    session.refresh(run)
    _emit_service_log(
        service="run_orchestration",
        event="run_cancelled",
        message="Run cancelled",
        project_id=project_id,
        run_id=run.id,
        correlation_id=_resolve_correlation_id_from_run_config(run.config_json),
        metadata={
            "previous_status": previous_status,
            "current_status": run.status,
        },
    )

    segment_count = session.query(Segment).filter(Segment.run_id == run.id).count()
    return RunResponse(
        run_id=run.id,
        project_id=project_id,
        status=run.status,
        segment_count=segment_count,
    )


@app.get(
    "/api/projects/{project_id}/runs/{run_id}/config-preset",
    response_model=RunConfigPresetResponse,
    status_code=status.HTTP_200_OK,
)
def get_run_config_preset(
    project_id: int,
    run_id: int,
    session: Session = Depends(get_session),
) -> RunConfigPresetResponse:
    _get_project_or_404(session, project_id)
    run = _get_run_or_404(session, project_id, run_id)
    return RunConfigPresetResponse(
        project_id=project_id,
        run_id=run.id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        run_config=_build_run_config_preset(run.config_json),
    )


@app.get(
    "/api/projects/{project_id}/runs/config-diff",
    response_model=RunConfigDiffResponse,
    status_code=status.HTTP_200_OK,
)
def get_run_config_diff(
    project_id: int,
    base_run_id: int = Query(..., ge=1),
    target_run_id: int = Query(..., ge=1),
    session: Session = Depends(get_session),
) -> RunConfigDiffResponse:
    _get_project_or_404(session, project_id)
    if base_run_id == target_run_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="base_run_id and target_run_id must be different.",
        )

    base_run = _get_run_or_404(session, project_id, base_run_id)
    target_run = _get_run_or_404(session, project_id, target_run_id)
    diff_payload = _build_run_config_diff(
        base_run_config=base_run.config_json,
        target_run_config=target_run.config_json,
    )
    return RunConfigDiffResponse(
        project_id=project_id,
        base_run_id=base_run.id,
        target_run_id=target_run.id,
        base_config_schema_version=diff_payload["base_config_schema_version"],
        target_config_schema_version=diff_payload["target_config_schema_version"],
        is_identical=bool(diff_payload["is_identical"]),
        changed_fields=diff_payload["changed_fields"],
        base_only_fields=diff_payload["base_only_fields"],
        target_only_fields=diff_payload["target_only_fields"],
    )


@app.get(
    "/api/projects/{project_id}/runs/{run_id}",
    response_model=RunDetailResponse,
    status_code=status.HTTP_200_OK,
)
def get_run_detail(project_id: int, run_id: int, session: Session = Depends(get_session)) -> RunDetailResponse:
    _get_project_or_404(session, project_id)
    run = _get_run_or_404(session, project_id, run_id)

    segment_count = session.query(Segment).filter(Segment.run_id == run.id).count()
    llm_calls = (
        session.query(LLMCall)
        .filter(LLMCall.run_id == run.id)
        .order_by(LLMCall.created_at.asc())
        .all()
    )
    changelog_entries = (
        session.query(RunChangelogEntry)
        .filter(RunChangelogEntry.run_id == run.id)
        .order_by(RunChangelogEntry.created_at.asc(), RunChangelogEntry.id.asc())
        .all()
    )

    call_payload = [
        {
            "id": call.id,
            "provider": call.provider,
            "task_type": call.task_type,
            "success": call.success,
            "request_count": call.request_count,
            "token_usage_estimate": call.token_usage_estimate,
            "model_identifier": call.model_identifier,
            "called_at": _serialize_datetime_to_utc_iso(call.called_at),
            "detail": call.detail,
            "created_at": call.created_at.isoformat(),
            "is_cache_hit": call.is_cache_hit,
        }
        for call in llm_calls
    ]

    cache_metrics: dict[str, dict[str, int]] = {}
    for call in llm_calls:
        metric = cache_metrics.setdefault(call.task_type, {"hits": 0, "misses": 0})
        if call.is_cache_hit:
            metric["hits"] += 1
        else:
            metric["misses"] += 1

    if run.status == RUN_STATUS_COMPLETED:
        _refresh_run_artifact_integrity_in_config(session=session, run=run)
        session.refresh(run)
    sanitized_run_config = _sanitize_run_config_for_frontend(run.config_json)

    return RunDetailResponse(
        run_id=run.id,
        project_id=project_id,
        status=run.status,
        llm_provider_name=run.llm_provider_name,
        llm_model_identifier=run.llm_model_identifier,
        llm_model_version=run.llm_model_version,
        config=sanitized_run_config,
        started_at=run.started_at,
        finished_at=run.finished_at,
        segment_count=segment_count,
        llm_cache_metrics=cache_metrics,
        llm_calls=call_payload,
        changelog_entries=[
            {
                "id": entry.id,
                "event_type": entry.event_type,
                "event_message": entry.event_message,
                "event_metadata": entry.event_metadata,
                "created_at": entry.created_at,
            }
            for entry in changelog_entries
        ],
    )


def _coerce_dashboard_non_negative_int(value: object, *, default: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _coerce_dashboard_non_negative_optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _coerce_dashboard_optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_pipeline_stage_duration_items(
    raw_items: object,
    *,
    total_duration_ms: int,
) -> list[dict[str, object]]:
    if not isinstance(raw_items, list):
        return []

    normalized_items: list[dict[str, object]] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, Mapping):
            continue

        raw_stage_name = raw_item.get("name")
        if not isinstance(raw_stage_name, str):
            continue
        stage_name = raw_stage_name.strip()
        if not stage_name:
            continue

        duration_ms = _coerce_dashboard_non_negative_int(raw_item.get("duration_ms"), default=0)
        share_of_total = 0.0
        if total_duration_ms > 0:
            share_of_total = min(1.0, max(0.0, float(duration_ms) / float(total_duration_ms)))

        normalized_items.append(
            {
                "stage_name": stage_name,
                "duration_ms": duration_ms,
                "memory_bytes_start": _coerce_dashboard_non_negative_optional_int(raw_item.get("memory_bytes_start")),
                "memory_bytes_end": _coerce_dashboard_non_negative_optional_int(raw_item.get("memory_bytes_end")),
                "memory_bytes_delta": _coerce_dashboard_optional_int(raw_item.get("memory_bytes_delta")),
                "share_of_total": round(share_of_total, 6),
            }
        )

    return normalized_items


def _build_pipeline_stage_durations_dashboard(
    *,
    project_id: int,
    run: Run,
) -> PipelineStageDurationsDashboardResponse:
    run_config = run.config_json if isinstance(run.config_json, Mapping) else {}
    performance_telemetry = run_config.get("performance_telemetry")

    raw_steps: object = []
    total_duration_ms = 0
    if isinstance(performance_telemetry, Mapping):
        raw_steps = performance_telemetry.get("steps", [])
        total_duration_ms = _coerce_dashboard_non_negative_int(
            performance_telemetry.get("total_duration_ms"),
            default=0,
        )

    stage_rows = _normalize_pipeline_stage_duration_items(raw_steps, total_duration_ms=total_duration_ms)
    if total_duration_ms <= 0 and stage_rows:
        total_duration_ms = sum(int(row.get("duration_ms", 0)) for row in stage_rows)
        stage_rows = _normalize_pipeline_stage_duration_items(raw_steps, total_duration_ms=total_duration_ms)

    if total_duration_ms <= 0 and run.started_at is not None and run.finished_at is not None:
        total_duration_ms = max(0, int((run.finished_at - run.started_at).total_seconds() * 1000))

    slowest_stage_name: str | None = None
    slowest_stage_duration_ms: int | None = None
    if stage_rows:
        slowest_stage = max(stage_rows, key=lambda row: int(row.get("duration_ms", 0)))
        slowest_stage_name = str(slowest_stage["stage_name"])
        slowest_stage_duration_ms = int(slowest_stage["duration_ms"])

    generated_at = (run.finished_at or run.started_at or datetime.now(timezone.utc)).isoformat()
    return PipelineStageDurationsDashboardResponse(
        project_id=project_id,
        run_id=run.id,
        run_status=run.status,
        generated_at=generated_at,
        total_duration_ms=total_duration_ms,
        stage_count=len(stage_rows),
        slowest_stage_name=slowest_stage_name,
        slowest_stage_duration_ms=slowest_stage_duration_ms,
        stages=stage_rows,
    )


@app.get(
    "/api/projects/{project_id}/runs/{run_id}/pipeline-stage-durations-dashboard",
    response_model=PipelineStageDurationsDashboardResponse,
    status_code=status.HTTP_200_OK,
)
def get_run_pipeline_stage_durations_dashboard(
    project_id: int,
    run_id: int,
    session: Session = Depends(get_session),
) -> PipelineStageDurationsDashboardResponse:
    _get_project_or_404(session, project_id)
    run = _get_run_or_404(session, project_id, run_id)
    return _build_pipeline_stage_durations_dashboard(project_id=project_id, run=run)


@app.get(
    "/api/projects/{project_id}/runs/{run_id}/audiobook-prep-dashboard",
    response_model=AudiobookPrepDashboardResponse,
    status_code=status.HTTP_200_OK,
)
def get_run_audiobook_prep_dashboard(
    project_id: int,
    run_id: int,
    session: Session = Depends(get_session),
) -> AudiobookPrepDashboardResponse:
    project = _get_project_or_404(session, project_id)
    run = _get_run_or_404(session, project_id, run_id)

    segment_rows = (
        session.query(Segment)
        .filter(Segment.run_id == run.id)
        .order_by(Segment.id.asc())
        .all()
    )
    segment_payloads = [segment.segment_json for segment in segment_rows if isinstance(segment.segment_json, dict)]

    unresolved_speaker_count = 0
    low_confidence_region_count = 0
    speaker_ids: set[int] = set()

    for segment in segment_payloads:
        if _is_low_confidence_region(segment):
            low_confidence_region_count += 1

        speaker_state = segment.get("speaker_state")
        tag_states = _as_dict(segment.get("tag_states"))
        speaker_id = segment.get("speaker_id")

        if (
            _is_low_confidence_state(speaker_state)
            or _is_low_confidence_state(tag_states.get("speaker"))
            or not isinstance(speaker_id, int)
        ):
            unresolved_speaker_count += 1

        if isinstance(speaker_id, int):
            speaker_ids.add(speaker_id)

    character_rows = (
        session.query(Character.id, Character.voice_id)
        .filter(Character.project_id == project.id, Character.id.in_(speaker_ids or [0]))
        .all()
        if speaker_ids
        else []
    )
    mapped_speaker_ids = {
        row[0]
        for row in session.query(CharacterVoiceMap.character_id)
        .filter(CharacterVoiceMap.character_id.in_([row[0] for row in character_rows]))
        .all()
    }

    unresolved_voice_mapping_count = 0
    for character_id, raw_voice_id in character_rows:
        resolved_voice_id = str(raw_voice_id).strip() if isinstance(raw_voice_id, str) else raw_voice_id
        if not resolved_voice_id and character_id not in mapped_speaker_ids:
            unresolved_voice_mapping_count += 1

    generated_at = (run.finished_at or run.started_at or datetime.now(timezone.utc)).isoformat()

    blocking_reasons: list[str] = []
    warning_reasons: list[str] = []
    if run.status != "completed":
        blocking_reasons.append("Run must be completed before the audiobook dashboard is fully ready.")
    if unresolved_speaker_count > 0:
        blocking_reasons.append("Some speaker assignments are still unresolved.")
    if unresolved_voice_mapping_count > 0:
        blocking_reasons.append("Some speakers are missing voice mappings.")
    if low_confidence_region_count > 0:
        warning_reasons.append("Some regions were tagged as low confidence and should be reviewed.")

    return AudiobookPrepDashboardResponse(
        project_id=project.id,
        run_id=run.id,
        run_status=run.status,
        generated_at=generated_at,
        unresolved_speaker_count=unresolved_speaker_count,
        unresolved_voice_mapping_count=unresolved_voice_mapping_count,
        low_confidence_region_count=low_confidence_region_count,
        export_readiness={
            "is_ready": not bool(blocking_reasons),
            "blocking_reasons": blocking_reasons,
            "warning_reasons": warning_reasons,
        },
    )


@app.get(
    "/api/projects/{project_id}/runs/{run_id}/character-analytics",
    response_model=CharacterOccurrenceAnalyticsResponse,
    status_code=status.HTTP_200_OK,
)
def get_character_occurrence_analytics(
    project_id: int,
    run_id: int,
    session: Session = Depends(get_session),
) -> CharacterOccurrenceAnalyticsResponse:
    _get_project_or_404(session, project_id)
    run = _get_run_or_404(session, project_id, run_id)

    config_json = run.config_json or {}
    configured_payload = {
        "character_mentions_by_chapter": config_json.get("character_mentions_by_chapter"),
        "character_first_appearance_chapter_index": config_json.get(
            "character_first_appearance_chapter_index"
        ),
        "character_last_appearance_chapter_index": config_json.get("character_last_appearance_chapter_index"),
        "character_mentions_per_1000_words": config_json.get("character_mentions_per_1000_words"),
        "character_dialogue_line_counts": config_json.get("character_dialogue_line_counts"),
    }
    if all(value is not None for value in configured_payload.values()):
        return CharacterOccurrenceAnalyticsResponse(
            project_id=project_id,
            run_id=run.id,
            character_mentions_by_chapter=configured_payload["character_mentions_by_chapter"],
            character_first_appearance_chapter_index=configured_payload[
                "character_first_appearance_chapter_index"
            ],
            character_last_appearance_chapter_index=configured_payload[
                "character_last_appearance_chapter_index"
            ],
            character_mentions_per_1000_words=configured_payload[
                "character_mentions_per_1000_words"
            ],
            character_dialogue_line_counts=configured_payload["character_dialogue_line_counts"],
        )

    chapters = (
        session.query(Chapter)
        .filter(Chapter.project_id == project_id)
        .order_by(Chapter.chapter_index.asc())
        .all()
    )
    characters = session.query(Character).filter(Character.project_id == project_id).all()
    segment_rows = (
        session.query(Segment)
        .filter(Segment.run_id == run.id)
        .order_by(Segment.id.asc())
        .all()
    )
    segments = [segment.segment_json for segment in segment_rows]
    analytics = build_character_occurrence_analytics(
        chapters=chapters,
        characters=characters,
        segment_payloads=segments,
    )
    return CharacterOccurrenceAnalyticsResponse(
        project_id=project_id,
        run_id=run.id,
        **analytics,
    )


@app.get(
    "/api/projects/{project_id}/runs/{run_id}/character-cooccurrence-graph",
    response_model=CharacterCooccurrenceGraphResponse,
    status_code=status.HTTP_200_OK,
)
def get_run_character_cooccurrence_graph(
    project_id: int,
    run_id: int,
    session: Session = Depends(get_session),
) -> CharacterCooccurrenceGraphResponse:
    project = _get_project_or_404(session, project_id)
    run = _get_run_or_404(session, project_id, run_id)
    export_payload = build_run_export(session=session, project=project, run=run)

    manifest = export_payload.get("manifest")
    if not isinstance(manifest, dict):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Run export manifest is missing.",
        )

    academic_reports = manifest.get("academic_reports")
    if not isinstance(academic_reports, dict):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Run academic_reports block is missing.",
        )

    academic_manifest = manifest.get("academic_export_manifest")
    if not isinstance(academic_manifest, dict):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Run academic_export_manifest block is missing.",
        )

    generated_at = academic_manifest.get("generated_at")
    if not isinstance(generated_at, str) or not generated_at.strip():
        generated_at = run.finished_at.isoformat() if run.finished_at else run.started_at.isoformat()

    graph_payload = academic_reports.get("character_cooccurrence_graph")
    centrality_payload = academic_reports.get("character_cooccurrence_centrality_table")

    if not isinstance(graph_payload, dict) or not isinstance(centrality_payload, dict):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character co-occurrence payload is not available for this run.",
        )

    graph_data = {
        "schema_version": "1.0.0",
        "output_schema": "graph_json",
        "output_format": "graph_json",
        "output_id": "AO-004",
        "output_name": "character_cooccurrence_graph",
        "project_id": project.id,
        "run_id": run.id,
        "run_status": run.status,
        "generated_at": generated_at,
        "generated_by": "build_run_export_graph_json",
        "graph": {
            "nodes": graph_payload.get("nodes", []),
            "edges": graph_payload.get("edges", []),
            "metadata": graph_payload.get("metadata", {}),
        },
        "character_cooccurrence_centrality": {
            "metrics_table": centrality_payload.get("metrics_table", []),
            "metadata": centrality_payload.get("metadata", {}),
        },
        "manifest_snapshot": {
            "output_schema": academic_manifest.get("output_schema"),
            "generated_by": academic_manifest.get("generated_by"),
            "generated_at": academic_manifest.get("generated_at"),
        },
    }

    return CharacterCooccurrenceGraphResponse(**graph_data)


@app.get(
    "/api/projects/{project_id}/runs/{run_id}/tension-graph",
    response_model=TensionGraphContractResponse,
    status_code=status.HTTP_200_OK,
)
def get_run_tension_graph(
    project_id: int,
    run_id: int,
    session: Session = Depends(get_session),
) -> TensionGraphContractResponse:
    project = _get_project_or_404(session, project_id)
    run = _get_run_or_404(session, project_id, run_id)
    export_payload = build_run_export(
        session=session,
        project=project,
        run=run,
    )
    manifest = export_payload.get("manifest")
    if not isinstance(manifest, dict):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Run export manifest is missing.",
        )

    academic_reports = manifest.get("academic_reports")
    if not isinstance(academic_reports, dict):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Run academic_reports block is missing.",
        )

    return build_tension_graph_contract(academic_reports)


@app.get(
    "/api/projects/{project_id}/runs/{run_id}/polarity-graph",
    response_model=PolarityGraphResponse,
    status_code=status.HTTP_200_OK,
)
def get_run_polarity_graph(
    project_id: int,
    run_id: int,
    window_size: int = Query(
        default=5,
        ge=1,
        le=100,
        description="Rolling window size for emotional polarity smoothing",
    ),
    session: Session = Depends(get_session),
) -> PolarityGraphResponse:
    project = _get_project_or_404(session, project_id)
    run = _get_run_or_404(session, project_id, run_id)
    export_payload = build_run_export(
        session=session,
        project=project,
        run=run,
    )
    manifest = export_payload.get("manifest")
    if not isinstance(manifest, dict):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Run export manifest is missing.",
        )

    academic_reports = manifest.get("academic_reports")
    if not isinstance(academic_reports, dict):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Run academic_reports block is missing.",
        )

    segments = export_payload.get("segments")
    time_series = export_payload.get("time_series")
    if not isinstance(segments, list):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Run export segments are missing.",
        )

    filtered_segments = []
    for segment in segments:
        if isinstance(segment, dict):
            filtered_segments.append(segment)

    rolling_window_curves = _build_rolling_emotional_curves(
        segments=filtered_segments,
        window_size=window_size,
    )

    adapted_academic_reports = dict(academic_reports)
    adapted_academic_reports["rolling_window_emotional_curves"] = rolling_window_curves

    if isinstance(time_series, Mapping):
        return build_polarity_graph_contract(adapted_academic_reports, time_series)

    return build_polarity_graph_contract(adapted_academic_reports)


@app.get("/api/projects/{project_id}/exports/{run_id}.json", status_code=status.HTTP_200_OK)
def get_export_json(
    project_id: int,
    run_id: int,
    from_chapter_index: int | None = None,
    from_segment_index: int | None = None,
    output_schema: str | None = None,
    output_format: str | None = None,
    output_id: str | None = None,
    session: Session = Depends(get_session),
) -> JSONResponse:
    project = _get_project_or_404(session, project_id)
    run = _get_run_or_404(session, project_id, run_id)
    export_headers = _build_export_correlation_headers(run.config_json)
    settings = get_settings()
    character_rows = session.query(Character).filter(Character.project_id == project.id).all()
    contradiction_review_required = _resolve_contradiction_review_required(project=project, run=run)
    requires_review_count = len(
        [
            payload
            for payload in compare_manual_and_inferred_gender_fields(
                character_rows,
                contradiction_review_threshold=settings.contradiction_review_threshold,
                contradiction_review_required=contradiction_review_required,
            )
            if payload["requires_review"]
        ]
    )
    if requires_review_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": (
                    "Export is blocked because one or more gender contradictions require manual review."
                ),
                "requires_review_count": requires_review_count,
                "threshold": settings.contradiction_review_threshold,
            },
        )

    if (from_chapter_index is None) != (from_segment_index is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from_chapter_index and from_segment_index must be provided together.",
        )

    if output_schema is not None and output_schema not in {"academic", "author"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Unsupported output_schema '{schema}'. Supported values: academic, author."
            ).format(schema=output_schema),
        )

    payload = build_run_export(
        session=session,
        project=project,
        run=run,
        from_chapter_index=from_chapter_index,
        from_segment_index=from_segment_index,
        apply_export_chunk_size=True,
    )

    if output_schema == "academic":
        requested_output_format = (output_format or "json").strip().lower()
        allowed_formats = resolve_run_allowed_export_formats(run)
        allowed_set = set(allowed_formats)
        if requested_output_format not in {"json", "graph_json"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Unsupported output_format for academic schema. "
                    "Supported values: json, graph_json."
                ),
            )
        if requested_output_format not in allowed_set:
            allowed_formats_str = ", ".join(allowed_formats) if allowed_formats else "none"
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Export format '{requested_output_format}' is not allowed for this run. "
                    f"Allowed formats: {allowed_formats_str}."
                ),
            )

        if requested_output_format == "json":
            export_recorded_at = datetime.now(timezone.utc)
            _append_project_activity_event(
                session=session,
                project_id=project.id,
                run_id=run.id,
                event_type="export",
                event_metadata={
                    "output_schema": "academic",
                    "output_format": "json",
                },
            )
            _refresh_project_dashboard_projection(
                session=session,
                project=project,
                export_recorded_at=export_recorded_at,
            )
            session.commit()
            return JSONResponse(content=payload, headers=export_headers)

        if requested_output_format == "graph_json":
            selected_output_id = (output_id or "AO-004").upper()
            if selected_output_id != "AO-004":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Unsupported output_id for graph_json. Supported values: AO-004.",
                )

            manifest = payload.get("manifest", {})
            export_recorded_at = datetime.now(timezone.utc)
            _append_project_activity_event(
                session=session,
                project_id=project.id,
                run_id=run.id,
                event_type="export",
                event_metadata={
                    "output_schema": "academic",
                    "output_format": "graph_json",
                    "output_id": selected_output_id,
                },
            )
            _refresh_project_dashboard_projection(
                session=session,
                project=project,
                export_recorded_at=export_recorded_at,
            )
            session.commit()
            return JSONResponse(
                content=build_run_export_graph_json(
                    project=project,
                    run=run,
                    academic_reports=manifest.get("academic_reports", {}),
                    academic_manifest=manifest.get("academic_export_manifest", {}),
                ),
                headers=export_headers,
            )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Unsupported output_format for academic schema. "
                "Supported values: json, graph_json."
            ),
        )

    if output_schema == "author":
        if output_format and output_format != "json":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported output_format for author schema. Supported values: json.",
            )
        export_recorded_at = datetime.now(timezone.utc)
        _append_project_activity_event(
            session=session,
            project_id=project.id,
            run_id=run.id,
            event_type="export",
            event_metadata={
                "output_schema": "author",
                "output_format": "json",
            },
        )
        _refresh_project_dashboard_projection(
            session=session,
            project=project,
            export_recorded_at=export_recorded_at,
        )
        session.commit()
        return JSONResponse(content=payload["manifest"]["narrative_health_report"], headers=export_headers)

    export_recorded_at = datetime.now(timezone.utc)
    _append_project_activity_event(
        session=session,
        project_id=project.id,
        run_id=run.id,
        event_type="export",
        event_metadata={
            "output_schema": "default",
            "output_format": "json",
        },
    )
    _refresh_project_dashboard_projection(
        session=session,
        project=project,
        export_recorded_at=export_recorded_at,
    )
    session.commit()
    return JSONResponse(content=payload, headers=export_headers)


@app.get("/api/projects/{project_id}/exports/{run_id}.csv", status_code=status.HTTP_200_OK)
def get_export_csv(
    project_id: int,
    run_id: int,
    from_chapter_index: int | None = None,
    from_segment_index: int | None = None,
    output_schema: str | None = None,
    session: Session = Depends(get_session),
) -> Response:
    project = _get_project_or_404(session, project_id)
    run = _get_run_or_404(session, project_id, run_id)
    export_headers = _build_export_correlation_headers(run.config_json)
    settings = get_settings()
    character_rows = session.query(Character).filter(Character.project_id == project.id).all()
    contradiction_review_required = _resolve_contradiction_review_required(project=project, run=run)
    requires_review_count = len(
        [
            payload
            for payload in compare_manual_and_inferred_gender_fields(
                character_rows,
                contradiction_review_threshold=settings.contradiction_review_threshold,
                contradiction_review_required=contradiction_review_required,
            )
            if payload["requires_review"]
        ]
    )
    if requires_review_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": (
                    "Export is blocked because one or more gender contradictions require manual review."
                ),
                "requires_review_count": requires_review_count,
                "threshold": settings.contradiction_review_threshold,
            },
        )

    if (from_chapter_index is None) != (from_segment_index is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from_chapter_index and from_segment_index must be provided together.",
        )

    if output_schema is not None and output_schema != "academic":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported output_schema '{output_schema}'. Supported values: academic.",
        )

    if output_schema == "academic":
        allowed_formats = resolve_run_allowed_export_formats(run)
        if "csv" not in allowed_formats:
            allowed_formats_str = ", ".join(allowed_formats) if allowed_formats else "none"
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"CSV export is not allowed for this run. Allowed formats: {allowed_formats_str}."
                ),
            )

        export_payload = build_run_export(
            session=session,
            project=project,
            run=run,
            from_chapter_index=from_chapter_index,
            from_segment_index=from_segment_index,
            apply_export_chunk_size=True,
        )
        manifest = export_payload.get("manifest", {})
        academic_reports = manifest.get("academic_reports", {})
        academic_manifest = manifest.get("academic_export_manifest", {})
        csv_data = build_run_export_academic_csv(
            project=project,
            run=run,
            academic_reports=academic_reports,
            academic_manifest=academic_manifest,
        )
        filename = f"project-{project_id}-run-{run_id}-academic.csv"
        export_recorded_at = datetime.now(timezone.utc)
        _append_project_activity_event(
            session=session,
            project_id=project.id,
            run_id=run.id,
            event_type="export",
            event_metadata={
                "output_schema": "academic",
                "output_format": "csv",
            },
        )
        _refresh_project_dashboard_projection(
            session=session,
            project=project,
            export_recorded_at=export_recorded_at,
        )
        session.commit()
    else:
        csv_data = build_run_export_csv(
            session=session,
            project=project,
            run=run,
            from_chapter_index=from_chapter_index,
            from_segment_index=from_segment_index,
            apply_export_chunk_size=True,
        )
        filename = f"project-{project_id}-run-{run_id}.csv"
        export_recorded_at = datetime.now(timezone.utc)
        _append_project_activity_event(
            session=session,
            project_id=project.id,
            run_id=run.id,
            event_type="export",
            event_metadata={
                "output_schema": "default",
                "output_format": "csv",
            },
        )
        _refresh_project_dashboard_projection(
            session=session,
            project=project,
            export_recorded_at=export_recorded_at,
        )
        session.commit()
    response_headers = dict(export_headers)
    response_headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers=response_headers,
    )
