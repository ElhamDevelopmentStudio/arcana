import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipg_preview.db"

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

    db_file = Path("test_nipg_preview.db")
    if db_file.exists():
        db_file.unlink()


def test_integration_preview_uses_character_scope_when_present() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Pronunciation Preview Merge"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        global_resp = client.put(
            f"/api/projects/{project_id}/pronunciation-dictionary/global",
            json={
                "entries": [
                    {"term": "Aegis", "verbalized_form": "EE-jis", "confidence": 1.0},
                    {"term": "Captain", "verbalized_form": "Cap-itan", "confidence": 1.0},
                ]
            },
        )
        assert global_resp.status_code == 200

        character_resp = client.put(
            f"/api/projects/{project_id}/pronunciation-dictionary/character/Alice",
            json={
                "entries": [
                    {"term": "Aegis", "verbalized_form": "Ah-jeez", "confidence": 0.95},
                ]
            },
        )
        assert character_resp.status_code == 200

        preview_resp = client.post(
            f"/api/projects/{project_id}/pronunciation-dictionary/preview",
            json={
                "text": "Captain saw the Aegis at dawn. Captain then passed the old Aegis signal.",
                "character_name": "Alice",
                "include_global_scope": True,
                "include_character_scope": True,
            },
        )
        assert preview_resp.status_code == 200

        payload = preview_resp.json()
        assert payload["project_id"] == project_id
        assert payload["character_name"] == "Alice"
        assert payload["included_scopes"] == ["global", "character"]
        assert payload["after"].count("Ah-jeez") == 2
        assert "EE-jis" not in payload["after"]
        replacements = payload["replacements"]
        assert len(replacements) == 2
        assert any(item["term"] == "Aegis" and item["scope"] == "character" for item in replacements)
        assert any(item["term"] == "Captain" and item["scope"] == "global" for item in replacements)
        assert payload["before"] == "Captain saw the Aegis at dawn. Captain then passed the old Aegis signal."


def test_integration_preview_flags_ambiguous_replacement_candidates() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Pronunciation Preview Ambiguous Candidates"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        global_resp = client.put(
            f"/api/projects/{project_id}/pronunciation-dictionary/global",
            json={"entries": [{"term": "Aegis", "verbalized_form": "EE-jis", "confidence": 1.0}]},
        )
        assert global_resp.status_code == 200

        character_resp = client.put(
            f"/api/projects/{project_id}/pronunciation-dictionary/character/Alice",
            json={
                "entries": [
                    {"term": "Aegis", "verbalized_form": "Ah-jeez", "confidence": 1.0},
                ]
            },
        )
        assert character_resp.status_code == 200

        preview_resp = client.post(
            f"/api/projects/{project_id}/pronunciation-dictionary/preview",
            json={
                "text": "Aegis sounded at dawn.",
                "character_name": "Alice",
                "include_global_scope": True,
                "include_character_scope": True,
            },
        )
        assert preview_resp.status_code == 200

        payload = preview_resp.json()
        assert payload["after"] == "Ah-jeez sounded at dawn."
        assert payload["warnings"] == [
            {
                "type": "ambiguous_replacement",
                "term": "Aegis",
                "message": "Ambiguous replacement for 'Aegis' from scopes: character, global.",
                "scopes": ["character", "global"],
                "competing_verbalized_forms": ["Ah-jeez", "EE-jis"],
            }
        ]


def test_integration_preview_global_scope_only_when_character_scope_disabled() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Pronunciation Preview Global Only"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        global_resp = client.put(
            f"/api/projects/{project_id}/pronunciation-dictionary/global",
            json={"entries": [{"term": "Aegis", "verbalized_form": "EE-jis", "confidence": 1.0}]},
        )
        assert global_resp.status_code == 200

        character_resp = client.put(
            f"/api/projects/{project_id}/pronunciation-dictionary/character/Alice",
            json={"entries": [{"term": "Aegis", "verbalized_form": "Ah-jeez", "confidence": 0.9}]},
        )
        assert character_resp.status_code == 200

        preview_resp = client.post(
            f"/api/projects/{project_id}/pronunciation-dictionary/preview",
            json={
                "text": "The Aegis glimmered near the tower.",
                "character_name": "Alice",
                "include_global_scope": True,
                "include_character_scope": False,
            },
        )
        assert preview_resp.status_code == 200
        payload = preview_resp.json()
        assert payload["after"] == "The EE-jis glimmered near the tower."
        assert payload["replacements"][0]["term"] == "Aegis"


def test_integration_preview_can_match_substrings() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Pronunciation Preview Substring Matching"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        global_resp = client.put(
            f"/api/projects/{project_id}/pronunciation-dictionary/global",
            json={"entries": [{"term": "Aegis", "verbalized_form": "EE-jis", "confidence": 1.0}]},
        )
        assert global_resp.status_code == 200

        preview_resp = client.post(
            f"/api/projects/{project_id}/pronunciation-dictionary/preview",
            json={
                "text": "CaptainAegis and Aegis.",
                "include_global_scope": True,
                "include_character_scope": False,
                "match_whole_words": False,
            },
        )
        assert preview_resp.status_code == 200
        payload = preview_resp.json()
        assert payload["after"] == "CaptainEE-jis and EE-jis."
        assert payload["replacements"] == [
            {
                "term": "Aegis",
                "verbalized_form": "EE-jis",
                "count": 2,
                "scope": "global",
            }
        ]


