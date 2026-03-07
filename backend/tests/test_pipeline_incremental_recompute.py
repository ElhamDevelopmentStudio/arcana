import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_pipeline_incremental_recompute.db"
os.environ["LLM_PROVIDER_PRIORITY_ORDER"] = "[\"openrouter\", \"siliconflow\", \"groq\"]"
_ORIGINAL_LLM_PROVIDER_PRIORITY_ORDER = os.environ.get("LLM_PROVIDER_PRIORITY_ORDER")

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import SubSegmentTag


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    if _ORIGINAL_LLM_PROVIDER_PRIORITY_ORDER is None:
        os.environ.pop("LLM_PROVIDER_PRIORITY_ORDER", None)
    else:
        os.environ["LLM_PROVIDER_PRIORITY_ORDER"] = _ORIGINAL_LLM_PROVIDER_PRIORITY_ORDER
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_pipeline_incremental_recompute.db")
    if db_file.exists():
        db_file.unlink()


def _create_project(client: TestClient, title: str) -> int:
    project_resp = client.post("/api/projects", json={"title": title})
    assert project_resp.status_code == 201
    return int(project_resp.json()["id"])


def _ingest_two_chapters(client: TestClient, project_id: int) -> None:
    ingest_resp = client.post(
        f"/api/projects/{project_id}/ingest/txt",
        files={
            "file": (
                "appendable.txt",
                io.BytesIO(
                    (
                        "Chapter 1\n"
                        "A quiet lamp burned on the dock."
                        "\n\nChapter 2\n"
                        "A wind moved softly through paper windows."
                    ).encode("utf-8")
                ),
                "text/plain",
            )
        },
    )
    assert ingest_resp.status_code == 200
    assert ingest_resp.json()["chapter_count"] == 2


def _append_chapter(client: TestClient, project_id: int) -> None:
    append_resp = client.post(
        f"/api/projects/{project_id}/ingest/append-chapter",
        files={
            "file": (
                "chapter-3.txt",
                io.BytesIO(
                    (
                        "Chapter 3\n"
                        "Clouds drifted low over the harbor."
                    ).encode("utf-8")
                ),
                "text/plain",
            )
        },
    )
    assert append_resp.status_code == 200
    assert append_resp.json()["chapter_count"] == 3


def _run_project(client: TestClient, project_id: int, run_payload: dict[str, object] | None = None) -> int:
    run_resp = client.post(f"/api/projects/{project_id}/runs", json=run_payload or {})
    assert run_resp.status_code == 200
    return int(run_resp.json()["run_id"])


def _get_export_segments(client: TestClient, project_id: int, run_id: int) -> list[dict[str, object]]:
    export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
    assert export_resp.status_code == 200
    export_payload = export_resp.json()
    assert export_payload["status"] == "completed"
    return list(export_payload["segments"])


def test_incremental_recompute_reuses_unchanged_prefix_segments() -> None:
    with TestClient(app) as client:
        project_id = _create_project(client, "Incremental Recompute Project")
        _ingest_two_chapters(client=client, project_id=project_id)

        first_run_id = _run_project(
            client=client,
            project_id=project_id,
            run_payload={
                "llm_enabled": False,
                "max_segment_chars": 255,
            },
        )
        first_run_segments = _get_export_segments(client=client, project_id=project_id, run_id=first_run_id)
        assert first_run_segments

        _append_chapter(client=client, project_id=project_id)

        second_run_id = _run_project(
            client=client,
            project_id=project_id,
            run_payload={
                "incremental_recompute": True,
                "llm_enabled": False,
                "max_segment_chars": 255,
            },
        )
        second_run_segments = _get_export_segments(
            client=client,
            project_id=project_id,
            run_id=second_run_id,
        )

        first_prefix = [segment for segment in first_run_segments if int(segment["chapter_id"]) <= 2]
        second_prefix = [segment for segment in second_run_segments if int(segment["chapter_id"]) <= 2]
        assert len(first_prefix) == len(first_run_segments)
        assert len(second_prefix) == len(first_run_segments)
        assert second_prefix == first_run_segments

        appended_segments = [segment for segment in second_run_segments if int(segment["chapter_id"]) > 2]
        assert appended_segments
        assert all(int(segment.get("chapter_id", 0)) == 3 for segment in appended_segments)
        assert len(appended_segments) >= 1

        second_run_detail = client.get(f"/api/projects/{project_id}/runs/{second_run_id}").json()
        incremental_recompute = second_run_detail["config"].get("incremental_recompute")
        assert incremental_recompute is not None
        assert incremental_recompute["enabled"] is True
        assert incremental_recompute["reused_chapter_count"] == 2

        session = get_session_factory()()
        try:
            first_run_tag_count = (
                session.query(SubSegmentTag).filter(SubSegmentTag.run_id == first_run_id).count()
            )
            second_run_tag_count = (
                session.query(SubSegmentTag).filter(SubSegmentTag.run_id == second_run_id).count()
            )
            assert second_run_tag_count >= first_run_tag_count
        finally:
            session.close()
