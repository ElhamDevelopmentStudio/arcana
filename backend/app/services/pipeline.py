from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Chapter,
    Character,
    LLMCall,
    LLMCache,
    Project,
    PronunciationDictionary,
    Run,
    Segment,
    SubSegmentTag,
)
from app.services.export import build_run_export
from app.services.llm_router import (
    LLMRequest,
    LLMRouter,
    get_provider_api_keys,
    get_provider_priority_order,
    get_provider_runtime_settings,
    is_supported_provider,
)
from app.services.provider_toggle import is_provider_enabled
from app.services.character_merge import normalize_candidate_key
from app.services.character_analytics import (
    build_character_occurrence_analytics,
)
from app.services.llm_task_types import LLMTaskType
from app.services.phonetics import replace_pronunciations
from app.services.quota import (
    consume_quota,
    consume_api_key_quota,
    mark_provider_available,
    mark_api_key_rate_limited,
    mark_api_key_reset_at,
    mark_api_key_successful_call,
    mark_provider_rate_limited,
    mark_provider_reset_at,
    mark_provider_successful_call,
)
from app.services.segmentation import segment_text_with_parent_paragraph
from app.services.tagging import tag_segment
from app.services.normalization import build_segment_level_offset_map
from app.services.voice import (
    _normalize_internal_thought_voice_policy,
    build_effective_voice_config,
    resolve_voice,
)

_LOW_GENDER_CONFIDENCE = 0.0
_LOW_CONFIDENCE_GENDERS = frozenset({"neutral", "unknown"})
_AMBIGUOUS_CHARACTER_REFERENCE = object()
_LLM_CONFIDENCE_THRESHOLD_DEFAULT = 0.6


class PipelineError(RuntimeError):
    pass


def _coerce_confidence(value: object) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return _LOW_GENDER_CONFIDENCE
    if confidence < 0.0:
        return 0.0
    if confidence > 1.0:
        return 1.0
    return round(confidence, 4)


def _coerce_confidence_threshold(value: object) -> float:
    try:
        threshold = float(value)
    except (TypeError, ValueError):
        return _LLM_CONFIDENCE_THRESHOLD_DEFAULT
    if threshold < 0.0:
        return 0.0
    if threshold > 1.0:
        return 1.0
    return round(threshold, 4)


def _build_llm_cache_key(input_text: str) -> str:
    return sha256(str(input_text).encode("utf-8")).hexdigest()


def _get_cached_llm_response(
    session: Session,
    *,
    input_text: str,
    task_type: str,
    configuration_snapshot_id: str,
    model_identifier: str | None,
) -> LLMCache | None:
    model_id = (str(model_identifier or "").strip()) or None
    if model_id is None:
        return None

    input_text_hash = _build_llm_cache_key(input_text)
    return (
        session.query(LLMCache)
        .filter(
            LLMCache.input_text_hash == input_text_hash,
            LLMCache.task_type == task_type,
            LLMCache.configuration_snapshot_id == configuration_snapshot_id,
            LLMCache.model_identifier == model_id,
        )
        .one_or_none()
    )


def _coerce_call_timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)

    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _build_probe_provider_order(requested_provider: str, settings: object) -> tuple[str, ...]:
    requested_provider_normalized = _normalize_provider_name_for_llm(requested_provider)
    ordered: list[str] = [requested_provider_normalized]
    for provider in get_provider_priority_order(settings=settings):
        normalized = _normalize_provider_name_for_llm(provider)
        if normalized and normalized not in ordered:
            ordered.append(normalized)
    return tuple(ordered)


def _normalize_provider_name_for_llm(value: object) -> str:
    return str(value).strip().lower()


def _resolve_gender_confidence(
    speaker: str,
    character_lookup: dict[str, dict[str, object] | object],
) -> float:
    if not speaker:
        return _LOW_GENDER_CONFIDENCE

    entry = _character_lookup_entry_for_speaker(speaker=speaker, character_lookup=character_lookup)
    if entry is None:
        return _LOW_GENDER_CONFIDENCE

    gender = str(entry.get("gender", "unknown")).strip().lower() or "unknown"
    if gender in _LOW_CONFIDENCE_GENDERS:
        return _LOW_GENDER_CONFIDENCE

    return _coerce_confidence(entry.get("confidence"))