def test_integration_preview_can_match_case_insensitively() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Pronunciation Preview Case Sensitivity"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        global_resp = client.put(
            f"/api/projects/{project_id}/pronunciation-dictionary/global",
            json={"entries": [{"term": "Aegis", "verbalized_form": "EE-jis", "confidence": 1.0}]},
        )
        assert global_resp.status_code == 200

        preview_resp = client.post(
            f"/api/projects/{project_id}/pronunciation-dictionary/preview",
            json={
                "text": "Aegis spoke with aegis and AEGIS.",
                "include_global_scope": True,
                "include_character_scope": False,
                "case_sensitive": False,
            },
        )
        assert preview_resp.status_code == 200
        payload = preview_resp.json()
        assert payload["after"] == "EE-jis spoke with EE-jis and EE-jis."
        assert payload["replacements"] == [
            {
                "term": "Aegis",
                "verbalized_form": "EE-jis",
                "count": 3,
                "scope": "global",
            }
        ]


def test_integration_preview_includes_place_scope_terms() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Pronunciation Preview Place Terms"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        place_resp = client.put(
            f"/api/projects/{project_id}/pronunciation-dictionary/places",
            json={"entries": [{"term": "Narnia", "verbalized_form": "Nar-nia", "confidence": 1.0}]},
        )
        assert place_resp.status_code == 200

        preview_resp = client.post(
            f"/api/projects/{project_id}/pronunciation-dictionary/preview",
            json={
                "text": "They reached the gates of Narnia.",
                "include_global_scope": True,
                "include_character_scope": False,
                "include_place_scope": True,
            },
        )
        assert preview_resp.status_code == 200
        payload = preview_resp.json()
        assert payload["after"] == "They reached the gates of Nar-nia."
        assert payload["included_scopes"] == ["place"]
        assert payload["replacements"] == [
            {
                "term": "Narnia",
                "verbalized_form": "Nar-nia",
                "count": 1,
                "scope": "place",
            }
        ]


def test_integration_preview_includes_artifact_scope_terms() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Pronunciation Preview Artifact Terms"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        artifact_resp = client.put(
            f"/api/projects/{project_id}/pronunciation-dictionary/artifacts",
            json={"entries": [{"term": "phylactery", "verbalized_form": "artefact-phrase", "confidence": 1.0}]},
        )
        assert artifact_resp.status_code == 200

        preview_resp = client.post(
            f"/api/projects/{project_id}/pronunciation-dictionary/preview",
            json={
                "text": "The phylactery hummed in the crypt.",
                "include_global_scope": False,
                "include_character_scope": False,
                "include_artifact_scope": True,
            },
        )
        assert preview_resp.status_code == 200
        payload = preview_resp.json()
        assert payload["after"] == "The artefact-phrase hummed in the crypt."
        assert payload["included_scopes"] == ["artifact"]
        assert payload["replacements"] == [
            {
                "term": "phylactery",
                "verbalized_form": "artefact-phrase",
                "count": 1,
                "scope": "artifact",
            }
        ]


def test_integration_preview_rejects_empty_scopes() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Pronunciation Preview Validation"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        preview_resp = client.post(
            f"/api/projects/{project_id}/pronunciation-dictionary/preview",
            json={
                "text": "The same phrase again.",
                "include_global_scope": False,
                "include_character_scope": False,
            },
        )
        assert preview_resp.status_code == 400
        assert (
            preview_resp.json()["detail"]
            == "Set at least one of include_global_scope, include_character_scope, include_place_scope, or include_artifact_scope to true."
        )


def test_integration_preview_alias_aware_replaces_aliases_when_enabled() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Pronunciation Preview Alias Aware"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        character_map_resp = client.put(
            f"/api/projects/{project_id}/characters",
            json={
                "characters": [
                    {
                        "name": "Alice",
                        "verbalized_form": "A-lise",
                        "gender": "female",
                        "aliases": ["Al"],
                        "notes": "alias test",
                        "source": "manual",
                        "confidence": 1.0,
                    },
                ],
            },
        )
        assert character_map_resp.status_code == 200

        preview_without_alias_aware = client.post(
            f"/api/projects/{project_id}/pronunciation-dictionary/preview",
            json={
                "text": "Al waited by the lantern.",
                "character_name": "Alice",
                "include_global_scope": False,
                "include_character_scope": True,
                "alias_aware": False,
            },
        )
        assert preview_without_alias_aware.status_code == 200
        payload_without_alias_aware = preview_without_alias_aware.json()
        assert payload_without_alias_aware["after"] == "Al waited by the lantern."
        assert payload_without_alias_aware["replacements"] == []
        assert payload_without_alias_aware["included_scopes"] == []

        preview_with_alias_aware = client.post(
            f"/api/projects/{project_id}/pronunciation-dictionary/preview",
            json={
                "text": "Al waited by the lantern.",
                "character_name": "Alice",
                "include_global_scope": False,
                "include_character_scope": True,
                "alias_aware": True,
            },
        )
        assert preview_with_alias_aware.status_code == 200
        payload_with_alias_aware = preview_with_alias_aware.json()
        assert payload_with_alias_aware["after"] == "A-lise waited by the lantern."
        assert payload_with_alias_aware["included_scopes"] == ["character"]
        assert payload_with_alias_aware["replacements"] == [
            {
                "term": "Al",
                "verbalized_form": "A-lise",
                "count": 1,
                "scope": "character",
            },
        ]
