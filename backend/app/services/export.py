from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Chapter, Project, Run, Segment


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


def build_run_export(session: Session, project: Project, run: Run) -> dict:
    generated_at = run.finished_at or run.started_at or datetime.now(timezone.utc)
    rows = session.execute(
        select(Segment.segment_json)
        .join(Chapter, Chapter.id == Segment.chapter_id)
        .where(Segment.run_id == run.id)
        .order_by(Chapter.chapter_index.asc(), Segment.segment_index.asc())
    ).scalars()

    segments = [_normalize_segment_for_export(row) for row in list(rows)]
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
        "ordered_by": ["chapter_index", "segment_index"],
    }

    return {
        "project_id": project.id,
        "project_title": project.title,
        "run_id": run.id,
        "status": run.status,
        "manifest": manifest,
        "segments": segments,
    }
