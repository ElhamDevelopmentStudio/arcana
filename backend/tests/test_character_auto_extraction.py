import io
import os

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_character_auto_extraction.db"

from pathlib import Path  # noqa: E402

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.main import app
import app.main as app_main
from app.services.character_extraction import extract_character_candidates_from_texts
from app.services.character_extraction import CandidateEvidence, CandidateSourceTrace
from app.services.character_merge import build_canonical_name_merge_suggestions, merge_character_candidates
from app.services import character_scrape


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
    assert all(candidate.source_trace for candidate in candidates)
    assert any(trace.kind == "dialogue_attribution" for trace in candidates[0].source_trace)


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
    assert candidates[0].source_trace
    assert any(trace.kind in {"dialogue_attribution", "narrative_attribution"} for trace in candidates[0].source_trace)


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
        for entry in payload["candidates"]:
            assert isinstance(entry["source_trace"], list)
            assert entry["source_trace"], "Expected at least one source trace per candidate."
            trace = entry["source_trace"][0]
            assert set(trace.keys()) >= {
                "kind",
                "chapter_index",
                "span_start",
                "span_end",
                "excerpt",
                "weight",
            }


def test_integration_character_auto_extraction_rejects_empty_chapters() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "No Chapters Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        extract_resp = client.post(f"/api/projects/{project_id}/characters/extract")
        assert extract_resp.status_code == 400
        assert extract_resp.json()["detail"] == "No chapters available for character auto-extraction."


def test_integration_character_scrape_requires_warning_ack() -> None:
    with TestClient(app) as client:
        project_id = _create_project_with_ingested_text(client, "Scrape Warning Test")

        extract_resp = client.post(
            f"/api/projects/{project_id}/characters/scrape",
            json={"source_url": "https://example.com", "acknowledge_source_risk": False},
        )
        assert extract_resp.status_code == 400
        assert extract_resp.json()["detail"] == "You must acknowledge scrape risk before proceeding."


def test_integration_character_scrape_rejects_invalid_url() -> None:
    with TestClient(app) as client:
        project_id = _create_project_with_ingested_text(client, "Scrape Invalid URL Test")

        extract_resp = client.post(
            f"/api/projects/{project_id}/characters/scrape",
            json={"source_url": "ftp://example.com/guide", "acknowledge_source_risk": True},
        )
        assert extract_resp.status_code == 400
        assert extract_resp.json()["detail"] == "source_url must use http or https scheme."


def test_integration_character_scrape_returns_candidates(monkeypatch) -> None:
    def _fake_fetch_scrape_text(_: str, config: object | None = None) -> str:  # noqa: ARG001
        return (
            "<p>Mira looked around. \"The room is quiet,\" she said. "
            "Later, Jalen answered and spoke."
        )

    monkeypatch.setattr(character_scrape, "fetch_scrape_text", _fake_fetch_scrape_text)

    with TestClient(app) as client:
        project_id = _create_project_with_ingested_text(client, "Scrape Candidate Test")
        existing_import = client.post(
            f"/api/projects/{project_id}/characters/import",
            files={
                "file": (
                    "characters.json",
                    io.BytesIO(b'{\"Mira\":{\"verbalized_form\":\"Mira\",\"gender\":\"female\",\"source\":\"manual\",\"confidence\":0.9}}'),
                    "application/json",
                )
            },
        )
        assert existing_import.status_code == 200

        extract_resp = client.post(
            f"/api/projects/{project_id}/characters/scrape",
            json={"source_url": "https://example.com/characters", "acknowledge_source_risk": True},
        )
        assert extract_resp.status_code == 200
        payload = extract_resp.json()
        assert payload["project_id"] == project_id
        assert payload["status"] == "complete"
        assert payload["candidate_count"] == 1
        assert payload["candidates"][0]["name"] == "Jalen"
        assert payload["candidates"][0]["source"] == "scrape"
        assert payload["candidates"][0]["source_trace"]


