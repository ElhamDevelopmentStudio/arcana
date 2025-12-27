from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
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


def build_run_export(session: Session, project: Project, run: Run) -> dict:
    generated_at = run.finished_at or run.started_at or datetime.now(timezone.utc)
    rows = session.execute(
        select(Segment.segment_json)
        .join(Chapter, Chapter.id == Segment.chapter_id)
        .where(Segment.run_id == run.id)
        .order_by(Chapter.chapter_index.asc(), Segment.segment_index.asc())
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
    }
