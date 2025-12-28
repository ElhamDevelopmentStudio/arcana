import csv
import io
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models import Chapter, LLMCall, Project, Run, Segment


def _to_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _build_tag_bundle(segment_json: Mapping[str, Any]) -> dict[str, Any]:
    confidence = _to_dict(segment_json.get("confidence"))
    return {
        "type": segment_json.get("type"),
        "speaker": segment_json.get("speaker"),
        "speaker_id": segment_json.get("speaker_id"),
        "gender": segment_json.get("gender"),
        "emotion": {
            "valence": segment_json.get("emotion_valence"),
            "intensity": segment_json.get("emotion_intensity"),
            "primary_label": segment_json.get("emotion_primary_label"),
            "secondary_label": segment_json.get("emotion_secondary_label"),
            "state": segment_json.get("emotion_state"),
            "evidence": _to_dict(segment_json.get("emotion_evidence")),
            "confidence": confidence.get("emotion"),
        },
        "type_confidence": confidence.get("type"),
        "speaker_confidence": confidence.get("speaker"),
        "tension": {
            **_to_dict(segment_json.get("tension_contribution")),
            "confidence": confidence.get("tension"),
        },
        "dominance": {
            **_to_dict(segment_json.get("dominance_contribution")),
            "confidence": confidence.get("dominance"),
        },
        "summary_tag": _to_dict(segment_json.get("summary_tag")),
        "type_evidence": _to_dict(segment_json.get("type_evidence")),
        "speaker_evidence": _to_dict(segment_json.get("speaker_evidence")),
        "sub_segment_boundaries": segment_json.get("sub_segment_boundaries", []),
        "confidence": confidence,
    }


def _normalize_segment_for_export(segment_json: Any) -> dict[str, Any]:
    if not isinstance(segment_json, Mapping):
        return {}
    segment_payload = dict(segment_json)
    segment_payload["tag_bundle"] = _build_tag_bundle(segment_payload)
    return segment_payload


def _build_project_config_snapshot(project: Project) -> dict[str, Any]:
    return {
        "configuration_snapshot_id": project.configuration_snapshot_id,
        "selected_mode": project.selected_mode,
        "selected_modes": list(project.selected_modes or []),
        "voice_config": dict(project.voice_config_json or {}),
        "default_voices": {
            "narrator": project.default_narrator_voice,
            "male": project.default_male_voice,
            "female": project.default_female_voice,
            "neutral": project.default_neutral_voice,
            "unknown": project.default_unknown_voice,
        },
    }


