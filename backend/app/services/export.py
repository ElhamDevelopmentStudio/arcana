from sqlalchemy import select
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.models import Chapter, Project, Run, Segment


def build_run_export(session: Session, project: Project, run: Run) -> dict:
    generated_at = run.finished_at or run.started_at or datetime.now(timezone.utc)
    rows = session.execute(
        select(Segment.segment_json)
        .join(Chapter, Chapter.id == Segment.chapter_id)
        .where(Segment.run_id == run.id)
        .order_by(Chapter.chapter_index.asc(), Segment.segment_index.asc())
    ).scalars()

    segments = list(rows)
    manifest = {
        "schema_version": "1.0.0",
        "export_type": "audiobook_tts_package",
        "export_format": "json",
        "generated_at": generated_at.isoformat(),
        "project": {
            "id": project.id,
            "title": project.title,
        },
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
