import io
import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_onboarding_seed_fixtures.db"

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.main import app

ROOT = Path(__file__).resolve().parents[2]
SEED_FIXTURES_DIR = ROOT / "seed_fixtures" / "quick_onboarding"


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_onboarding_seed_fixtures.db")
    if db_file.exists():
        db_file.unlink()


def _read_text_fixture(filename: str) -> str:
    text = (SEED_FIXTURES_DIR / filename).read_text(encoding="utf-8").strip()
    assert text
    return text


def _read_json_fixture(filename: str) -> object:
    with (SEED_FIXTURES_DIR / filename).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload


def test_unit_seed_fixture_inventory_snapshot() -> None:
    file_names = sorted(item.name for item in SEED_FIXTURES_DIR.iterdir() if item.is_file())
    assert file_names == ["README.md", "characters-minimal.json", "minimal-novel.txt", "run-request.json"]


def test_integration_seed_fixture_json_payload_shapes() -> None:
    run_request = _read_json_fixture("run-request.json")
    characters = _read_json_fixture("characters-minimal.json")

    assert isinstance(run_request, dict)
    assert run_request["mode"] == "audiobook"
    assert run_request["llm_enabled"] is False
    assert run_request["allow_unfinalized_character_map"] is True

    assert isinstance(characters, list)
    assert len(characters) == 2
    names = [str(item["name"]) for item in characters]
    assert names == ["Sunny", "Nephis"]


def test_e2e_seed_fixtures_support_create_ingest_run_and_export() -> None:
    with TestClient(app) as client:
        create_resp = client.post("/api/projects", json={"title": "Onboarding Seed Fixture Project"})
        assert create_resp.status_code == 201
        project_id = int(create_resp.json()["id"])

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={
                "file": (
                    "minimal-novel.txt",
                    io.BytesIO(_read_text_fixture("minimal-novel.txt").encode("utf-8")),
                    "text/plain",
                )
            },
        )
        assert ingest_resp.status_code == 200
        assert ingest_resp.json()["chapter_count"] == 2

        characters_payload = _read_json_fixture("characters-minimal.json")
        import_resp = client.post(
            f"/api/projects/{project_id}/characters/import",
            files={
                "file": (
                    "characters-minimal.json",
                    io.BytesIO(json.dumps(characters_payload).encode("utf-8")),
                    "application/json",
                )
            },
        )
        assert import_resp.status_code == 200
        assert import_resp.json()["imported_count"] == 2

        run_request_payload = _read_json_fixture("run-request.json")
        run_resp = client.post(f"/api/projects/{project_id}/runs", json=run_request_payload)
        assert run_resp.status_code == 200
        run_id = int(run_resp.json()["run_id"])
        assert run_resp.json()["segment_count"] > 0

        export_resp = client.get(f"/api/projects/{project_id}/exports/{run_id}.json")
        assert export_resp.status_code == 200
        export_payload = export_resp.json()
        assert export_payload["project_id"] == project_id
        assert export_payload["run_id"] == run_id
        assert len(export_payload["segments"]) > 0
