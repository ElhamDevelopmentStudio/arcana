import io
import json
import os
import pytest

from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_character_schema.db"

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import Character
from app.services.characters import parse_character_file


_SAMPLE_TEXT = (
    "Chapter 1\n"
    '"Sunny looked around," Sunny said. The cold wind cut through the dark street.\n\n'
    "Chapter 2\n"
    "Nephis smiled. Hope rose with the warm light."
)


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


def test_unit_parse_character_file_rejects_invalid_gender() -> None:
    payload = json.dumps({"Kai": {"verbalized_form": "Kai", "gender": "nonbinary"}}).encode("utf-8")

    with pytest.raises(ValueError, match="unsupported gender"):
        parse_character_file("characters.json", payload)


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


def test_integration_character_import_rejects_invalid_gender() -> None:
    payload = json.dumps({"Kai": {"verbalized_form": "Kai", "gender": "nonbinary"}}).encode("utf-8")

    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Invalid Gender Import"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        import_resp = client.post(
            f"/api/projects/{project_id}/characters/import",
            files={"file": ("characters.json", io.BytesIO(payload), "application/json")},
        )
        assert import_resp.status_code == 400
        assert "unsupported gender" in import_resp.json()["detail"]


def test_integration_character_map_rejects_invalid_gender_on_save() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Invalid Gender Save"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        save_resp = client.put(
            f"/api/projects/{project_id}/characters",
            json={
                "characters": [
                    {
                        "name": "Kai",
                        "verbalized_form": "Kai",
                        "gender": "nonbinary",
                        "aliases": [],
                        "notes": None,
                        "source": "manual",
                        "confidence": 1.0,
                        "source_trace": [],
                    }
                ]
            },
        )
        assert save_resp.status_code == 422
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


def test_integration_character_map_endpoints_list_and_replace() -> None:
    project_title = "Character Map Endpoint"
    imported_payload = json.dumps(
        {
            "Kai": {"verbalized_form": "Kai", "gender": "male"},
            "Nephis": {"verbalized_form": "Nephis", "gender": "female"},
        }
    ).encode("utf-8")

    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": project_title})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        import_resp = client.post(
            f"/api/projects/{project_id}/characters/import",
            files={"file": ("characters.json", io.BytesIO(imported_payload), "application/json")},
        )
        assert import_resp.status_code == 200

        list_resp = client.get(f"/api/projects/{project_id}/characters")
        assert list_resp.status_code == 200
        list_payload = list_resp.json()
        assert list_payload["project_id"] == project_id
        assert len(list_payload["characters"]) == 2
        assert list_payload["characters"][0]["name"] == "Kai"
        assert list_payload["characters"][1]["name"] == "Nephis"

        replace_payload = {
            "characters": [
                {
                    "name": " Nephis ",
                    "verbalized_form": "Nia",
                    "gender": "FEMALE",
                    "aliases": ["N"],
                    "notes": "Lead",
                    "source": "manual",
                    "confidence": 0.91,
                },
                {
                    "name": "kai",
                    "verbalized_form": "Kai",
                    "gender": "MALE",
                    "aliases": [],
                    "notes": "Lead",
                    "source": "manual",
                    "confidence": 1.0,
                },
                {
                    "name": "Kai",
                    "verbalized_form": "KAI-DUP",
                    "gender": "male",
                    "aliases": [],
                    "notes": "",
                    "source": "manual",
                    "confidence": 0.79,
                },
            ]
        }
        save_resp = client.put(f"/api/projects/{project_id}/characters", json=replace_payload)
        assert save_resp.status_code == 200
        save_payload = save_resp.json()
        assert save_payload["project_id"] == project_id
        assert len(save_payload["characters"]) == 2
        assert save_payload["characters"][0]["name"] == "Nephis"
        assert save_payload["characters"][0]["verbalized_form"] == "Nia"
        assert save_payload["characters"][0]["gender"] == "female"
        assert save_payload["characters"][1]["name"] == "Kai"
        assert save_payload["characters"][1]["verbalized_form"] == "KAI-DUP"
        assert save_payload["characters"][1]["gender"] == "male"

    session = get_session_factory()()
    try:
        rows = (
            session.query(Character)
            .filter(Character.project_id == project_id)
            .order_by(Character.name.asc())
            .all()
        )
        assert len(rows) == 2
        assert rows[0].name == "Kai"
        assert rows[0].verbalized_form == "KAI-DUP"
        assert rows[0].gender == "male"
        assert rows[0].aliases == []
        assert rows[0].notes is None
        assert rows[0].source == "manual"

        assert rows[1].name == "Nephis"
        assert rows[1].verbalized_form == "Nia"
        assert rows[1].notes == "Lead"
        assert rows[1].aliases == ["N"]
        assert rows[1].confidence == 0.91
    finally:
        session.close()