def test_unit_merge_character_candidates_normalizes_and_merges() -> None:
    merged = merge_character_candidates(
        [
            {
                "name": "Nora",
                "verbalized_form": "Nora",
                "gender": "female",
                "aliases": ["N."],
                "notes": "core",
                "source": "manual",
                "confidence": 1.0,
                "source_trace": [],
            },
            {
                "name": "  nora  ",
                "verbalized_form": "Nora",
                "gender": "unknown",
                "aliases": [],
                "notes": None,
                "source": "auto",
                "confidence": 0.7,
                "source_trace": [
                    {
                        "kind": "dialogue_attribution",
                        "chapter_index": 1,
                        "span_start": 0,
                        "span_end": 1,
                        "excerpt": "Nora said...",
                        "weight": 0.8,
                    }
                ],
            },
            {
                "name": "Mira",
                "verbalized_form": "Mira",
                "gender": "unknown",
                "aliases": [],
                "notes": None,
                "source": "scrape",
                "confidence": 0.81,
                "source_trace": [
                    {
                        "kind": "dialogue_attribution",
                        "chapter_index": 2,
                        "span_start": 2,
                        "span_end": 8,
                        "excerpt": "Mira appeared.",
                        "weight": 0.6,
                    }
                ],
            },
        ]
    )

    assert len(merged) == 2

    merged_map = {entry["name"]: entry for entry in merged}
    assert merged_map["Nora"]["source"] == "merged:auto|user_import"
    assert merged_map["Nora"]["aliases"] == ["N."]
    assert merged_map["Nora"]["source_trace"] == [
        {
            "kind": "dialogue_attribution",
            "chapter_index": 1,
            "span_start": 0,
            "span_end": 1,
            "excerpt": "Nora said...",
            "weight": 0.8,
        }
    ]


def test_unit_build_canonical_name_merge_suggestions_identifies_similar_existing_canonical_names() -> None:
    candidate_payloads = [
        {
            "name": "Miran",
            "verbalized_form": "Miran",
            "gender": "female",
            "aliases": [],
            "notes": None,
            "source": "auto",
            "confidence": 0.74,
            "source_trace": [],
        },
        {
            "name": "Nora",
            "verbalized_form": "Nora",
            "gender": "female",
            "aliases": [],
            "notes": None,
            "source": "auto",
            "confidence": 0.62,
            "source_trace": [],
        },
    ]

    suggestions = build_canonical_name_merge_suggestions(
        candidate_payloads=candidate_payloads,
        canonical_names={"Mira", "Lio"},
    )

    assert len(suggestions) == 1
    assert suggestions[0]["canonical_name"] == "Mira"
    assert suggestions[0]["alias_name"] == "Miran"
    assert suggestions[0]["candidate_source"] == "auto"
    assert suggestions[0]["canonical_source"] == "user_import"
    assert suggestions[0]["reason"] == "name_similarity"
    assert suggestions[0]["score"] >= 0.86


def test_unit_build_canonical_name_merge_suggestions_ignores_non_matches_and_existing() -> None:
    candidate_payloads = [
        {
            "name": "Mira",
            "verbalized_form": "Mira",
            "gender": "female",
            "aliases": [],
            "notes": None,
            "source": "auto",
            "confidence": 0.74,
            "source_trace": [],
        },
        {
            "name": "Brianna",
            "verbalized_form": "Brianna",
            "gender": "female",
            "aliases": [],
            "notes": None,
            "source": "auto",
            "confidence": 0.62,
            "source_trace": [],
        },
    ]

    suggestions = build_canonical_name_merge_suggestions(
        candidate_payloads=candidate_payloads,
        canonical_names={"Mira", "Lio"},
        threshold=0.9,
    )

    assert suggestions == []


