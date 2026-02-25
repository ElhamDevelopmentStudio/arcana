import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_mode_switch.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Chapter, Project
from app.schemas import ProjectModeSwitchRequest


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_mode_switch.db")
    if db_file.exists():
        db_file.unlink()


def _sample_txt() -> str:
    return (
        "Chapter 1\n"
        '"Sunny looked around," Sunny said. The cold wind cut through the dark street.\n\n'
        "Chapter 2\n"
        "Nephis smiled. Hope rose with the warm light."
    )


def test_unit_project_mode_switch_request_normalizes_mode() -> None:
    payload = ProjectModeSwitchRequest(mode="  AUTHOR ")
    assert payload.mode == "author"


def test_integration_mode_switch_endpoint_persists_selected_mode() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Mode Switch Integration"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]
        assert project_resp.json()["selected_mode"] == "audiobook"

        switch_resp = client.put(
            f"/api/projects/{project_id}/mode",
            json={"mode": "academic"},
        )
        assert switch_resp.status_code == 200
        payload = switch_resp.json()
        assert payload["project_id"] == project_id
        assert payload["previous_mode"] == "audiobook"
        assert payload["selected_mode"] == "academic"
        assert payload["chapter_count"] == 0
        assert payload["reused_ingested_corpus"] is False

    session = get_session_factory()()
    try:
        project = session.query(Project).filter(Project.id == project_id).one()
        assert project.selected_mode == "academic"
    finally:
        session.close()


def test_e2e_mode_switch_reuses_ingested_corpus_without_reingestion() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Mode Switch E2E"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200
        assert ingest_resp.json()["chapter_count"] == 2

        session = get_session_factory()()
        try:
            chapter_text_before = [
                chapter.raw_text
                for chapter in session.query(Chapter)
                .filter(Chapter.project_id == project_id)
                .order_by(Chapter.chapter_index.asc())
                .all()
            ]
        finally:
            session.close()

        switch_resp = client.put(
            f"/api/projects/{project_id}/mode",
            json={"mode": "author"},
        )
        assert switch_resp.status_code == 200
        payload = switch_resp.json()
        assert payload["previous_mode"] == "audiobook"
        assert payload["selected_mode"] == "author"
        assert payload["chapter_count"] == 2
        assert payload["reused_ingested_corpus"] is True

    session = get_session_factory()()
    try:
        chapter_text_after = [
            chapter.raw_text
            for chapter in session.query(Chapter)
            .filter(Chapter.project_id == project_id)
            .order_by(Chapter.chapter_index.asc())
            .all()
        ]
        assert chapter_text_after == chapter_text_before
    finally:
        session.close()


def test_regression_mode_switch_response_snapshot() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Mode Switch Regression"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        switch_resp = client.put(
            f"/api/projects/{project_id}/mode",
            json={"mode": "custom"},
        )
        assert switch_resp.status_code == 200
        assert switch_resp.json() == {
            "project_id": project_id,
            "previous_mode": "audiobook",
            "selected_mode": "custom",
            "chapter_count": 0,
            "reused_ingested_corpus": False,
        }


def test_regression_repeated_mode_switches_do_not_duplicate_raw_text_rows() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Mode Switch Raw Text Integrity"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", io.BytesIO(_sample_txt().encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200
        assert ingest_resp.json()["chapter_count"] == 2

        session = get_session_factory()()
        try:
            before_rows = (
                session.query(Chapter)
                .filter(Chapter.project_id == project_id)
                .order_by(Chapter.chapter_index.asc())
                .all()
            )
            before_snapshot = [(row.id, row.chapter_index, row.raw_text) for row in before_rows]
        finally:
            session.close()

        for mode in ["academic", "author", "custom", "audiobook"]:
            switch_resp = client.put(
                f"/api/projects/{project_id}/mode",
                json={"mode": mode},
            )
            assert switch_resp.status_code == 200

    session = get_session_factory()()
    try:
        after_rows = (
            session.query(Chapter)
            .filter(Chapter.project_id == project_id)
            .order_by(Chapter.chapter_index.asc())
            .all()
        )
        after_snapshot = [(row.id, row.chapter_index, row.raw_text) for row in after_rows]
        assert after_snapshot == before_snapshot
        assert len(after_rows) == 2
        assert len({row.raw_text for row in after_rows}) == 2
    finally:
        session.close()
