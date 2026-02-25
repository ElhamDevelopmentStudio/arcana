import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_ingest_append_overlap.db"

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.main import app
from app.services.ingestion import detect_append_overlap_or_duplicate


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_ingest_append_overlap.db")
    if db_file.exists():
        db_file.unlink()


def _initial_ingestion_payload() -> bytes:
    return b"Chapter 1\nSunny crossed the street and entered the station."


def test_unit_detect_append_overlap_or_duplicate_identifies_exact_duplicate() -> None:
    detected = detect_append_overlap_or_duplicate(
        new_title="Chapter 2",
        new_content="same content line",
        existing_chapters=[(1, "Chapter 1", "same content line")],
    )
    assert detected is not None
    assert detected["kind"] == "exact_content_duplicate"
    assert detected["chapter_index"] == 1


def test_integration_append_chapter_rejects_exact_duplicate_content() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Append Duplicate Integration"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("source.txt", io.BytesIO(_initial_ingestion_payload()), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        append_resp = client.post(
            f"/api/projects/{project_id}/ingest/append-chapter",
            files={"file": ("chapter_2.txt", io.BytesIO(b"Sunny crossed the street and entered the station."), "text/plain")},
        )
        assert append_resp.status_code == 409
        assert "exact_content_duplicate" in append_resp.json()["detail"]


def test_e2e_append_chapter_accepts_distinct_content() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Append Distinct E2E"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("source.txt", io.BytesIO(_initial_ingestion_payload()), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        append_resp = client.post(
            f"/api/projects/{project_id}/ingest/append-chapter",
            files={"file": ("chapter_2.txt", io.BytesIO(b"A completely new chapter event unfolds here."), "text/plain")},
        )
        assert append_resp.status_code == 200
        assert append_resp.json()["chapter_count"] == 2


def test_regression_append_rejects_same_title_high_overlap_content() -> None:
    long_block = (
        "Sunny stepped into the corridor and listened to the wind outside. "
        "He counted each breath, waited by the reinforced wall, and watched the patrol lights drift. "
        "No one spoke for several minutes."
    )
    overlap_block = (
        "Sunny stepped into the corridor and listened to the wind outside. "
        "He counted each breath, waited by the reinforced wall, and watched the patrol lights drift. "
        "No one spoke for several minutes. Then he noticed the terminal blinking."
    )

    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Append Overlap Regression"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("chapter_1.txt", io.BytesIO(f"Chapter 1\n{long_block}".encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        append_resp = client.post(
            f"/api/projects/{project_id}/ingest/append-chapter",
            files={"file": ("chapter_1.txt", io.BytesIO(overlap_block.encode("utf-8")), "text/plain")},
        )
        assert append_resp.status_code == 409
        assert "same_title_content_overlap" in append_resp.json()["detail"]
