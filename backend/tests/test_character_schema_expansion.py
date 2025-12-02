import io
import json
import os

from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_character_schema.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Character
from app.services.characters import parse_character_file


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_character_schema.db")
    if db_file.exists():
        db_file.unlink()


def test_unit_parse_character_file_supports_extended_fields() -> None:
    payload = json.dumps(
        {
            "Kai": {
                "verbalized_form": "Kai",
                "gender": "female",
                "aliases": ["First", "Sky-Knight"],
                "notes": "Primary lead.",
                "source": "manual",
                "confidence": 0.88,
            }
        }
    ).encode("utf-8")

    parsed = parse_character_file("characters.json", payload)
    assert len(parsed) == 1
    row = parsed[0]
    assert row.aliases == ["First", "Sky-Knight"]
    assert row.notes == "Primary lead."
    assert row.source == "manual"
    assert row.confidence == 0.88


def test_integration_character_import_stores_schema_fields_and_defaults_for_legacy_rows() -> None:
    payload = json.dumps(
        {
            "Kai": {"verbalized_form": "Kai", "gender": "female"},
            "Lio": {"verbalized_form": "Lee-o", "gender": "male", "aliases": ["Li"], "confidence": 0.72},
        }
    ).encode("utf-8")

    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Character Schema Expansion"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        import_resp = client.post(
            f"/api/projects/{project_id}/characters/import",
            files={"file": ("characters.json", io.BytesIO(payload), "application/json")},
        )
        assert import_resp.status_code == 200
        assert import_resp.json()["imported_count"] == 2

        session = get_session_factory()()
        try:
            rows = (
                session.query(Character)
                .filter(Character.project_id == project_id)
                .order_by(Character.name.asc())
                .all()
            )

            kai = rows[0]
            lio = rows[1]
            assert kai.name == "Kai"
            assert kai.aliases == []
            assert kai.notes is None
            assert kai.source == "user_import"
            assert kai.confidence == 1.0

            assert lio.name == "Lio"
            assert lio.aliases == ["Li"]
            assert lio.confidence == 0.72
        finally:
            session.close()


def test_unit_parse_character_file_legacy_csv_uses_verbalized_header() -> None:
    csv_payload = "name,verbalized,gender\nKai,Kai,female\nLio,Lee-o,male\n"

    parsed = parse_character_file("characters.csv", csv_payload.encode("utf-8"))
    assert len(parsed) == 2
    assert parsed[0].name == "Kai"
    assert parsed[0].verbalized_form == "Kai"
    assert parsed[0].gender == "female"
    assert parsed[0].aliases == []
    assert parsed[0].source == "user_import"
    assert parsed[0].confidence == 1.0


def test_integration_character_import_keeps_legacy_csv_compatibility() -> None:
    csv_payload = "name,verbalized,gender\nKai,Kai,female\nLio,Lee-o,male\n"

    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Legacy Character CSV"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        import_resp = client.post(
            f"/api/projects/{project_id}/characters/import",
            files={"file": ("characters.csv", io.BytesIO(csv_payload.encode("utf-8")), "text/csv")},
        )
        assert import_resp.status_code == 200
        assert import_resp.json()["imported_count"] == 2

        session = get_session_factory()()
        try:
            rows = (
                session.query(Character)
                .filter(Character.project_id == project_id)
                .order_by(Character.name.asc())
                .all()
            )

            kai = rows[0]
            lio = rows[1]
            assert kai.name == "Kai"
            assert kai.verbalized_form == "Kai"
            assert kai.gender == "female"
            assert kai.aliases == []
            assert kai.source == "user_import"
            assert kai.confidence == 1.0

            assert lio.name == "Lio"
            assert lio.verbalized_form == "Lee-o"
            assert lio.gender == "male"
        finally:
            session.close()
