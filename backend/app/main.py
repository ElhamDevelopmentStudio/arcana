from datetime import datetime, timezone

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_session, init_db
from app.modes import DEFAULT_MODE, get_mode_catalog
from app.models import Chapter, Character, LLMCall, Project, Run, Segment
from app.schemas import (
    CharacterImportResponse,
    IngestResponse,
    ModeCatalogResponse,
    ProjectCreate,
    ProjectModeSwitchRequest,
    ProjectModeSwitchResponse,
    ProjectResponse,
    RunCreateRequest,
    RunDetailResponse,
    RunResponse,
    VoiceConfigRequest,
    VoiceConfigResponse,
)
from app.services.characters import parse_character_file
from app.services.epub_ingestion import extract_epub_chapters
from app.services.export import build_run_export
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
from app.services.mode_profiles import build_run_config_snapshot
from app.services.mode_switch import mark_runs_stale_for_mode_switch
from app.services.normalization import normalize_text_with_warnings
from app.services.pipeline import PipelineError, execute_pipeline
from app.services.voice import DEFAULT_VOICE_CONFIG

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


@app.post("/api/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, session: Session = Depends(get_session)) -> ProjectResponse:
    project = Project(
        title=payload.title.strip(),
        selected_mode=DEFAULT_MODE,
        selected_modes=[DEFAULT_MODE],
        voice_config_json=dict(DEFAULT_VOICE_CONFIG),
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
    txt_warning = build_encoding_warning("txt", encoding, confidence)
    if txt_warning is not None:
        warnings.append(txt_warning)
    warnings.extend(build_duplicate_title_warnings("txt", chapters))
    dedup_actions = build_duplicate_title_dedup_actions("txt", chapters)

    session.query(Chapter).filter(Chapter.project_id == project_id).delete()

    for idx, (title, content) in enumerate(chapters, start=1):
        chapter_title = to_internal_utf8(title)
        chapter_content = to_internal_utf8(content)
        normalized, quote_warnings = normalize_text_with_warnings(chapter_content, source="txt")
        warnings.extend(quote_warnings)
        session.add(
            Chapter(
                project_id=project_id,
                chapter_index=idx,
                chapter_internal_id=build_internal_chapter_id(idx),
                chapter_title=chapter_title,
                raw_text=chapter_content,
                normalized_text=normalized,
            )
        )

    if _project_title_needs_fallback(project.title):
        project.title = to_internal_utf8(detected_title)
    _update_project_ingestion_log(project, source="txt", warnings=warnings, dedup_actions=dedup_actions)
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
    markdown_warning = build_encoding_warning("markdown", encoding, confidence)
    if markdown_warning is not None:
        warnings.append(markdown_warning)
    warnings.extend(build_duplicate_title_warnings("markdown", chapters))
    dedup_actions = build_duplicate_title_dedup_actions("markdown", chapters)

    session.query(Chapter).filter(Chapter.project_id == project_id).delete()

    for chapter_index, (chapter_title, chapter_content) in enumerate(chapters, start=1):
        stored_chapter_title = to_internal_utf8(chapter_title)
        stored_chapter_content = to_internal_utf8(chapter_content)
        normalized, quote_warnings = normalize_text_with_warnings(
            stored_chapter_content,
            source="markdown",
        )
        warnings.extend(quote_warnings)
        session.add(
            Chapter(
                project_id=project_id,
                chapter_index=chapter_index,
                chapter_internal_id=build_internal_chapter_id(chapter_index),
                chapter_title=stored_chapter_title,
                raw_text=stored_chapter_content,
                normalized_text=normalized,
            )
        )

    if _project_title_needs_fallback(project.title):
        project.title = to_internal_utf8(detected_title)
    _update_project_ingestion_log(project, source="markdown", warnings=warnings, dedup_actions=dedup_actions)
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
    session.query(Chapter).filter(Chapter.project_id == project_id).delete()

    for chapter_index, (chapter_title, chapter_content) in enumerate(chapters, start=1):
        title = to_internal_utf8(chapter_title.strip() or f"Chapter {chapter_index}")
        content = to_internal_utf8(chapter_content.strip())
        if not content:
            continue
        normalized, quote_warnings = normalize_text_with_warnings(content, source="epub")
        warnings.extend(quote_warnings)
        session.add(
            Chapter(
                project_id=project_id,
                chapter_index=chapter_index,
                chapter_internal_id=build_internal_chapter_id(chapter_index),
                chapter_title=title,
                raw_text=content,
                normalized_text=normalized,
            )
        )

    if _project_title_needs_fallback(project.title):
        project.title = to_internal_utf8(
            chapters[0][0].strip() or detect_title_with_fallback("", filename=filename)
        )
    _update_project_ingestion_log(
        project,
        source="epub",
        warnings=warnings + build_duplicate_title_warnings("epub", chapters),
        dedup_actions=build_duplicate_title_dedup_actions("epub", chapters),
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
        if not content:
            continue

        file_boundaries.append((filename, to_internal_utf8(content)))

    chapter_rows = [
        (to_internal_utf8(chapter_title), to_internal_utf8(chapter_content))
        for chapter_title, chapter_content in detect_chapters_from_file_boundaries(file_boundaries)
    ]
    warnings.extend(build_duplicate_title_warnings("chapters-dir", chapter_rows))
    dedup_actions = build_duplicate_title_dedup_actions("chapters-dir", chapter_rows)

    if not chapter_rows:
        raise make_ingestion_http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_type=IngestionErrorType.MISSING_CHAPTERS,
            detail="No non-empty chapter content found",
        )

    session.query(Chapter).filter(Chapter.project_id == project_id).delete()

    for chapter_index, (chapter_title, chapter_content) in enumerate(chapter_rows, start=1):
        normalized, quote_warnings = normalize_text_with_warnings(
            chapter_content,
            source="chapters-dir",
        )
        warnings.extend(quote_warnings)
        session.add(
            Chapter(
                project_id=project_id,
                chapter_index=chapter_index,
                chapter_internal_id=build_internal_chapter_id(chapter_index),
                chapter_title=chapter_title,
                raw_text=chapter_content,
                normalized_text=normalized,
            )
        )

    if _project_title_needs_fallback(project.title):
        project.title = to_internal_utf8(chapter_rows[0][0])
    _update_project_ingestion_log(project, source="chapters-dir", warnings=warnings, dedup_actions=dedup_actions)
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
    normalized, quote_warnings = normalize_text_with_warnings(chapter_content, source="append-chapter")
    warnings: list[dict[str, object]] = [warning] if warning is not None else []
    warnings.extend(quote_warnings)
    combined_titles = [(row[1], row[2]) for row in existing_chapters] + [(chapter_title, chapter_content)]
    warnings.extend(build_duplicate_title_warnings("append-chapter", combined_titles))
    dedup_actions = build_duplicate_title_dedup_actions("append-chapter", combined_titles)

    session.add(
        Chapter(
            project_id=project_id,
            chapter_index=next_chapter_index,
            chapter_internal_id=build_internal_chapter_id(next_chapter_index),
            chapter_title=chapter_title,
            raw_text=chapter_content,
            normalized_text=normalized,
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
    _get_project_or_404(session, project_id)

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
            )
        )

    session.commit()

    return CharacterImportResponse(project_id=project_id, imported_count=len(parsed))


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

    project.voice_config_json = {
        "narrator_voice": payload.narrator_voice,
        "male_default_voice": payload.male_default_voice,
        "female_default_voice": payload.female_default_voice,
    }
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

    explicit_overrides = payload.model_dump(exclude={"mode"}, exclude_unset=True)
    config_snapshot = build_run_config_snapshot(mode=payload.mode, overrides=explicit_overrides)
    config_snapshot["ingestion_warnings"] = list((project.ingestion_log_json or {}).get("warnings", []))

    project.selected_mode = str(config_snapshot["mode"])
    project.selected_modes = _merge_selected_modes(project.selected_modes, project.selected_mode)
    run = Run(
        project_id=project.id,
        status="running",
        config_json=config_snapshot,
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
            run_config=config_snapshot,
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


@app.get("/api/projects/{project_id}/exports/{run_id}.json", status_code=status.HTTP_200_OK)
def get_export_json(project_id: int, run_id: int, session: Session = Depends(get_session)) -> JSONResponse:
    project = _get_project_or_404(session, project_id)
    run = _get_run_or_404(session, project_id, run_id)

    payload = build_run_export(session, project, run)
    return JSONResponse(content=payload)
