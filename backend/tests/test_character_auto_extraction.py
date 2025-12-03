import io
import os

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_character_auto_extraction.db"

from pathlib import Path  # noqa: E402

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.main import app
from app.services.character_extraction import extract_character_candidates_from_texts


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_character_auto_extraction.db")
    if db_file.exists():
        db_file.unlink()


def test_unit_extract_character_candidates_from_dialogue_and_narration() -> None:
    candidates = extract_character_candidates_from_texts(
        [
            '"Look at the horizon," Aria said. "I see it." Aria said again.\n'
            "Mira asked the crew to hold. Later, Dax answered.\n",
            'The wind spoke and Dax replied to the rumor.',
        ]
    )

    assert {candidate.name for candidate in candidates} == {"Aria", "Mira", "Dax"}
    assert candidates[0].name == "Aria"
    assert candidates[0].confidence > candidates[1].confidence
    assert 0.35 <= candidates[0].confidence <= 0.99


def test_unit_extract_character_candidates_filters_known_names_case_insensitive() -> None:
    candidates = extract_character_candidates_from_texts(
        [
            '"Come on," Aria said. "Wait," Aria said.\n'
            "Mira asked for more supplies.\n",
            "Aria answered.",
        ],
        known_names={"aria"},
    )

    names = [candidate.name for candidate in candidates]
    assert names == ["Mira"]
    assert candidates[0].confidence >= 0.45


def _create_project_with_ingested_text(client: TestClient, title: str) -> int:
    project_resp = client.post("/api/projects", json={"title": title})
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    ingest_payload = (
        "Chapter 1\n"
        '"The gate is locked," Aria said. The lock clicked.\n\n'
        'Chapter 2\n'
        '"Wait," Nora said. Mira looked away.\n'
    )
    ingest_resp = client.post(
        f"/api/projects/{project_id}/ingest/txt",
        files={"file": ("novel.txt", io.BytesIO(ingest_payload.encode("utf-8")), "text/plain")},
    )
    assert ingest_resp.status_code == 200
    return project_id


def test_integration_character_auto_extraction_returns_only_new_names() -> None:
    with TestClient(app) as client:
        project_id = _create_project_with_ingested_text(client, "Auto Extraction Integration")

        import_resp = client.post(
            f"/api/projects/{project_id}/characters/import",
            files={
                "file": (
                    "characters.json",
                    io.BytesIO(
                        b'{"Mira":{"verbalized_form":"Mira","gender":"female","source":"manual","confidence":0.9}}'
                    ),
                    "application/json",
                )
            },
        )
        assert import_resp.status_code == 200

        extract_resp = client.post(f"/api/projects/{project_id}/characters/extract")
        assert extract_resp.status_code == 200
        payload = extract_resp.json()
        assert payload["project_id"] == project_id
        assert payload["status"] == "complete"
        assert payload["candidate_count"] == len(payload["candidates"]) == 2
        names = {entry["name"] for entry in payload["candidates"]}
        assert names == {"Aria", "Nora"}
        assert all(entry["source"] == "auto" for entry in payload["candidates"])
        assert all(0.35 <= entry["confidence"] <= 0.99 for entry in payload["candidates"])


def test_integration_character_auto_extraction_rejects_empty_chapters() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "No Chapters Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        extract_resp = client.post(f"/api/projects/{project_id}/characters/extract")
        assert extract_resp.status_code == 400
        assert extract_resp.json()["detail"] == "No chapters available for character auto-extraction."