def _character_lookup_entry_for_speaker(
    speaker: str,
    character_lookup: dict[str, dict[str, object] | object],
) -> dict[str, object] | None:
    normalized_speaker = normalize_candidate_key(speaker)
    if not normalized_speaker:
        return None

    entry = character_lookup.get(normalized_speaker)
    if not isinstance(entry, dict):
        return None
    return entry


def _build_character_lookup(rows: list[Character]) -> dict[str, dict[str, object] | object]:
    lookup: dict[str, dict[str, object] | object] = {}

    def add_lookup_key(normalized_key: str, entry: dict[str, object]) -> None:
        if not normalized_key:
            return
        existing = lookup.get(normalized_key)
        if existing is None:
            lookup[normalized_key] = entry
            return
        if existing is entry:
            return
        if isinstance(existing, dict) and existing.get("id") == entry.get("id"):
            return
        lookup[normalized_key] = _AMBIGUOUS_CHARACTER_REFERENCE

    def _character_voice_id(character_row: Character) -> str | None:
        assigned_voice = getattr(character_row, "voice_map", None)
        if assigned_voice is not None and assigned_voice.voice_id:
            return str(assigned_voice.voice_id)
        if character_row.voice_id:
            return str(character_row.voice_id)
        return None

    for character in rows:
        voice_id = _character_voice_id(character)
        speaker_entry: dict[str, object] = {
            "id": character.id,
            "gender": character.gender,
            "voice_id": voice_id,
            "confidence": character.confidence,
        }
        add_lookup_key(normalize_candidate_key(character.name), speaker_entry)
        for alias in character.aliases or []:
            add_lookup_key(normalize_candidate_key(alias), speaker_entry)

    return lookup


def _resolve_speaker_entry(
    speaker: str,
    character_lookup: dict[str, dict[str, object] | object],
) -> dict[str, object] | None:
    if not speaker:
        return None
    if normalize_candidate_key(speaker) == "unknown":
        return None
    return _character_lookup_entry_for_speaker(speaker=speaker, character_lookup=character_lookup)


def _should_escalate_to_llm(
    tags: dict[str, object], *, confidence_threshold: float = _LLM_CONFIDENCE_THRESHOLD_DEFAULT, deep_semantic_refinement: bool = False
) -> bool:
    if bool(deep_semantic_refinement):
        return True

    threshold = _coerce_confidence_threshold(confidence_threshold)
    ambiguity_flags = tags.get("ambiguity_flags")
    if isinstance(ambiguity_flags, str):
        if ambiguity_flags.strip():
            return True
    elif isinstance(ambiguity_flags, (list, tuple, set)):
        for flag in ambiguity_flags:
            if str(flag).strip():
                return True
    elif isinstance(ambiguity_flags, dict):
        if any(bool(value) for value in ambiguity_flags.values()):
            return True

    check_states = {
        str(tags.get("type_state", "unknown")).lower(),
        str(tags.get("speaker_state", "unknown")).lower(),
        str(tags.get("emotion_state", "unknown")).lower(),
        str(tags.get("summary_tag", {}).get("state", "unknown")).lower()
        if isinstance(tags.get("summary_tag"), dict)
        else "unknown",
        str(tags.get("tension_contribution", {}).get("state", "unknown")).lower()
        if isinstance(tags.get("tension_contribution"), dict)
        else "unknown",
        str(tags.get("dominance_contribution", {}).get("state", "unknown")).lower()
        if isinstance(tags.get("dominance_contribution"), dict)
        else "unknown",
    }
    if any(state in {"uncertain", "unknown"} for state in check_states):
        return True

    confidence_fields = [
        ("type_confidence", tags.get("type_confidence")),
        ("speaker_confidence", tags.get("speaker_confidence")),
        ("emotion_confidence", tags.get("emotion_confidence")),
        ("summary_confidence", tags.get("summary_tag", {}).get("confidence") if isinstance(tags.get("summary_tag"), dict) else None),
        ("tension_confidence", tags.get("tension_contribution", {}).get("confidence") if isinstance(tags.get("tension_contribution"), dict) else None),
        ("dominance_confidence", tags.get("dominance_contribution", {}).get("confidence") if isinstance(tags.get("dominance_contribution"), dict) else None),
    ]
    for _, value in confidence_fields:
        if _coerce_confidence(value) < threshold:
            return True
    return False