def _load_run_llm_calls(session: Session, run: Run) -> list[dict[str, Any]]:
    llm_calls = (
        session.query(LLMCall)
        .filter(LLMCall.run_id == run.id)
        .order_by(LLMCall.created_at.asc(), LLMCall.id.asc())
        .all()
    )
    return [
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


def _build_export_reports(project: Project, run: Run, segment_count: int, ordered_by: list[str]) -> dict[str, Any]:
    run_snapshot = dict(run.config_json or {})
    project_ingestion_log = dict(project.ingestion_log_json or {})
    return {
        "project": {
            "id": project.id,
            "title": project.title,
            "configuration_snapshot_id": project.configuration_snapshot_id,
            "selected_mode": project.selected_mode,
        },
        "run": {
            "id": run.id,
            "status": run.status,
            "segment_count": segment_count,
            "ordered_by": ordered_by,
        },
        "normalization_report": project_ingestion_log.get("normalization_report", {}),
        "character_analytics_snapshot": {
            key: run_snapshot.get(key)
            for key in (
                "character_mentions_by_chapter",
                "character_first_appearance_chapter_index",
                "character_last_appearance_chapter_index",
                "character_mentions_per_1000_words",
                "character_dialogue_line_counts",
            )
            if run_snapshot.get(key) is not None
        },
        "mode_profile_snapshot": _to_dict(run_snapshot.get("voice_config")),
        "generated_at": run.finished_at.isoformat() if run.finished_at else run.started_at.isoformat(),
    }


def _build_segment_rows_query(run_id: int, from_chapter_index: int | None, from_segment_index: int | None):
    base_query = (
        select(Segment.segment_json)
        .join(Chapter, Chapter.id == Segment.chapter_id)
        .where(Segment.run_id == run_id)
        .order_by(Chapter.chapter_index.asc(), Segment.segment_index.asc())
    )
    if from_chapter_index is None and from_segment_index is None:
        return base_query

    if from_chapter_index is None or from_segment_index is None:
        raise ValueError("from_chapter_index and from_segment_index must be provided together")

    return base_query.where(
        or_(
            Chapter.chapter_index > from_chapter_index,
            and_(
                Chapter.chapter_index == from_chapter_index,
                Segment.segment_index > from_segment_index,
            ),
        )
    )


def _to_number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _build_time_series(segments: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    emotion_valence = []
    emotion_intensity = []
    tension = []
    dominance = []
    emotion_delta = []
    previous_segment = None
    previous_values = {"valence": None, "intensity": None, "tension": None, "dominance": None}

    for position, segment in enumerate(segments, start=1):
        chapter_id = segment.get("chapter_id")
        segment_id = segment.get("segment_id")
        segment_index = segment.get("segment_index")
        timestamped_point = {
            "position": position,
            "chapter_id": chapter_id,
            "segment_index": segment_index,
            "segment_id": segment_id,
        }

        valence = _to_number(segment.get("emotion_valence"))
        intensity = _to_number(segment.get("emotion_intensity"))
        tension_value = _to_number(_to_dict(segment.get("tension_contribution")).get("value"))
        dominance_value = _to_number(_to_dict(segment.get("dominance_contribution")).get("value"))

        if previous_segment is not None:
            emotion_delta.append(
                {
                    "position": position,
                    "segment_id": segment_id,
                    "from_segment_id": previous_segment.get("segment_id"),
                    "valence_delta": (valence or 0.0) - (previous_values["valence"] or 0.0),
                    "intensity_delta": (intensity or 0.0) - (previous_values["intensity"] or 0.0),
                    "tension_delta": (tension_value or 0.0) - (previous_values["tension"] or 0.0),
                    "dominance_delta": (dominance_value or 0.0) - (previous_values["dominance"] or 0.0),
                }
            )

        emotion_valence.append({**timestamped_point, "value": valence if valence is not None else 0.0})
        emotion_intensity.append({**timestamped_point, "value": intensity if intensity is not None else 0.0})
        tension.append({**timestamped_point, "value": tension_value if tension_value is not None else 0.0})
        dominance.append({**timestamped_point, "value": dominance_value if dominance_value is not None else 0.0})
        previous_segment = segment
        previous_values["valence"] = valence if valence is not None else 0.0
        previous_values["intensity"] = intensity if intensity is not None else 0.0
        previous_values["tension"] = tension_value if tension_value is not None else 0.0
        previous_values["dominance"] = dominance_value if dominance_value is not None else 0.0

    return {
        "emotion_valence": emotion_valence,
        "emotion_intensity": emotion_intensity,
        "tension": tension,
        "dominance": dominance,
        "emotion_delta": emotion_delta,
    }


def _csv_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _build_segment_csv_row(
    segment: Mapping[str, Any],
    project_id: int,
    run_id: int,
) -> dict[str, str]:
    parent_paragraph = _to_dict(segment.get("parent_paragraph_reference"))
    parent_sentence = _to_dict(segment.get("parent_sentence_reference"))
    original_span_pointer = _to_dict(segment.get("original_span_pointer"))
    tag_bundle = _to_dict(segment.get("tag_bundle"))
    confidence = _to_dict(tag_bundle.get("confidence"))
    emotion = _to_dict(tag_bundle.get("emotion"))
    tension = _to_dict(tag_bundle.get("tension"))
    dominance = _to_dict(tag_bundle.get("dominance"))

    sub_segment_boundaries = segment.get("sub_segment_boundaries", [])
    sub_segment_count = len(sub_segment_boundaries) if isinstance(sub_segment_boundaries, list) else 0

    return {
        "project_id": str(project_id),
        "run_id": str(run_id),
        "segment_id": _csv_cell(segment.get("segment_id")),
        "chapter_id": _csv_cell(segment.get("chapter_id")),
        "chapter_internal_id": _csv_cell(segment.get("chapter_internal_id")),
        "segment_index": _csv_cell(segment.get("segment_index")),
        "type": _csv_cell(segment.get("type")),
        "speaker": _csv_cell(segment.get("speaker")),
        "speaker_id": _csv_cell(segment.get("speaker_id")),
        "gender": _csv_cell(segment.get("gender")),
        "resolved_voice_id": _csv_cell(segment.get("resolved_voice_id")),
        "voice_id": _csv_cell(segment.get("voice_id")),
        "original_text": _csv_cell(segment.get("original_text")),
        "normalized_text": _csv_cell(segment.get("normalized_text")),
        "phonetic_text": _csv_cell(segment.get("phonetic_text")),
        "parent_paragraph_index": _csv_cell(parent_paragraph.get("paragraph_index")),
        "parent_paragraph_id": _csv_cell(parent_paragraph.get("paragraph_id")),
        "parent_sentence_start_index": _csv_cell(parent_sentence.get("sentence_start_index")),
        "parent_sentence_end_index": _csv_cell(parent_sentence.get("sentence_end_index")),
        "type_confidence": _csv_cell(confidence.get("type")),
        "speaker_confidence": _csv_cell(confidence.get("speaker")),
        "emotion_confidence": _csv_cell(confidence.get("emotion")),
        "gender_confidence": _csv_cell(confidence.get("gender")),
        "emotion_valence": _csv_cell(emotion.get("valence")),
        "emotion_intensity": _csv_cell(emotion.get("intensity")),
        "emotion_primary_label": _csv_cell(emotion.get("primary_label")),
        "emotion_secondary_label": _csv_cell(emotion.get("secondary_label")),
        "emotion_state": _csv_cell(emotion.get("state")),
        "emotion_evidence": _csv_cell(emotion.get("evidence")),
        "tension_contribution": _csv_cell(tension),
        "dominance_contribution": _csv_cell(dominance),
        "speaker_evidence": _csv_cell(segment.get("speaker_evidence")),
        "type_evidence": _csv_cell(segment.get("type_evidence")),
        "summary_tag": _csv_cell(segment.get("summary_tag")),
        "original_start_char": _csv_cell(original_span_pointer.get("original_start_char")),
        "original_end_char": _csv_cell(original_span_pointer.get("original_end_char")),
        "normalized_start_char": _csv_cell(original_span_pointer.get("normalized_start_char")),
        "normalized_end_char": _csv_cell(original_span_pointer.get("normalized_end_char")),
        "original_to_normalized_offset_map": _csv_cell(segment.get("original_to_normalized_offset_map")),
        "sub_segment_boundary_count": _csv_cell(sub_segment_count),
        "sub_segment_boundaries": _csv_cell(segment.get("sub_segment_boundaries")),
    }


def build_run_export_csv(
    session: Session,
    project: Project,
    run: Run,
    from_chapter_index: int | None = None,
    from_segment_index: int | None = None,
) -> str:
    rows = session.execute(
        _build_segment_rows_query(run.id, from_chapter_index, from_segment_index)
    ).scalars()

    segments = [_normalize_segment_for_export(row) for row in list(rows)]
    if not segments:
        return ""

    fieldnames = [
        "project_id",
        "run_id",
        "segment_id",
        "chapter_id",
        "chapter_internal_id",
        "segment_index",
        "type",
        "speaker",
        "speaker_id",
        "gender",
        "resolved_voice_id",
        "voice_id",
        "original_text",
        "normalized_text",
        "phonetic_text",
        "parent_paragraph_index",
        "parent_paragraph_id",
        "parent_sentence_start_index",
        "parent_sentence_end_index",
        "type_confidence",
        "speaker_confidence",
        "emotion_confidence",
        "gender_confidence",
        "emotion_valence",
        "emotion_intensity",
        "emotion_primary_label",
        "emotion_secondary_label",
        "emotion_state",
        "emotion_evidence",
        "tension_contribution",
        "dominance_contribution",
        "speaker_evidence",
        "type_evidence",
        "summary_tag",
        "original_start_char",
        "original_end_char",
        "normalized_start_char",
        "normalized_end_char",
        "original_to_normalized_offset_map",
        "sub_segment_boundary_count",
        "sub_segment_boundaries",
    ]

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for segment in segments:
        writer.writerow(_build_segment_csv_row(segment, project_id=project.id, run_id=run.id))
    return output.getvalue()


def build_run_export(
    session: Session,
    project: Project,
    run: Run,
    from_chapter_index: int | None = None,
    from_segment_index: int | None = None,
) -> dict:
    generated_at = run.finished_at or run.started_at or datetime.now(timezone.utc)
    total_segments = session.query(Segment).filter(Segment.run_id == run.id).count()
    rows = session.execute(
        _build_segment_rows_query(run.id, from_chapter_index, from_segment_index)
    ).scalars()

    segments = [_normalize_segment_for_export(row) for row in list(rows)]
    ordered_by = ["chapter_index", "segment_index"]
    llm_calls = _load_run_llm_calls(session, run)
    ingestion_log = dict(project.ingestion_log_json or {})
    manifest = {
        "schema_version": "1.0.0",
        "export_type": "audiobook_tts_package",
        "export_format": "json",
        "generated_at": generated_at.isoformat(),
        "project": {
            "id": project.id,
            "title": project.title,
            "configuration_snapshot_id": project.configuration_snapshot_id,
            "selected_mode": project.selected_mode,
        },
        "project_config_snapshot": _build_project_config_snapshot(project),
        "run": {
            "id": run.id,
            "status": run.status,
            "config_snapshot": run.config_json,
        },
        "segment_count": len(segments),
        "ordered_by": ordered_by,
        "logs": {
            "ingestion_log": ingestion_log,
            "llm_calls": llm_calls,
        },
        "reports": _build_export_reports(
            project=project,
            run=run,
            segment_count=len(segments),
            ordered_by=ordered_by,
        ),
    }

    return {
        "project_id": project.id,
        "project_title": project.title,
        "run_id": run.id,
        "status": run.status,
        "manifest": manifest,
        "segments": segments,
        "time_series": _build_time_series(segments),
        "cursor": {
            "from_chapter_index": from_chapter_index,
            "from_segment_index": from_segment_index,
            "returned_segment_count": len(segments),
            "total_segment_count": total_segments,
            "has_more_segments": len(segments) < total_segments,
            "next_resume_from": None
            if not segments
            else {
                "chapter_index": segments[-1].get("chapter_id"),
                "segment_index": segments[-1].get("segment_index"),
            },
        },
    }
