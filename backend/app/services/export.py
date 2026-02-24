from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Chapter, Project, Run, Segment


def build_run_export(session: Session, project: Project, run: Run) -> dict:
    rows = session.execute(
        select(Segment.segment_json)
        .join(Chapter, Chapter.id == Segment.chapter_id)
        .where(Segment.run_id == run.id)
        .order_by(Chapter.chapter_index.asc(), Segment.segment_index.asc())
    ).scalars()

    segments = list(rows)

    return {
        "project_id": project.id,
        "project_title": project.title,
        "run_id": run.id,
        "status": run.status,
        "segments": segments,
    }
