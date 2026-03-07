import io
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_project_source_text_privacy.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Chapter, Project, ProjectRawCorpusBlob
from app.schemas import ProjectCreate, ProjectResponse


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_project_source_text_privacy.db")
    if db_file.exists():
        db_file.unlink()


def _sample_txt() -> str:
    return (
        "Chapter 1\n"
        "The wind moved softly through the hall.\n\n"
        "Chapter 2\n"
        "A lantern lit the stairs."
    )


def test_unit_project_create_schema_supports_do_not_store_source_text_defaults_and_override() -> None:
    payload = ProjectCreate(title="Source Privacy Unit")
    assert payload.do_not_store_source_text is False

    payload_override = ProjectCreate(title="Source Privacy Unit", do_not_store_source_text=True)
    assert payload_override.do_not_store_source_text is True

    response = ProjectResponse(
        id=1,
        title="Privacy Unit",
        selected_mode="audiobook",
        selected_modes=["audiobook"],
        llm_enabled=False,
        do_not_store_source_text=True,
        configuration_snapshot_id="project-1-config-initial",
        character_map_finalized=False,
        ingestion_timestamp=None,
        created_at=datetime.now(timezone.utc),
    )
    assert response.do_not_store_source_text is True


def test_integration_project_create_persists_do_not_store_source_text_preference() -> None:
    with TestClient(app) as client:
        project_resp = client.post(
            "/api/projects",
            json={"title": "Source Privacy Create", "do_not_store_source_text": True},
        )
    assert project_resp.status_code == 201

    payload = project_resp.json()
    assert payload["do_not_store_source_text"] is True
    project_id = payload["id"]

    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        assert project.do_not_store_source_text is True
    finally:
        session.close()


def test_integration_ingest_skips_raw_corpus_persistence_when_do_not_store_source_text_is_set() -> None:
    with TestClient(app) as client:
        project_resp = client.post(
            "/api/projects",
            json={"title": "Source Privacy Ingest", "do_not_store_source_text": True},
        )
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("story.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200
        assert ingest_resp.json()["chapter_count"] > 0

    session = get_session_factory()()
    try:
        raw_corpus_blobs = session.query(ProjectRawCorpusBlob).filter(
            ProjectRawCorpusBlob.project_id == project_id
        ).all()
        assert len(raw_corpus_blobs) == 0
    finally:
        session.close()


def test_integration_ingest_strips_chapter_level_source_text_in_derived_metrics_mode() -> None:
    with TestClient(app) as client:
        project_resp = client.post(
            "/api/projects",
            json={"title": "Source Privacy Chapter Source", "do_not_store_source_text": True},
        )
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("story.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

    session = get_session_factory()()
    try:
        chapters = session.query(Chapter).filter(Chapter.project_id == project_id).order_by(Chapter.chapter_index.asc()).all()
        assert len(chapters) > 0
        for chapter in chapters:
            assert chapter.raw_text == ""
            assert chapter.original_text_snapshot == ""
            assert chapter.original_to_normalized_offset_map == []
            assert chapter.normalized_text
    finally:
        session.close()


def test_integration_run_artifact_integrity_accepts_no_raw_corpus_blobs_for_privacy_mode_project() -> None:
    with TestClient(app) as client:
        project_resp = client.post(
            "/api/projects",
            json={"title": "Source Privacy Run Integrity", "do_not_store_source_text": True},
        )
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("story.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={"max_segment_chars": 80, "llm_enabled": False, "allow_unfinalized_character_map": True},
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        detail_resp = client.get(f"/api/projects/{project_id}/runs/{run_id}")
        assert detail_resp.status_code == 200
        artifact_integrity = detail_resp.json()["config"]["artifact_integrity"]

    checks = {entry["artifact"]: entry for entry in artifact_integrity["checks"]}
    assert artifact_integrity["is_artifact_integrity_intact"] is True
    assert checks["project_raw_corpus_blobs"]["passed"] is True
    assert checks["project_raw_corpus_blobs"]["details"]["reason"] == "do_not_store_source_text"
    assert checks["project_raw_corpus_blobs"]["details"]["observed_count"] == 0

    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        assert project.do_not_store_source_text is True
        raw_corpus_blobs = session.query(ProjectRawCorpusBlob).filter(
            ProjectRawCorpusBlob.project_id == project_id
        ).all()
        assert len(raw_corpus_blobs) == 0
    finally:
        session.close()