def test_integration_character_map_finalize_action_tracks_state() -> None:
    imported_payload = json.dumps({"Kai": {"verbalized_form": "Kai", "gender": "female"}}).encode("utf-8")

    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Character Finalization Flow"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        import_resp = client.post(
            f"/api/projects/{project_id}/characters/import",
            files={"file": ("characters.json", io.BytesIO(imported_payload), "application/json")},
        )
        assert import_resp.status_code == 200

        list_before_finalize_resp = client.get(f"/api/projects/{project_id}/characters")
        assert list_before_finalize_resp.status_code == 200
        assert list_before_finalize_resp.json()["character_map_finalized"] is False

        finalize_resp = client.post(f"/api/projects/{project_id}/characters/finalize")
        assert finalize_resp.status_code == 200
        assert finalize_resp.json()["character_map_finalized"] is True

        list_after_finalize_resp = client.get(f"/api/projects/{project_id}/characters")
        assert list_after_finalize_resp.status_code == 200
        assert list_after_finalize_resp.json()["character_map_finalized"] is True

        save_resp = client.put(
            f"/api/projects/{project_id}/characters",
            json={
                "characters": [
                    {
                        "name": "Kai",
                        "verbalized_form": "Kai",
                        "gender": "female",
                        "aliases": [],
                        "notes": None,
                        "source": "manual",
                        "confidence": 1.0,
                        "source_trace": [],
                    }
                ]
            },
        )
        assert save_resp.status_code == 200

        list_after_save_resp = client.get(f"/api/projects/{project_id}/characters")
        assert list_after_save_resp.status_code == 200
        assert list_after_save_resp.json()["character_map_finalized"] is False


def test_integration_run_pipeline_is_blocked_with_unfinalized_character_map() -> None:
    imported_payload = json.dumps({"Kai": {"verbalized_form": "Kai", "gender": "female"}}).encode("utf-8")

    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Unfinalized Character Map Run Gate"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", io.BytesIO(_SAMPLE_TEXT.encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200
        assert ingest_resp.json()["chapter_count"] == 2

        import_resp = client.post(
            f"/api/projects/{project_id}/characters/import",
            files={"file": ("characters.json", io.BytesIO(imported_payload), "application/json")},
        )
        assert import_resp.status_code == 200

        run_payload = {
            "max_segment_chars": 120,
            "llm_enabled": False,
            "provider_name": "openrouter",
            "max_calls_per_day": 2,
        }
        run_resp = client.post(f"/api/projects/{project_id}/runs", json=run_payload)
        assert run_resp.status_code == 409
        assert "not finalized" in run_resp.json()["detail"]


def test_integration_run_pipeline_with_unfinalized_character_map_override() -> None:
    imported_payload = json.dumps({"Kai": {"verbalized_form": "Kai", "gender": "female"}}).encode("utf-8")

    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Unfinalized Character Map Override Run"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", io.BytesIO(_SAMPLE_TEXT.encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200
        assert ingest_resp.json()["chapter_count"] == 2

        import_resp = client.post(
            f"/api/projects/{project_id}/characters/import",
            files={"file": ("characters.json", io.BytesIO(imported_payload), "application/json")},
        )
        assert import_resp.status_code == 200

        run_payload = {
            "max_segment_chars": 120,
            "llm_enabled": False,
            "provider_name": "openrouter",
            "max_calls_per_day": 2,
            "allow_unfinalized_character_map": True,
        }
        run_resp = client.post(f"/api/projects/{project_id}/runs", json=run_payload)
        assert run_resp.status_code == 200
        assert run_resp.json()["run_id"] > 0


def test_integration_run_pipeline_after_character_map_finalized() -> None:
    imported_payload = json.dumps({"Kai": {"verbalized_form": "Kai", "gender": "female"}}).encode("utf-8")

    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Finalized Character Map Run Gate"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", io.BytesIO(_SAMPLE_TEXT.encode("utf-8")), "text/plain")},
        )
        assert ingest_resp.status_code == 200
        assert ingest_resp.json()["chapter_count"] == 2

        import_resp = client.post(
            f"/api/projects/{project_id}/characters/import",
            files={"file": ("characters.json", io.BytesIO(imported_payload), "application/json")},
        )
        assert import_resp.status_code == 200

        finalize_resp = client.post(f"/api/projects/{project_id}/characters/finalize")
        assert finalize_resp.status_code == 200
        assert finalize_resp.json()["character_map_finalized"] is True

        run_payload = {
            "max_segment_chars": 120,
            "llm_enabled": False,
            "provider_name": "openrouter",
            "max_calls_per_day": 2,
        }
        run_resp = client.post(f"/api/projects/{project_id}/runs", json=run_payload)
        assert run_resp.status_code == 200
        assert run_resp.json()["run_id"] > 0


