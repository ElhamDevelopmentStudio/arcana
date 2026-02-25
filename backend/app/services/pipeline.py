from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Chapter, Character, LLMCall, Project, Run, Segment
from app.services.export import build_run_export
from app.services.llm_router import LLMRequest, LLMRouter
from app.services.character_analytics import build_character_mentions_by_chapter
from app.services.phonetics import replace_pronunciations
from app.services.quota import consume_quota
from app.services.segmentation import segment_text
from app.services.tagging import tag_segment
from app.services.normalization import build_segment_level_offset_map
from app.services.voice import resolve_voice


class PipelineError(RuntimeError):
    pass


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
    name_to_verbalized = {character.name: character.verbalized_form for character in characters}
    character_lookup = {
        character.name.lower(): {"gender": character.gender, "voice_id": character.voice_id}
        for character in characters
    }

    session.query(Segment).filter(Segment.run_id == run.id).delete()
    session.query(LLMCall).filter(LLMCall.run_id == run.id).delete()

    max_chars = int(run_config.get("max_segment_chars", 255))
    first_segment_text: str | None = None
    total_segments = 0

    for chapter in chapters:
        pieces = segment_text(chapter.normalized_text, max_chars=max_chars)
        chapter_search_cursor = 0
        for segment_index, original_text in enumerate(pieces, start=1):
            phonetic_text = replace_pronunciations(original_text, name_to_verbalized)
            tags = tag_segment(original_text)
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
                "segment_id": f"{chapter.chapter_index}-{segment_index:03d}",
                "original_text": original_text,
                "phonetic_text": phonetic_text,
                "type": tags["type"],
                "speaker": speaker,
                "gender": gender,
                "voice_id": voice_id,
                "emotion_valence": tags["emotion_valence"],
                "emotion_intensity": tags["emotion_intensity"],
                "confidence": {
                    "speaker": tags["speaker_confidence"],
                    "emotion": tags["emotion_confidence"],
                },
                "original_to_normalized_offset_map": segment_offset_map,
            }

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

    chapter_mention_counters = build_character_mentions_by_chapter(chapters=chapters, characters=characters)
    run.config_json = {
        **(run.config_json or {}),
        "character_mentions_by_chapter": [counter.to_dict() for counter in chapter_mention_counters],
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
