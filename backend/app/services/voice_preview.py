from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Character, Project, Run, Segment
from app.services.voice import build_effective_voice_config, resolve_voice


def _build_character_lookup(characters: list[Character]) -> dict[str, dict[str, str | None]]:
    def _character_voice_id(character_row: Character) -> str | None:
        assigned_voice = getattr(character_row, "voice_map", None)
        if assigned_voice is not None and assigned_voice.voice_id:
            return str(assigned_voice.voice_id)
        if character_row.voice_id:
            return str(character_row.voice_id)
        return None

    return {
        character.name.lower(): {
            "gender": character.gender,
            "voice_id": _character_voice_id(character),
        }
        for character in characters
    }


def _build_voice_preview_payload(
    segments: list[Segment],
    character_lookup: dict[str, dict[str, str | None]],
    voice_config: dict[str, str],
    max_segments: int | None = None,
) -> list[dict[str, object]]:
    payload: list[dict[str, object]] = []
    for segment in segments:
        segment_json = segment.segment_json or {}
        if not isinstance(segment_json, dict):
            continue

        speaker = str(segment_json.get("speaker", "unknown")).strip() or "unknown"
        segment_type = str(segment_json.get("type", "narration"))

        voice_id, resolved_gender = resolve_voice(
            segment_type=segment_type,
            speaker=speaker,
            character_lookup=character_lookup,
            voice_config=voice_config,
        )

        entry = character_lookup.get(speaker.lower())
        if entry is not None:
            gender = str(entry.get("gender", resolved_gender))
        else:
            gender = resolved_gender

        payload.append(
            {
                "segment_id": segment_json.get("segment_id") or f"{segment.chapter_id}-{segment.segment_index}",
                "segment_index": segment.segment_index,
                "speaker": speaker,
                "segment_type": segment_type,
                "voice_id": voice_id,
                "gender": gender,
            }
        )

        if max_segments is not None and len(payload) >= max_segments:
            break

    return payload


def recompute_voice_previews_for_runs(
    session: Session,
    project: Project,
    runs: list[Run],
    *,
    max_segments: int | None = None,
) -> int:
    if not runs:
        return 0

    session.flush()

    character_lookup = _build_character_lookup(
        list(session.query(Character).filter(Character.project_id == project.id).all())
    )
    voice_config = build_effective_voice_config(
        project.voice_config_json,
        default_narrator_voice=project.default_narrator_voice,
    )
    recomputed_at = datetime.now(timezone.utc).isoformat()

    runs_recomputed = 0
    for run in runs:
        segment_rows = (
            session.query(Segment)
            .filter(Segment.run_id == run.id)
            .order_by(Segment.id.asc())
            .all()
        )
        run.config_json = {
            **(run.config_json or {}),
            "voice_preview": {
                "segments": _build_voice_preview_payload(
                    segments=segment_rows,
                    character_lookup=character_lookup,
                    voice_config=voice_config,
                    max_segments=max_segments,
                ),
                "recomputed_at": recomputed_at,
                "recompute_reason": "character_gender_edited",
                "project_id": project.id,
                "run_id": run.id,
            },
            "voice_preview_recompute_timestamp": recomputed_at,
        }
        runs_recomputed += 1

    return runs_recomputed
