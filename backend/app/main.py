from datetime import datetime, timezone

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_session, init_db
from app.modes import DEFAULT_MODE, get_mode_catalog
from app.models import Chapter, Character, LLMCall, Project, PronunciationDictionary, Run, Segment
from app.schemas import (
    CharacterImportResponse,
    CharacterMapItem,
    CharacterMapResponse,
    CharacterMapUpdateRequest,
    CharacterMapFinalizeResponse,
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
    CharacterExtractionResponse,
    CharacterScrapeRequest,
    CharacterCandidatesMergeRequest,
    CharacterGenderComparisonItem,
    CharacterGenderComparisonResponse,
    ModeCatalogResponse,
    ProjectCreate,
    ProjectModeSwitchRequest,
    ProjectModeSwitchResponse,
    ProjectResponse,
    RunCreateRequest,
    CharacterOccurrenceAnalyticsResponse,
    RunDetailResponse,
    RunResponse,
    VoiceConfigRequest,
    VoiceConfigResponse,
)
from app.services.characters import parse_character_file
from app.services.character_extraction import extract_character_candidates_from_texts
from app.services.character_scrape import extract_character_candidates_from_scrape_url
from app.services.epub_ingestion import extract_epub_chapters
from app.services.character_merge import build_canonical_name_merge_suggestions, merge_character_candidates
from app.services.character_merge import normalize_candidate_key
from app.services.character_merge import detect_alias_conflicts
from app.services.character_merge import resolve_alias_to_canonical_name
from app.services.export import build_run_export, build_run_export_csv
from app.services.ingestion_errors import IngestionErrorType, make_ingestion_http_error
from app.services.ingestion import (
    build_duplicate_title_dedup_actions,
    build_duplicate_title_warnings,
    build_encoding_warning,
    build_internal_chapter_id,
    calculate_delta_affected_range,
    chapter_filename_sort_key,
    chapter_title_from_filename,
    contains_explicit_chapter_header,
    decode_text,
    decode_text_with_metadata,
    detect_append_overlap_or_duplicate,
    detect_chapters,
    detect_chapters_from_file_boundaries,
    detect_title_with_fallback,
    detect_text_encoding,
    extract_single_append_chapter,
    is_likely_unsupported_encoding,
    normalize_markdown_for_ingestion,
    to_internal_utf8,
)
from app.services.mode_profiles import PROFILE_CONFIG_KEYS, build_run_config_snapshot
from app.services.mode_switch import mark_runs_stale_for_gender_edit, mark_runs_stale_for_mode_switch
from app.services.character_analytics import build_character_occurrence_analytics
from app.services.gender_comparison import compare_manual_and_inferred_gender_fields
from app.services.gender_inference import infer_character_genders
from app.services.normalization import (
    build_original_to_normalized_offset_map,
    build_normalization_report,
    normalize_text_with_report,
)
from app.services.voice_preview import recompute_voice_previews_for_runs
from app.services.pipeline import PipelineError, execute_pipeline
from app.services.voice import DEFAULT_VOICE_CONFIG, _normalize_internal_thought_voice_policy
from app.services.phonetics import replace_pronunciations_with_counts

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


def _merge_selected_modes(existing_modes: list[str] | None, mode: str) -> list[str]:
    merged = list(existing_modes or [])
    if mode not in merged:
        merged.append(mode)
    return merged


def _build_initial_configuration_snapshot_id(project_id: int) -> str:
    return f"project-{project_id}-config-initial"


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
    "/api/projects/{project_id}/characters/gender-comparison",
    response_model=CharacterGenderComparisonResponse,
    status_code=status.HTTP_200_OK,
)
def compare_character_genders(
    project_id: int,
    include_only_conflicts: bool = False,
    session: Session = Depends(get_session),
) -> CharacterGenderComparisonResponse:
    _get_project_or_404(session, project_id)
    settings = get_settings()

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
            contradiction_review_threshold=settings.contradiction_review_threshold,
        )
    ]

    contradiction_count = len([payload for payload in comparison_payloads if payload.is_contradiction])

    return CharacterGenderComparisonResponse(
        project_id=project_id,
        comparison_count=len(comparison_payloads),
        contradiction_count=contradiction_count,
        comparisons=comparison_payloads,
    )


