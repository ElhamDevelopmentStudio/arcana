import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_mvp_ingest_txt_and_chapter_directory.db"

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.main import app


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_mvp_ingest_txt_and_chapter_directory.db")
    if db_file.exists():
        db_file.unlink()


def test_acceptance_ingest_supports_txt_and_chapter_directory_paths() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "MVP TXT + Directory Ingestion"})
        assert project_resp.status_code == 201
        project_id = int(project_resp.json()["id"])

        txt_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": (
                    "novel.txt",
                    io.BytesIO(
                        (
                            "Chapter 1\n"
                            "The gate stood open.\n\n"
                            "Chapter 2\n"
                            "Footsteps echoed in the hall."
                        ).encode("utf-8")
                    ),
                    "text/plain",
                )
            },
        )
        assert txt_resp.status_code == 200
        assert int(txt_resp.json()["chapter_count"]) >= 2

        directory_resp = client.post(
            f"/api/projects/{project_id}/ingest/chapters-dir",
            files=[
                (
                    "files",
                    (
                        "001-first.txt",
                        io.BytesIO("Chapter One\nA lantern flickered.".encode("utf-8")),
                        "text/plain",
                    ),
                ),
                (
                    "files",
                    (
                        "002-second.txt",
                        io.BytesIO("Chapter Two\nThe harbor went silent.".encode("utf-8")),
                        "text/plain",
                    ),
                ),
            ],
        )
        assert directory_resp.status_code == 200
        assert int(directory_resp.json()["chapter_count"]) >= 2