def execute_pipeline(session: Session, project: Project, run: Run, run_config: dict) -> dict:
    chapters = (
        session.query(Chapter)
        .filter(Chapter.project_id == project.id)
        .order_by(Chapter.chapter_index.asc())
        .all()
    )

    if not chapters:
        raise PipelineError("No chapters available. Upload and ingest a TXT file first.")

    characters = (
        session.query(Character)
        .filter(Character.project_id == project.id)
        .order_by(Character.name.asc(), Character.id.asc())
        .all()
    )

    global_pronunciations = {
        entry.term.strip(): entry.verbalized_form.strip()
        for entry in session.query(PronunciationDictionary)
        .filter(
            PronunciationDictionary.project_id == project.id,
            PronunciationDictionary.scope == "global",
            PronunciationDictionary.character_name == "",
        )
        .order_by(PronunciationDictionary.term.asc(), PronunciationDictionary.id.asc())
        .all()
    }
    place_pronunciations = {
        entry.term.strip(): entry.verbalized_form.strip()
        for entry in session.query(PronunciationDictionary)
        .filter(
            PronunciationDictionary.project_id == project.id,
            PronunciationDictionary.scope == "place",
            PronunciationDictionary.character_name == "",
        )
        .order_by(PronunciationDictionary.term.asc(), PronunciationDictionary.id.asc())
        .all()
    }
    invented_pronunciations = {
        entry.term.strip(): entry.verbalized_form.strip()
        for entry in session.query(PronunciationDictionary)
        .filter(
            PronunciationDictionary.project_id == project.id,
            PronunciationDictionary.scope == "invented",
            PronunciationDictionary.character_name == "",
        )
        .order_by(PronunciationDictionary.term.asc(), PronunciationDictionary.id.asc())
        .all()
    }
    artifact_pronunciations = {
        entry.term.strip(): entry.verbalized_form.strip()
        for entry in session.query(PronunciationDictionary)
        .filter(
            PronunciationDictionary.project_id == project.id,
            PronunciationDictionary.scope == "artifact",
            PronunciationDictionary.character_name == "",
        )
        .order_by(PronunciationDictionary.term.asc(), PronunciationDictionary.id.asc())
        .all()
    }
    character_scope_entries = (
        session.query(PronunciationDictionary)
        .filter(
            PronunciationDictionary.project_id == project.id,
            PronunciationDictionary.scope == "character",
        )
        .order_by(
            PronunciationDictionary.character_name.asc(),
            PronunciationDictionary.term.asc(),
            PronunciationDictionary.id.asc(),
        )
        .all()
    )
    character_pronunciations = {}
    for entry in character_scope_entries:
        normalized_name = entry.character_name.strip().lower()
        if not normalized_name:
            continue
        character_map = character_pronunciations.setdefault(normalized_name, {})
        character_map[entry.term.strip()] = entry.verbalized_form.strip()

    name_to_verbalized = {
        **global_pronunciations,
        **place_pronunciations,
        **artifact_pronunciations,
        **invented_pronunciations,
    }
    for character in characters:
        name_to_verbalized[character.name.strip()] = character.verbalized_form.strip()
    character_lookup = _build_character_lookup(rows=characters)
    voice_config = build_effective_voice_config(
        project.voice_config_json,
        default_narrator_voice=project.default_narrator_voice,
        default_male_voice=project.default_male_voice,
        default_female_voice=project.default_female_voice,
        default_neutral_voice=project.default_neutral_voice,
        default_unknown_voice=project.default_unknown_voice,
    )
    voice_config["internal_thought_voice_policy"] = _normalize_internal_thought_voice_policy(
        run_config.get("internal_thought_voice_policy")
    )
    if run_config.get("internal_thought_voice"):
        voice_config["thought_voice"] = str(run_config["internal_thought_voice"]).strip()

    session.query(Segment).filter(Segment.run_id == run.id).delete()
    session.query(LLMCall).filter(LLMCall.run_id == run.id).delete()
    session.query(SubSegmentTag).filter(SubSegmentTag.run_id == run.id).delete()

    max_chars = int(run_config.get("max_segment_chars", 255))
    llm_probe_text: str | None = None
    total_segments = 0
    segment_payloads: list[dict[str, object]] = []

    for chapter in chapters:
        pieces = segment_text_with_parent_paragraph(chapter.normalized_text, max_chars=max_chars)
        chapter_search_cursor = 0
        for segment_index, piece in enumerate(pieces, start=1):
            original_text = str(piece.get("text", ""))
            parent_paragraph_index = int(piece.get("paragraph_index", 1))
            parent_sentence_start_index = int(piece.get("sentence_start_index", 1))
            parent_sentence_end_index = int(piece.get("sentence_end_index", parent_sentence_start_index))
            if parent_sentence_end_index < parent_sentence_start_index:
                parent_sentence_end_index = parent_sentence_start_index
            tags = tag_segment(original_text)
            speaker = str(tags["speaker"])
            speaker_entry = _resolve_speaker_entry(speaker=speaker, character_lookup=character_lookup)
            normalized_speaker = speaker.strip().lower()
            pronunciation_map = {**name_to_verbalized}
            if normalized_speaker and normalized_speaker != "unknown":
                pronunciation_map.update(character_pronunciations.get(normalized_speaker, {}))
            phonetic_text = replace_pronunciations(original_text, pronunciation_map)
            segment_start = chapter.normalized_text.find(original_text, chapter_search_cursor)
            if segment_start < 0:
                segment_start = max(chapter_search_cursor, 0)
                segment_offset_map: list[dict[str, int]] = []
            else:
                segment_offset_map = build_segment_level_offset_map(
                    chapter.original_to_normalized_offset_map,
                    segment_start,
                    original_text,
                )
            segment_offset_candidates = [
                (entry["original_start"], entry["original_end"])
                for entry in segment_offset_map
                if entry.get("original_start") != -1 and entry.get("original_end") != -1
            ]
            if segment_offset_candidates:
                original_span_start = min(start for start, _ in segment_offset_candidates)
                original_span_end = max(end for _, end in segment_offset_candidates)
            else:
                original_span_start = -1
                original_span_end = -1
            chapter_search_cursor = segment_start + len(original_text)

            speaker = str(tags["speaker"])
            resolved_voice_id, resolved_gender = resolve_voice(
                segment_type=str(tags["type"]),
                speaker=speaker,
                character_lookup=character_lookup,
                voice_config=voice_config,
            )

            canonical_entry = speaker_entry
            gender = resolved_gender
            if canonical_entry is not None:
                gender = str(canonical_entry.get("gender", resolved_gender))

            speaker_id: int | None = None
            if canonical_entry is not None:
                speaker_id = int(canonical_entry["id"]) if canonical_entry.get("id") is not None else None

            segment_payload = {
                "chapter_id": chapter.chapter_index,
                "chapter_internal_id": chapter.chapter_internal_id,
                "segment_id": f"{chapter.chapter_index}-{segment_index:03d}",
                "segment_index": segment_index,
                "original_text": original_text,
                "normalized_text": original_text,
                "phonetic_text": phonetic_text,
                "parent_paragraph_reference": {
                    "paragraph_index": parent_paragraph_index,
                    "paragraph_id": f"{chapter.chapter_index:03d}-p{parent_paragraph_index:03d}",
                },
                "parent_sentence_reference": {
                    "sentence_start_index": parent_sentence_start_index,
                    "sentence_end_index": parent_sentence_end_index,
                    "sentence_id": (
                        f"{chapter.chapter_index:03d}-p{parent_paragraph_index:03d}"
                        f"-s{parent_sentence_start_index:03d}"
                    ),
                },
                "type": tags["type"],
                "type_evidence": tags.get("type_evidence", {}),
                "speaker": speaker,
                "speaker_evidence": tags.get("speaker_evidence", {}),
                "speaker_id": speaker_id,
                "gender": gender,
                "type_confidence": tags["type_confidence"],
                "speaker_state": tags.get("speaker_state", "uncertain"),
                "emotion_state": tags.get("emotion_state", "uncertain"),
                "summary_tag": tags.get("summary_tag", {}),
                "ambiguity_flags": tags.get("ambiguity_flags", []),
                "emotion_evidence": tags.get("emotion_evidence", {}),
                "tag_states": {
                    "type": tags.get("type_state", "uncertain"),
                    "speaker": tags.get("speaker_state", "uncertain"),
                    "emotion": tags.get("emotion_state", "uncertain"),
                    "tension": tags.get("tension_contribution", {}).get("state", "uncertain"),
                    "dominance": tags.get("dominance_contribution", {}).get("state", "uncertain"),
                    "summary": tags.get("summary_tag", {}).get("state", "uncertain"),
                },
                "voice_id": resolved_voice_id,
                "resolved_voice_id": resolved_voice_id,
                "emotion_valence": tags["emotion_valence"],
                "emotion_intensity": tags["emotion_intensity"],
                "emotion_primary_label": tags["emotion_primary_label"],
                "emotion_secondary_label": tags["emotion_secondary_label"],
                "emotion_shift": tags["emotion_shift"],
                "narration_internal_thought_shift": tags["narration_internal_thought_shift"],
                "internal_external_speech_shift": tags["internal_external_speech_shift"],
                "tone_reversal": tags["tone_reversal"],
                "sub_segment_boundaries": tags["sub_segment_boundaries"],
                "tension_contribution": tags["tension_contribution"],
                "dominance_contribution": tags["dominance_contribution"],
                "confidence": {
                    "speaker": tags["speaker_confidence"],
                    "emotion": tags["emotion_confidence"],
                    "gender": _resolve_gender_confidence(speaker=speaker, character_lookup=character_lookup),
                    "type": tags["type_confidence"],
                    "tension": tags["tension_contribution"]["confidence"],
                    "dominance": tags["dominance_contribution"]["confidence"],
                },
                "original_span_pointer": {
                    "original_start_char": original_span_start,
                    "original_end_char": original_span_end,
                    "normalized_start_char": segment_start,
                    "normalized_end_char": segment_start + len(original_text),
                },
                "original_to_normalized_offset_map": segment_offset_map,
            }
            segment_payloads.append(segment_payload)
            if llm_probe_text is None and _should_escalate_to_llm(
                segment_payload,
                confidence_threshold=run_config.get("llm_confidence_threshold", _LLM_CONFIDENCE_THRESHOLD_DEFAULT),
                deep_semantic_refinement=run_config.get("deep_semantic_refinement", False),
            ):
                llm_probe_text = original_text

            segment = Segment(
                run_id=run.id,
                chapter_id=chapter.id,
                segment_index=segment_index,
                segment_json=segment_payload,
            )
            session.add(segment)
            session.flush()

            for boundary_index, boundary in enumerate(tags["sub_segment_boundaries"], start=1):
                if not isinstance(boundary, dict):
                    continue
                segment_payload_id = str(segment_payload["segment_id"])
                session.add(
                    SubSegmentTag(
                        run_id=run.id,
                        chapter_id=chapter.id,
                        segment_id=segment.id,
                        sub_segment_id=f"{segment_payload_id}-{boundary_index:02d}",
                        sub_segment_index=boundary_index,
                        shift_type=str(boundary.get("shift_type")),
                        boundary_start_char=int(boundary.get("boundary_start_char", 0)),
                        boundary_end_char=int(boundary.get("boundary_end_char", 0)),
                        from_label=(None if boundary.get("from_label") is None else str(boundary.get("from_label"))),
                        to_label=(None if boundary.get("to_label") is None else str(boundary.get("to_label"))),
                        from_text=(None if boundary.get("from_text") is None else str(boundary.get("from_text"))),
                        to_text=(None if boundary.get("to_text") is None else str(boundary.get("to_text"))),
                        confidence=float(boundary.get("confidence", 0.0)),
                        tags={"shift_type": boundary.get("shift_type"), "payload": dict(boundary)},
                        evidence=boundary.get("evidence", {}),
                    )
                )

            total_segments += 1

    llm_enabled = bool(run_config.get("llm_enabled", False))
    if llm_enabled and llm_probe_text:
        _run_llm_probe(
            session=session,
            project=project,
            run=run,
            run_config=run_config,
            input_text=llm_probe_text,
        )

    character_occurrence_analytics = build_character_occurrence_analytics(
        chapters=chapters,
        characters=characters,
        segment_payloads=segment_payloads,
    )
    run.config_json = {
        **(run.config_json or {}),
        **character_occurrence_analytics,
    }

    run.status = "completed"
    run.finished_at = datetime.now(timezone.utc)
    session.flush()

    export_payload = build_run_export(session, project, run)
    return {
        "segment_count": total_segments,
        "export": export_payload,
    }