def _build_mergeable_candidates_from_candidates(
    candidates: list[object],
    source: str,
) -> list[dict[str, object]]:
    payloads: list[dict[str, object]] = []
    for candidate in candidates:
        source_trace = list(getattr(candidate, "source_trace", []))
        inferred_gender = str(getattr(candidate, "inferred_gender", "unknown")).strip().lower() or "unknown"
        inferred_source_trace = list(getattr(candidate, "inferred_source_trace", []))
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
                "source_trace": [
                    {
                        "kind": trace.kind,
                        "chapter_index": trace.chapter_index,
                        "span_start": trace.span_start,
                        "span_end": trace.span_end,
                        "excerpt": trace.excerpt,
                        "weight": trace.weight,
                    }
                    for trace in getattr(candidate, "source_trace", [])
                ],
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


@app.post("/api/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, session: Session = Depends(get_session)) -> ProjectResponse:
    project = Project(
        title=payload.title.strip(),
        selected_mode=DEFAULT_MODE,
        selected_modes=[DEFAULT_MODE],
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
        character_map_finalized=project.character_map_finalized,
        configuration_snapshot_id=project.configuration_snapshot_id,
        ingestion_timestamp=project.ingestion_timestamp,
        created_at=project.created_at,
    )


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

    project.selected_mode = payload.mode
    project.selected_modes = _merge_selected_modes(project.selected_modes, payload.mode)
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

    filename = file.filename or ""
    if not filename.lower().endswith(".txt"):
        raise make_ingestion_http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_type=IngestionErrorType.UNSUPPORTED_FORMAT,
            detail="Only .txt files are supported",
        )

    payload = file.file.read()
    raw_text, encoding, confidence = decode_text_with_metadata(payload)
    if is_likely_unsupported_encoding(raw_text):
        raise make_ingestion_http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_type=IngestionErrorType.UNSUPPORTED_ENCODING,
            detail="Unable to decode TXT content reliably with supported encodings",
        )
    detected_title = detect_title_with_fallback(raw_text, filename=filename)
    chapters = [(title, content) for title, content in detect_chapters(raw_text) if content.strip()]
    if not chapters:
        raise make_ingestion_http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_type=IngestionErrorType.MISSING_CHAPTERS,
            detail="No non-empty chapters found in TXT input",
        )
    warnings: list[dict[str, object]] = []
    chapter_normalization_reports: list[dict[str, object]] = []
    encoding_warnings: list[dict[str, object]] = []
    txt_warning = build_encoding_warning("txt", encoding, confidence)
    if txt_warning is not None:
        warnings.append(txt_warning)
        encoding_warnings.append(txt_warning)
    duplicate_title_warnings = build_duplicate_title_warnings("txt", chapters)
    warnings.extend(duplicate_title_warnings)
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
        warnings.extend(quote_warnings)
        session.add(
            Chapter(
                project_id=project_id,
                chapter_index=idx,
                chapter_internal_id=build_internal_chapter_id(idx),
                chapter_title=chapter_title,
                raw_text=chapter_content,
                original_text_snapshot=chapter_content,
                normalized_text=normalized,
                normalized_text_snapshot=normalized,
                original_to_normalized_offset_map=chapter_offset_map,
            )
        )
    normalization_report = build_normalization_report(
        source="txt",
        chapter_count=len(chapter_normalization_reports),
        chapter_reports=chapter_normalization_reports,
        suspected_duplicate_title_count=len(duplicate_title_warnings),
        encoding_issue_count=len(encoding_warnings),
    )

    if _project_title_needs_fallback(project.title):
        project.title = to_internal_utf8(detected_title)
    _update_project_ingestion_log(
        project,
        source="txt",
        warnings=warnings,
        dedup_actions=dedup_actions,
        normalization_report=normalization_report,
    )
    project.ingestion_timestamp = datetime.now(timezone.utc)
    session.add(project)
    session.commit()

    return IngestResponse(project_id=project_id, chapter_count=len(chapters))


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

    filename = file.filename or ""
    lower_filename = filename.lower()
    if not (lower_filename.endswith(".md") or lower_filename.endswith(".markdown")):
        raise make_ingestion_http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_type=IngestionErrorType.UNSUPPORTED_FORMAT,
            detail="Only .md or .markdown files are supported",
        )

    payload = file.file.read()
    markdown_text, encoding, confidence = decode_text_with_metadata(payload)
    if is_likely_unsupported_encoding(markdown_text):
        raise make_ingestion_http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_type=IngestionErrorType.UNSUPPORTED_ENCODING,
            detail="Unable to decode Markdown content reliably with supported encodings",
        )
    normalized_source = normalize_markdown_for_ingestion(markdown_text)
    detected_title = detect_title_with_fallback(normalized_source, filename=filename)
    chapters = [(title, content) for title, content in detect_chapters(normalized_source) if content.strip()]
    if not chapters:
        raise make_ingestion_http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_type=IngestionErrorType.MISSING_CHAPTERS,
            detail="No non-empty chapters found in Markdown input",
        )
    warnings: list[dict[str, object]] = []
    chapter_normalization_reports: list[dict[str, object]] = []
    encoding_warnings: list[dict[str, object]] = []
    markdown_warning = build_encoding_warning("markdown", encoding, confidence)
    if markdown_warning is not None:
        warnings.append(markdown_warning)
        encoding_warnings.append(markdown_warning)
    duplicate_title_warnings = build_duplicate_title_warnings("markdown", chapters)
    warnings.extend(duplicate_title_warnings)
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
        warnings.extend(quote_warnings)
        session.add(
            Chapter(
                project_id=project_id,
                chapter_index=chapter_index,
                chapter_internal_id=build_internal_chapter_id(chapter_index),
                chapter_title=stored_chapter_title,
                raw_text=stored_chapter_content,
                original_text_snapshot=stored_chapter_content,
                normalized_text=normalized,
                normalized_text_snapshot=normalized,
                original_to_normalized_offset_map=chapter_offset_map,
            )
        )
    normalization_report = build_normalization_report(
        source="markdown",
        chapter_count=len(chapter_normalization_reports),
        chapter_reports=chapter_normalization_reports,
        suspected_duplicate_title_count=len(duplicate_title_warnings),
        encoding_issue_count=len(encoding_warnings),
    )

    if _project_title_needs_fallback(project.title):
        project.title = to_internal_utf8(detected_title)
    _update_project_ingestion_log(
        project,
        source="markdown",
        warnings=warnings,
        dedup_actions=dedup_actions,
        normalization_report=normalization_report,
    )
    project.ingestion_timestamp = datetime.now(timezone.utc)
    session.add(project)
    session.commit()

    return IngestResponse(project_id=project_id, chapter_count=len(chapters))


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
    filename = file.filename or ""
    if not filename.lower().endswith(".epub"):
        raise make_ingestion_http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_type=IngestionErrorType.UNSUPPORTED_FORMAT,
            detail="Only .epub files are supported",
        )

    payload = file.file.read()
    try:
        chapters = extract_epub_chapters(payload)
    except NotImplementedError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc)) from exc

    if not chapters:
        raise make_ingestion_http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_type=IngestionErrorType.MISSING_CHAPTERS,
            detail="No chapter content found in EPUB",
        )

    warnings: list[dict[str, object]] = []
    chapter_normalization_reports: list[dict[str, object]] = []
    duplicate_title_warnings = build_duplicate_title_warnings("epub", chapters)
    warnings.extend(duplicate_title_warnings)
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
        warnings.extend(quote_warnings)
        session.add(
            Chapter(
                project_id=project_id,
                chapter_index=chapter_index,
                chapter_internal_id=build_internal_chapter_id(chapter_index),
                chapter_title=title,
                raw_text=content,
                original_text_snapshot=content,
                normalized_text=normalized,
                normalized_text_snapshot=normalized,
                original_to_normalized_offset_map=chapter_offset_map,
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
        encoding_issue_count=encoding_issue_count,
    )
    _update_project_ingestion_log(
        project,
        source="epub",
        warnings=warnings,
        dedup_actions=build_duplicate_title_dedup_actions("epub", chapters),
        normalization_report=normalization_report,
    )
    project.ingestion_timestamp = datetime.now(timezone.utc)
    session.add(project)
    session.commit()

    chapter_count = session.query(Chapter).filter(Chapter.project_id == project_id).count()
    if chapter_count == 0:
        raise make_ingestion_http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_type=IngestionErrorType.MISSING_CHAPTERS,
            detail="No non-empty chapter content found in EPUB",
        )
    return IngestResponse(project_id=project_id, chapter_count=chapter_count)


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
    if not files:
        raise make_ingestion_http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_type=IngestionErrorType.MISSING_CHAPTERS,
            detail="At least one chapter file is required",
        )

    sorted_files = sorted(files, key=lambda upload: chapter_filename_sort_key(upload.filename or ""))

    file_boundaries: list[tuple[str, str]] = []
    warnings: list[dict[str, object]] = []
    encoding_warnings: list[dict[str, object]] = []
    chapter_normalization_reports: list[dict[str, object]] = []
    for upload in sorted_files:
        filename = upload.filename or ""
        if not filename.lower().endswith(".txt"):
            raise make_ingestion_http_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_type=IngestionErrorType.UNSUPPORTED_FORMAT,
                detail="Chapter directory only supports .txt files",
            )

        payload = upload.file.read()
        content = decode_text(payload).strip()
        if is_likely_unsupported_encoding(content):
            raise make_ingestion_http_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_type=IngestionErrorType.UNSUPPORTED_ENCODING,
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
    dedup_actions = build_duplicate_title_dedup_actions("chapters-dir", chapter_rows)

    if not chapter_rows:
        raise make_ingestion_http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_type=IngestionErrorType.MISSING_CHAPTERS,
            detail="No non-empty chapter content found",
        )

    session.query(Chapter).filter(Chapter.project_id == project_id).delete()

    for chapter_index, (chapter_title, chapter_content) in enumerate(chapter_rows, start=1):
        normalized, quote_warnings, chapter_report = normalize_text_with_report(
            chapter_content,
            source="chapters-dir",
        )
        chapter_normalization_reports.append(chapter_report)
        chapter_offset_map = build_original_to_normalized_offset_map(chapter_content, normalized)
        warnings.extend(quote_warnings)
        session.add(
            Chapter(
                project_id=project_id,
                chapter_index=chapter_index,
                chapter_internal_id=build_internal_chapter_id(chapter_index),
                chapter_title=chapter_title,
                raw_text=chapter_content,
                original_text_snapshot=chapter_content,
                normalized_text=normalized,
                normalized_text_snapshot=normalized,
                original_to_normalized_offset_map=chapter_offset_map,
            )
        )

    if _project_title_needs_fallback(project.title):
        project.title = to_internal_utf8(chapter_rows[0][0])
    normalization_report = build_normalization_report(
        source="chapters-dir",
        chapter_count=len(chapter_normalization_reports),
        chapter_reports=chapter_normalization_reports,
        suspected_duplicate_title_count=len(duplicate_title_warnings),
        encoding_issue_count=len(encoding_warnings),
    )
    _update_project_ingestion_log(
        project,
        source="chapters-dir",
        warnings=warnings,
        dedup_actions=dedup_actions,
        normalization_report=normalization_report,
    )
    project.ingestion_timestamp = datetime.now(timezone.utc)
    session.add(project)
    session.commit()

    return IngestResponse(project_id=project_id, chapter_count=len(chapter_rows))


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

    filename = file.filename or ""
    if not filename.lower().endswith(".txt"):
        raise make_ingestion_http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_type=IngestionErrorType.UNSUPPORTED_FORMAT,
            detail="Append chapter only supports .txt files",
        )

    payload = file.file.read()
    raw_text, encoding, confidence = decode_text_with_metadata(payload)
    if is_likely_unsupported_encoding(raw_text):
        raise make_ingestion_http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_type=IngestionErrorType.UNSUPPORTED_ENCODING,
            detail="Unable to decode appended chapter reliably with supported encodings",
        )
    has_explicit_header = contains_explicit_chapter_header(raw_text)
    parsed_chapters = detect_chapters(raw_text)
    fallback_title = chapter_title_from_filename(filename, chapter_index=_get_next_chapter_index(session, project_id))
    try:
        parsed_title, parsed_content = extract_single_append_chapter(parsed_chapters, fallback_title=fallback_title)
    except ValueError as exc:
        raise make_ingestion_http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_type=IngestionErrorType.MISSING_CHAPTERS,
            detail=str(exc),
        ) from exc

    next_chapter_index = _get_next_chapter_index(session, project_id)
    chapter_title = to_internal_utf8(parsed_title if has_explicit_header else fallback_title)
    chapter_content = to_internal_utf8(parsed_content)
    existing_chapters = (
        session.query(Chapter.chapter_index, Chapter.chapter_title, Chapter.raw_text)
        .filter(Chapter.project_id == project_id)
        .order_by(Chapter.chapter_index.asc())
        .all()
    )
    overlap_match = detect_append_overlap_or_duplicate(
        new_title=chapter_title,
        new_content=chapter_content,
        existing_chapters=[(row[0], row[1], row[2]) for row in existing_chapters],
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
    warnings: list[dict[str, object]] = [warning] if warning is not None else []
    warnings.extend(quote_warnings)
    combined_titles = [(row[1], row[2]) for row in existing_chapters] + [(chapter_title, chapter_content)]
    duplicate_title_warnings = build_duplicate_title_warnings("append-chapter", combined_titles)
    warnings.extend(duplicate_title_warnings)
    dedup_actions = build_duplicate_title_dedup_actions("append-chapter", combined_titles)

    session.add(
        Chapter(
            project_id=project_id,
            chapter_index=next_chapter_index,
            chapter_internal_id=build_internal_chapter_id(next_chapter_index),
            chapter_title=chapter_title,
            raw_text=chapter_content,
            original_text_snapshot=chapter_content,
            normalized_text=normalized,
            normalized_text_snapshot=normalized,
            original_to_normalized_offset_map=chapter_offset_map,
        )
    )

    affected_range = calculate_delta_affected_range(
        changed_chapter_indices=[next_chapter_index],
        total_chapter_count=len(existing_chapters) + 1,
    )
    _update_project_ingestion_log(
        project,
        source="append-chapter",
        warnings=warnings,
        dedup_actions=dedup_actions,
        affected_range=affected_range,
        normalization_report=build_normalization_report(
            source="append-chapter",
            chapter_count=1,
            chapter_reports=chapter_normalization_reports,
            suspected_duplicate_title_count=len(duplicate_title_warnings),
            encoding_issue_count=len(encoding_warnings),
        ),
    )
    project.ingestion_timestamp = datetime.now(timezone.utc)
    session.add(project)
    session.commit()

    chapter_count = session.query(Chapter).filter(Chapter.project_id == project_id).count()
    return IngestResponse(project_id=project_id, chapter_count=chapter_count)


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


@app.post(
    "/api/projects/{project_id}/characters/extract",
    response_model=CharacterExtractionResponse,
    status_code=status.HTTP_200_OK,
)
def auto_extract_characters(
    project_id: int,
    session: Session = Depends(get_session),
) -> CharacterExtractionResponse:
    _get_project_or_404(session, project_id)

    chapter_rows = (
        session.query(Chapter.normalized_text)
        .filter(Chapter.project_id == project_id)
        .order_by(Chapter.chapter_index.asc())
        .all()
    )
    if not chapter_rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No chapters available for character auto-extraction.",
        )

    existing_names = {
        row.name.strip().lower()
        for row in session.query(Character.name).filter(Character.project_id == project_id).all()
    }

    candidates = extract_character_candidates_from_texts(
        [row.normalized_text for row in chapter_rows],
        known_names=existing_names,
    )
    mapped_candidates = [
        CharacterMapItem(**candidate_payload)
        for candidate_payload in _build_mergeable_candidates_from_candidates(
            candidates,
            source="auto",
        )
    ]

    return CharacterExtractionResponse(
        project_id=project_id,
        status="complete",
        candidate_count=len(mapped_candidates),
        candidates=mapped_candidates,
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

    mapped_candidates = [
        CharacterMapItem(**candidate_payload)
        for candidate_payload in _build_mergeable_candidates_from_candidates(
            candidates,
            source="scrape",
        )
    ]

    return CharacterExtractionResponse(
        project_id=project_id,
        status="complete",
        candidate_count=len(mapped_candidates),
        candidates=mapped_candidates,
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


@app.post(
    "/api/projects/{project_id}/runs",
    response_model=RunResponse,
    status_code=status.HTTP_200_OK,
)
def create_run(
    project_id: int,
    payload: RunCreateRequest,
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
    _coalesce_internal_thought_policy(project=project, explicit_overrides=explicit_overrides)
    run_config = build_run_config_snapshot(
        mode=payload.mode,
        overrides=explicit_overrides,
    )
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

    project.selected_mode = str(run_config["mode"])
    project.selected_modes = _merge_selected_modes(project.selected_modes, project.selected_mode)
    run = Run(
        project_id=project.id,
        status="running",
        config_json=run_config,
        started_at=datetime.now(timezone.utc),
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    try:
        result = execute_pipeline(
            session=session,
            project=project,
            run=run,
            run_config=run_config,
        )
        session.commit()
    except PipelineError as exc:
        session.rollback()
        run = _get_run_or_404(session, project.id, run.id)
        run.status = "failed"
        run.finished_at = datetime.now(timezone.utc)
        session.add(run)
        session.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        run = _get_run_or_404(session, project.id, run.id)
        run.status = "failed"
        run.finished_at = datetime.now(timezone.utc)
        session.add(run)
        session.commit()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Pipeline failed") from exc

    return RunResponse(
        run_id=run.id,
        project_id=project.id,
        status=run.status,
        segment_count=result["segment_count"],
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

    call_payload = [
        {
            "id": call.id,
            "provider": call.provider,
            "task_type": call.task_type,
            "success": call.success,
            "request_count": call.request_count,
            "detail": call.detail,
            "created_at": call.created_at.isoformat(),
        }
        for call in llm_calls
    ]

    return RunDetailResponse(
        run_id=run.id,
        project_id=project_id,
        status=run.status,
        config=run.config_json,
        started_at=run.started_at,
        finished_at=run.finished_at,
        segment_count=segment_count,
        llm_calls=call_payload,
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


@app.get("/api/projects/{project_id}/exports/{run_id}.json", status_code=status.HTTP_200_OK)
def get_export_json(project_id: int, run_id: int, session: Session = Depends(get_session)) -> JSONResponse:
    project = _get_project_or_404(session, project_id)
    run = _get_run_or_404(session, project_id, run_id)
    settings = get_settings()
    character_rows = session.query(Character).filter(Character.project_id == project.id).all()
    requires_review_count = len(
        [
            payload
            for payload in compare_manual_and_inferred_gender_fields(
                character_rows,
                contradiction_review_threshold=settings.contradiction_review_threshold,
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

    payload = build_run_export(session, project, run)
    return JSONResponse(content=payload)


@app.get("/api/projects/{project_id}/exports/{run_id}.csv", status_code=status.HTTP_200_OK)
def get_export_csv(project_id: int, run_id: int, session: Session = Depends(get_session)) -> Response:
    project = _get_project_or_404(session, project_id)
    run = _get_run_or_404(session, project_id, run_id)
    settings = get_settings()
    character_rows = session.query(Character).filter(Character.project_id == project.id).all()
    requires_review_count = len(
        [
            payload
            for payload in compare_manual_and_inferred_gender_fields(
                character_rows,
                contradiction_review_threshold=settings.contradiction_review_threshold,
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

    csv_data = build_run_export_csv(session, project, run)
    filename = f"project-{project_id}-run-{run_id}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