def test_integration_character_aliases_are_saved_and_deduplicated() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Manual Alias Persistence"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        save_resp = client.put(
            f"/api/projects/{project_id}/characters",
            json={
                "characters": [
                    {
                        "name": "Kai",
                        "verbalized_form": "Kai",
                        "gender": "female",
                        "aliases": [" Captain ", "C.", "", "Captain", "C."],
                        "notes": None,
                        "source": "manual",
                        "confidence": 1.0,
                        "source_trace": [],
                    }
                ]
            },
        )
        assert save_resp.status_code == 200
        assert save_resp.json()["characters"][0]["aliases"] == ["Captain", "C."]

        list_resp = client.get(f"/api/projects/{project_id}/characters")
        assert list_resp.status_code == 200
        assert list_resp.json()["characters"][0]["aliases"] == ["Captain", "C."]


def test_integration_character_alias_lookup_matches_canonical_name_and_alias_form() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Alias Lookup"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        save_resp = client.put(
            f"/api/projects/{project_id}/characters",
            json={
                "characters": [
                    {
                        "name": "Kai",
                        "verbalized_form": "Kai",
                        "gender": "male",
                        "aliases": ["Captain", "K."],
                        "notes": None,
                        "source": "manual",
                        "confidence": 1.0,
                        "source_trace": [],
                    }
                ]
            },
        )
        assert save_resp.status_code == 200

        canonical_resp = client.post(
            f"/api/projects/{project_id}/characters/lookup-alias",
            json={"alias": "  KAI  "},
        )
        assert canonical_resp.status_code == 200
        assert canonical_resp.json()["canonical_name"] == "Kai"
        assert canonical_resp.json()["match_source"] == "canonical"

        alias_resp = client.post(
            f"/api/projects/{project_id}/characters/lookup-alias",
            json={"alias": " cApTaIn "},
        )
        assert alias_resp.status_code == 200
        assert alias_resp.json()["canonical_name"] == "Kai"
        assert alias_resp.json()["match_source"] == "alias"
        assert alias_resp.json()["alias"] == "cApTaIn"


def test_integration_character_alias_lookup_returns_none_when_missing() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Alias Lookup Miss"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        save_resp = client.put(
            f"/api/projects/{project_id}/characters",
            json={
                "characters": [
                    {
                        "name": "Kai",
                        "verbalized_form": "Kai",
                        "gender": "male",
                        "aliases": [],
                        "notes": None,
                        "source": "manual",
                        "confidence": 1.0,
                        "source_trace": [],
                    }
                ]
            },
        )
        assert save_resp.status_code == 200

        missing_resp = client.post(
            f"/api/projects/{project_id}/characters/lookup-alias",
            json={"alias": "UnknownCharacter"},
        )
        assert missing_resp.status_code == 200
        payload = missing_resp.json()
        assert payload["canonical_name"] is None
        assert payload["match_source"] == "none"


def test_integration_character_alias_lookup_reports_conflict_for_ambiguous_alias() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Alias Conflict Lookup"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        save_resp = client.put(
            f"/api/projects/{project_id}/characters",
            json={
                "characters": [
                    {
                        "name": "Kai",
                        "verbalized_form": "Kai",
                        "gender": "male",
                        "aliases": ["Captain", "K."],
                        "notes": None,
                        "source": "manual",
                        "confidence": 1.0,
                        "source_trace": [],
                    },
                    {
                        "name": "Lio",
                        "verbalized_form": "Lio",
                        "gender": "female",
                        "aliases": ["captain", "A."],
                        "notes": None,
                        "source": "manual",
                        "confidence": 1.0,
                        "source_trace": [],
                    },
                ]
            },
        )
        assert save_resp.status_code == 200

        conflict_resp = client.post(
            f"/api/projects/{project_id}/characters/lookup-alias",
            json={"alias": "Captain"},
        )
        assert conflict_resp.status_code == 200
        conflict_payload = conflict_resp.json()
        assert conflict_payload["canonical_name"] is None
        assert conflict_payload["match_source"] == "conflict"


def test_integration_character_alias_collision_endpoint_reports_duplicates() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Alias Collision Endpoint"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        save_resp = client.put(
            f"/api/projects/{project_id}/characters",
            json={
                "characters": [
                    {
                        "name": "Kai",
                        "verbalized_form": "Kai",
                        "gender": "male",
                        "aliases": ["Captain", "K."],
                        "notes": None,
                        "source": "manual",
                        "confidence": 1.0,
                        "source_trace": [],
                    },
                    {
                        "name": "Lio",
                        "verbalized_form": "Lio",
                        "gender": "female",
                        "aliases": ["captain", "A."],
                        "notes": None,
                        "source": "manual",
                        "confidence": 1.0,
                        "source_trace": [],
                    },
                ]
            },
        )
        assert save_resp.status_code == 200

        collisions_resp = client.get(f"/api/projects/{project_id}/characters/alias-collisions")
        assert collisions_resp.status_code == 200
        payload = collisions_resp.json()
        assert len(payload["collisions"]) == 1
        collision = payload["collisions"][0]
        assert collision["alias"].lower() == "captain"
        assert collision["canonical_names"] == ["Kai", "Lio"]