def _run_llm_probe(session: Session, project: Project, run: Run, run_config: dict, input_text: str) -> None:
    provider = _normalize_provider_name_for_llm(run_config.get("provider_name", "openrouter"))

    if not is_supported_provider(provider):
        session.add(
            LLMCall(
                run_id=run.id,
                provider=provider,
                task_type=LLMTaskType.SENTIMENT_PROBE.value,
                success=False,
                request_count=0,
                token_usage_estimate=None,
                detail="unsupported_provider",
                is_cache_hit=False,
                model_identifier=None,
                called_at=datetime.now(timezone.utc),
            )
        )
        session.flush()
        return

    if not is_provider_enabled(session=session, provider=provider):
        session.add(
            LLMCall(
                run_id=run.id,
                provider=provider,
                task_type=LLMTaskType.SENTIMENT_PROBE.value,
                success=False,
                request_count=0,
                token_usage_estimate=None,
                detail="provider_disabled",
                is_cache_hit=False,
                model_identifier=None,
                called_at=datetime.now(timezone.utc),
            )
        )
        session.flush()
        return

    max_calls_per_day = int(run_config.get("max_calls_per_day", 25))
    settings = get_settings()
    provider_candidates = _build_probe_provider_order(requested_provider=provider, settings=settings)
    configuration_snapshot_id = str(project.configuration_snapshot_id or f"run-{run.id}")

    request = LLMRequest(
        request_id=str(uuid4()),
        project_id=project.id,
        task_type=LLMTaskType.SENTIMENT_PROBE.value,
        input_text=input_text,
        expected_schema={"sentiment": "string", "confidence": "number"},
        configuration_snapshot_id=configuration_snapshot_id,
    )

    final_provider = provider
    final_request_count = 0
    final_token_usage = None
    final_detail = None
    final_model_identifier = None
    final_called_at = None
    success = False

    for active_provider in provider_candidates:
        if not is_supported_provider(active_provider):
            continue

        if not is_provider_enabled(session=session, provider=active_provider):
            if active_provider == provider:
                final_detail = "provider_disabled"
                final_provider = active_provider
                break
            continue

        runtime_base_url, runtime_model_identifier, runtime_api_key = get_provider_runtime_settings(
            settings=settings,
            provider_name=active_provider,
        )
        cached_response = _get_cached_llm_response(
            session=session,
            input_text=input_text,
            task_type=LLMTaskType.SENTIMENT_PROBE.value,
            configuration_snapshot_id=configuration_snapshot_id,
            model_identifier=runtime_model_identifier,
        )
        if cached_response is not None:
            cached_payload = cached_response.response_payload
            final_provider = active_provider
            final_success = bool(cached_payload.get("success", False))
            final_token_usage = cached_payload.get("token_usage_estimate")
            final_detail = cached_payload.get("detail")
            final_model_identifier = str(runtime_model_identifier)
            final_called_at = _coerce_call_timestamp(cached_payload.get("called_at"))
            success = final_success
            final_request_count = 0
            session.add(
                LLMCall(
                    run_id=run.id,
                    provider=final_provider,
                    task_type=LLMTaskType.SENTIMENT_PROBE.value,
                    success=final_success,
                    request_count=final_request_count,
                    token_usage_estimate=final_token_usage,
                    detail=(None if final_success else str(final_detail) if final_detail is not None else "cache_hit"),
                    is_cache_hit=True,
                    model_identifier=final_model_identifier,
                    called_at=final_called_at,
                )
            )
            session.flush()
            return

        runtime_api_keys = get_provider_api_keys(
            settings=settings,
            provider_name=active_provider,
        )
        if not runtime_api_keys and runtime_api_key:
            runtime_api_keys = [runtime_api_key]

        if not runtime_api_keys:
            runtime_api_keys = [None]

        router = LLMRouter(openrouter_base_url=runtime_base_url)
        provider_failure_detail: str | None = None

        for index, api_key in enumerate(runtime_api_keys):
            if api_key is not None:
                key_allowed, _ = consume_api_key_quota(
                    session=session,
                    provider=active_provider,
                    provider_api_key=api_key,
                    max_calls_per_day=max_calls_per_day,
                )
                if not key_allowed:
                    provider_failure_detail = "quota_reached"
                    continue
            else:
                pass

            allowed, request_count = consume_quota(
                session=session,
                provider=active_provider,
                max_calls_per_day=max_calls_per_day,
            )
            if not allowed:
                provider_failure_detail = "quota_reached"
                final_request_count = request_count
                break

            final_request_count = request_count
            response = router.call(
                request=request,
                provider_name=active_provider,
                model_identifier=runtime_model_identifier,
                api_key=api_key,
            )

            if response.success_flag:
                mark_provider_available(session=session, provider=active_provider)
                mark_provider_successful_call(session=session, provider=active_provider)
                if api_key is not None:
                    mark_api_key_successful_call(
                        session=session,
                        provider=active_provider,
                        provider_api_key=api_key,
                    )
                final_provider = active_provider
                final_token_usage = response.token_usage_estimate
                final_detail = response.raw_output
                final_model_identifier = response.model_identifier
                final_called_at = _coerce_call_timestamp(response.timestamp)
                payload = {
                    "success": response.success_flag,
                    "detail": response.raw_output,
                    "token_usage_estimate": response.token_usage_estimate,
                    "called_at": _coerce_call_timestamp(response.timestamp).isoformat(),
                }
                session.add(
                    LLMCache(
                        input_text_hash=_build_llm_cache_key(input_text),
                        task_type=LLMTaskType.SENTIMENT_PROBE.value,
                        configuration_snapshot_id=configuration_snapshot_id,
                        model_identifier=(str(response.model_identifier) if response.model_identifier else runtime_model_identifier),
                        response_payload=payload,
                    )
                )
                success = True
                break

            provider_failure_detail = response.error_code or "provider_error"
            final_detail = provider_failure_detail
            final_token_usage = response.token_usage_estimate
            final_model_identifier = response.model_identifier
            final_called_at = _coerce_call_timestamp(response.timestamp)

            if response.error_code in {"rate_limit", "quota"}:
                if api_key is not None:
                    mark_api_key_rate_limited(session=session, provider=active_provider, provider_api_key=api_key)
                    if response.error_code == "rate_limit":
                        mark_api_key_reset_at(
                            session=session,
                            provider=active_provider,
                            provider_api_key=api_key,
                            reset_at=response.rate_limit_reset_at,
                        )
                is_last_key = index + 1 >= len(runtime_api_keys)
                if not is_last_key:
                    continue

                mark_provider_rate_limited(session=session, provider=active_provider)
                if response.error_code == "rate_limit":
                    mark_provider_reset_at(
                        session=session,
                        provider=active_provider,
                        reset_at=response.rate_limit_reset_at,
                    )

            else:
                break
        if success:
            break

        if final_detail is None:
            final_detail = provider_failure_detail

        final_provider = active_provider
        if provider_failure_detail in {"rate_limit", "quota", "quota_reached"}:
            if active_provider != provider_candidates[-1]:
                continue
            break

        if provider_failure_detail is not None:
            break

    session.add(
        LLMCall(
            run_id=run.id,
            provider=final_provider,
            task_type=LLMTaskType.SENTIMENT_PROBE.value,
            success=success,
            request_count=final_request_count,
            token_usage_estimate=final_token_usage,
            detail=(None if success else final_detail),
            is_cache_hit=False,
            model_identifier=final_model_identifier,
            called_at=(
                _coerce_call_timestamp(None)
                if final_called_at is None
                else final_called_at
            ),
        )
    )
    session.flush()
