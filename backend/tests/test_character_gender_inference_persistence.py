import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_character_gender_inference_persistence.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Character


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_character_gender_inference_persistence.db")
    if db_file.exists():
        db_file.unlink()


def test_integration_persists_inferred_gender_fields() -> None:
    project_text = (
        "Chapter 1\n"
        '"Mr. Kai entered the hall," the old servant announced.\n'
        'Miss Nia was already waiting nearby.\n'
        '"She smiled." He smiled back.\n\n'
        "Chapter 2\n"
        'Nia whispered, "I saw her again."\n'
        "Kai nodded silently.\n"
    )

    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Gender Inference Persistence"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("novel.txt", io.BytesIO(project_text.encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200
        assert ingest_resp.json()["chapter_count"] == 2

        import_resp = client.post(
            f"/api/projects/{project_id}/characters/import",
            files={
                "file": (
                    "characters.json",
                    io.BytesIO(
                        b"{"
                        b'"Kai":{"verbalized_form":"Kai","gender":"unknown"},'
                        b'"Nia":{"verbalized_form":"Nia","gender":"unknown"}'
                        b"}"
                    ),
                    "application/json",
                )
            },
        )
        assert import_resp.status_code == 200

        infer_resp = client.post(f"/api/projects/{project_id}/characters/infer")
        assert infer_resp.status_code == 200
        payload = infer_resp.json()
        assert payload["project_id"] == project_id
        assert len(payload["characters"]) == 2

    session = get_session_factory()()
    try:
        kai = (
            session.query(Character)
            .filter(Character.project_id == project_id, Character.name == "Kai")
            .one()
        )
        nia = (
            session.query(Character)
            .filter(Character.project_id == project_id, Character.name == "Nia")
            .one()
        )

        assert kai.inferred_gender == "male"
        assert kai.inferred_confidence > 0.7
        assert isinstance(kai.inferred_source_trace, list)
        assert kai.inferred_source_trace, "Expected inferred evidence trace for Kai."
        assert any(trace["kind"].startswith("gender_inference_") for trace in kai.inferred_source_trace)

        assert nia.inferred_gender == "female"
        assert nia.inferred_confidence > 0.7
        assert isinstance(nia.inferred_source_trace, list)
        assert nia.inferred_source_trace
        assert any(trace["kind"].startswith("gender_inference_") for trace in nia.inferred_source_trace)

        assert kai.gender == "unknown"
        assert nia.gender == "unknown"
    finally:
        session.close()