def test_integration_character_merge_candidates_endpoint_merges_auto_and_scrape(monkeypatch) -> None:
    def _fake_extract_character_candidates_from_texts(
        _chapter_texts: list[str],
        known_names: set[str] | None = None,
    ) -> list[CandidateEvidence]:
        del known_names
        return [
            CandidateEvidence(
                name="Lena",
                confidence=0.62,
                source_trace=[
                    CandidateSourceTrace(
                        kind="dialogue_attribution",
                        chapter_index=1,
                        span_start=0,
                        span_end=2,
                        excerpt="Lena stepped forward.",
                        weight=1.0,
                    )
                ],
            ),
            CandidateEvidence(
                name="Mira",
                confidence=0.52,
                source_trace=[
                    CandidateSourceTrace(
                        kind="dialogue_attribution",
                        chapter_index=2,
                        span_start=10,
                        span_end=14,
                        excerpt="Mira replied.",
                        weight=1.0,
                    )
                ],
            ),
        ]

    def _fake_extract_scrape_candidates(_: str, config: object | None = None) -> list[CandidateEvidence]:
        return [
            CandidateEvidence(
                name="Lena",
                confidence=0.88,
                source_trace=[
                    CandidateSourceTrace(
                        kind="narrative_attribution",
                        chapter_index=1,
                        span_start=20,
                        span_end=25,
                        excerpt="Lena moved on.",
                        weight=0.6,
                    )
                ],
            ),
        ]

    monkeypatch.setattr(app_main, "extract_character_candidates_from_texts", _fake_extract_character_candidates_from_texts)
    monkeypatch.setattr(app_main, "extract_character_candidates_from_scrape_url", _fake_extract_scrape_candidates)

    with TestClient(app) as client:
        project_id = _create_project_with_ingested_text(client, "Merge Candidate Integration")
        existing_import = client.post(
            f"/api/projects/{project_id}/characters/import",
            files={
                "file": (
                    "characters.json",
                    io.BytesIO(b'{\"Mira\":{\"verbalized_form\":\"Mira\",\"gender\":\"female\",\"source\":\"manual\",\"confidence\":1.0}}'),
                    "application/json",
                )
            },
        )
        assert existing_import.status_code == 200

        merged_resp = client.post(
            f"/api/projects/{project_id}/characters/merged-candidates",
            json={"source_url": "https://example.com/characters", "acknowledge_source_risk": True, "include_auto": True},
        )
        assert merged_resp.status_code == 200
        merged_payload = merged_resp.json()
        assert merged_payload["status"] == "complete"
        names = sorted(entry["name"] for entry in merged_payload["candidates"])
        assert names == ["Lena", "Mira"]
        merged_map = {entry["name"]: entry for entry in merged_payload["candidates"]}
        assert merged_map["Lena"]["source"] == "merged:auto|scrape"
        assert merged_map["Mira"]["source"] == "merged:auto|user_import"
        assert len(merged_map["Lena"]["source_trace"]) == 2

        assert "proposed_characters" in merged_payload
        proposed = merged_payload["proposed_characters"]
        assert isinstance(proposed, list)
        assert len(proposed) == 1
        assert proposed[0]["name"] == "Lena"
        assert proposed[0]["source"] == "merged:auto|scrape"


def test_integration_character_merge_candidates_endpoint_returns_canonical_merge_suggestions(monkeypatch) -> None:
    def _fake_extract_character_candidates_from_texts(
        _chapter_texts: list[str],
        known_names: set[str] | None = None,
    ) -> list[CandidateEvidence]:
        del known_names
        return [
            CandidateEvidence(
                name="Miran",
                confidence=0.72,
                source_trace=[
                    CandidateSourceTrace(
                        kind="dialogue_attribution",
                        chapter_index=1,
                        span_start=2,
                        span_end=7,
                        excerpt="Miran appeared.",
                        weight=0.9,
                    )
                ],
            ),
            CandidateEvidence(
                name="Lio",
                confidence=0.52,
                source_trace=[
                    CandidateSourceTrace(
                        kind="narrative_attribution",
                        chapter_index=2,
                        span_start=14,
                        span_end=17,
                        excerpt="Lio entered.",
                        weight=1.0,
                    )
                ],
            ),
        ]

    monkeypatch.setattr(app_main, "extract_character_candidates_from_texts", _fake_extract_character_candidates_from_texts)

    with TestClient(app) as client:
        project_id = _create_project_with_ingested_text(client, "Merge Candidate Suggestions Integration")
        existing_import = client.post(
            f"/api/projects/{project_id}/characters/import",
            files={
                "file": (
                    "characters.json",
                    io.BytesIO(b'{\"Mira\":{\"verbalized_form\":\"Mira\",\"gender\":\"female\",\"source\":\"manual\",\"confidence\":1.0}}'),
                    "application/json",
                )
            },
        )
        assert existing_import.status_code == 200

        merged_resp = client.post(
            f"/api/projects/{project_id}/characters/merged-candidates",
            json={"include_auto": True},
        )
        assert merged_resp.status_code == 200
        merged_payload = merged_resp.json()
        assert merged_payload["status"] == "complete"
        assert merged_payload["candidate_count"] == len(merged_payload["candidates"]) == 3

        assert merged_payload["canonical_merge_suggestions"]
        suggestions = merged_payload["canonical_merge_suggestions"]
        assert len(suggestions) == 1
        suggestion = suggestions[0]
        assert suggestion["canonical_name"] == "Mira"
        assert suggestion["alias_name"] == "Miran"
        assert suggestion["candidate_source"] == "auto"
        assert suggestion["canonical_source"] == "user_import"
        assert suggestion["reason"] == "name_similarity"
        assert suggestion["score"] >= 0.85

        assert "proposed_characters" in merged_payload
        proposed = merged_payload["proposed_characters"]
        assert len(proposed) == 2
        proposed_names = {entry["name"] for entry in proposed}
        assert proposed_names == {"Miran", "Lio"}
