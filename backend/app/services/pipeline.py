from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Chapter, Character, LLMCall, Project, PronunciationDictionary, Run, Segment
from app.services.export import build_run_export
from app.services.llm_router import LLMRequest, LLMRouter
from app.services.character_analytics import (
    build_character_occurrence_analytics,
)
from app.services.phonetics import replace_pronunciations
from app.services.quota import consume_quota
from app.services.segmentation import segment_text_with_parent_paragraph
from app.services.tagging import tag_segment
from app.services.normalization import build_segment_level_offset_map
from app.services.voice import resolve_voice

_LOW_GENDER_CONFIDENCE = 0.0
_LOW_CONFIDENCE_GENDERS = frozenset({"neutral", "unknown"})


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


def _resolve_gender_confidence(
    speaker: str,
    character_lookup: dict[str, dict[str, object]],
) -> float:
    if not speaker or speaker.lower() == "unknown":
        return _LOW_GENDER_CONFIDENCE

    entry = character_lookup.get(speaker.lower())
    if entry is None:
        return _LOW_GENDER_CONFIDENCE

    gender = str(entry.get("gender", "unknown")).strip().lower() or "unknown"
    if gender in _LOW_CONFIDENCE_GENDERS:
        return _LOW_GENDER_CONFIDENCE

    return _coerce_confidence(entry.get("confidence"))


def execute_pipeline(session: Session, project: Project, run: Run, run_config: dict) -> dict:
    chapters = (
        session.query(Chapter)
        .filter(Chapter.project_id == project.id)
        .order_by(Chapter.chapter_index.asc())
        .all()
    )

    if not chapters:
        raise PipelineError("No chapters available. Upload and ingest a TXT file first.")

    characters = session.query(Character).filter(Character.project_id == project.id).all()

    global_pronunciations = {
        entry.term.strip(): entry.verbalized_form.strip()
        for entry in session.query(PronunciationDictionary)
        .filter(
            PronunciationDictionary.project_id == project.id,
            PronunciationDictionary.scope == "global",
            PronunciationDictionary.character_name == "",
        )
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
        .all()
    }
    character_scope_entries = session.query(PronunciationDictionary).filter(
        PronunciationDictionary.project_id == project.id,
        PronunciationDictionary.scope == "character",
    ).all()
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
    character_lookup = {
        character.name.lower(): {
            "gender": character.gender,
            "voice_id": character.voice_id,
            "confidence": character.confidence,
        }
        for character in characters
    }

    session.query(Segment).filter(Segment.run_id == run.id).delete()
    session.query(LLMCall).filter(LLMCall.run_id == run.id).delete()

    max_chars = int(run_config.get("max_segment_chars", 255))
    first_segment_text: str | None = None
    total_segments = 0
    segment_payloads: list[dict[str, object]] = []

    for chapter in chapters:
        pieces = segment_text_with_parent_paragraph(chapter.normalized_text, max_chars=max_chars)
        chapter_search_cursor = 0
        for segment_index, piece in enumerate(pieces, start=1):
            original_text = str(piece.get("text", ""))
            parent_paragraph_index = int(piece.get("paragraph_index", 1))
            tags = tag_segment(original_text)
            speaker = str(tags["speaker"])
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
            voice_id, resolved_gender = resolve_voice(
                segment_type=str(tags["type"]),
                speaker=speaker,
                character_lookup=character_lookup,
                voice_config=project.voice_config_json,
            )

            canonical_entry = character_lookup.get(speaker.lower()) if speaker.lower() != "unknown" else None
            gender = resolved_gender
            if canonical_entry is not None:
                gender = str(canonical_entry.get("gender", resolved_gender))

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
                "type": tags["type"],
                "speaker": speaker,
                "gender": gender,
                "voice_id": voice_id,
                "emotion_valence": tags["emotion_valence"],
                "emotion_intensity": tags["emotion_intensity"],
                "confidence": {
                    "speaker": tags["speaker_confidence"],
                    "emotion": tags["emotion_confidence"],
                    "gender": _resolve_gender_confidence(speaker=speaker, character_lookup=character_lookup),
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

            session.add(
                Segment(
                    run_id=run.id,
                    chapter_id=chapter.id,
                    segment_index=segment_index,
                    segment_json=segment_payload,
                )
            )

            if first_segment_text is None:
                first_segment_text = original_text

            total_segments += 1

    llm_enabled = bool(run_config.get("llm_enabled", False))
    if llm_enabled and first_segment_text:
        _run_llm_probe(session=session, project=project, run=run, run_config=run_config, input_text=first_segment_text)

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
    provider = str(run_config.get("provider_name", "openrouter")).lower()
    max_calls_per_day = int(run_config.get("max_calls_per_day", 25))

    allowed, request_count = consume_quota(
        session=session,
        provider=provider,
        max_calls_per_day=max_calls_per_day,
    )

    if not allowed:
        session.add(
            LLMCall(
                run_id=run.id,
                provider=provider,
                task_type="sentiment_probe",
                success=False,
                request_count=request_count,
                detail="quota_reached",
            )
        )
        session.flush()
        return

    settings = get_settings()
    router = LLMRouter(openrouter_base_url=settings.openrouter_base_url)
    request = LLMRequest(
        request_id=str(uuid4()),
        project_id=project.id,
        task_type="sentiment_probe",
        input_text=input_text,
        expected_schema={"sentiment": "string", "confidence": "number"},
        configuration_snapshot_id=f"run-{run.id}",
    )

    response = router.call(
        request=request,
        provider_name=provider,
        model_identifier=settings.openrouter_model,
        api_key=settings.openrouter_api_key,
    )

    detail = response.raw_output if response.success_flag else response.error_code

    session.add(
        LLMCall(
            run_id=run.id,
            provider=provider,
            task_type="sentiment_probe",
            success=response.success_flag,
            request_count=request_count,
            detail=detail,
        )
    )
    session.flush()
