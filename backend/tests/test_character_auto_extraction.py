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


def test_unit_extract_character_candidates_decodes_hex_escaped_chapter_text() -> None:
    plain_text = '"Watch the horizon," Sunny said. Nephis replied.'
    hex_escaped_text = "\\x" + plain_text.encode("utf-8").hex()

    candidates = extract_character_candidates_from_texts([hex_escaped_text])

    assert {candidate.name for candidate in candidates} == {"Sunny", "Nephis"}


def test_unit_extract_character_candidates_detects_bracketed_character_headings() -> None:
    candidates = extract_character_candidates_from_texts(
        [
            "[Kim Suho]\nA righteous man.\n\n[Shin Jonghak]\nAn elite heir.",
        ]
    )

    assert {candidate.name for candidate in candidates} == {"Kim Suho", "Shin Jonghak"}


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

        extract_resp = client.post(
            f"/api/projects/{project_id}/characters/extract",
            json={"auto_apply_to_character_map": False},
        )
        assert extract_resp.status_code == 200
        payload = extract_resp.json()
        assert payload["project_id"] == project_id
        assert payload["status"] == "complete"
        assert payload["candidate_count"] == len(payload["candidates"]) == 2
        names = {entry["name"] for entry in payload["candidates"]}
        assert names == {"Aria", "Nora"}
        assert all(entry["source"] == "auto" for entry in payload["candidates"])
        assert all(0.35 <= entry["confidence"] <= 0.99 for entry in payload["candidates"])
        assert payload["proposal_count"] == 2
        assert payload["extraction_batch_id"]
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

        proposals_resp = client.get(f"/api/projects/{project_id}/characters/proposals")
        assert proposals_resp.status_code == 200
        proposals_payload = proposals_resp.json()
        assert proposals_payload["proposal_count"] == 2
        proposal_names = {entry["name"] for entry in proposals_payload["proposals"]}
        assert proposal_names == {"Aria", "Nora"}

        character_map_resp = client.get(f"/api/projects/{project_id}/characters")
        assert character_map_resp.status_code == 200
        character_rows = character_map_resp.json()["characters"]
        assert len(character_rows) == 1
        assert character_rows[0]["name"] == "Mira"


def test_integration_character_auto_extraction_repeat_keeps_proposals_populated() -> None:
    with TestClient(app) as client:
        project_id = _create_project_with_ingested_text(client, "Auto Extraction Repeat")

        first_extract_resp = client.post(
            f"/api/projects/{project_id}/characters/extract",
            json={"auto_apply_to_character_map": False},
        )
        assert first_extract_resp.status_code == 200
        first_payload = first_extract_resp.json()
        assert first_payload["proposal_count"] > 0
        first_names = {entry["name"] for entry in first_payload["candidates"]}

        second_extract_resp = client.post(
            f"/api/projects/{project_id}/characters/extract",
            json={"auto_apply_to_character_map": False},
        )
        assert second_extract_resp.status_code == 200
        second_payload = second_extract_resp.json()
        assert second_payload["proposal_count"] > 0
        second_names = {entry["name"] for entry in second_payload["candidates"]}
        assert second_names == first_names

        proposals_resp = client.get(f"/api/projects/{project_id}/characters/proposals")
        assert proposals_resp.status_code == 200
        proposals_payload = proposals_resp.json()
        assert proposals_payload["proposal_count"] == len(first_names)
        assert {entry["name"] for entry in proposals_payload["proposals"]} == first_names


def test_integration_character_auto_extraction_auto_applies_strong_candidates_by_default() -> None:
    with TestClient(app) as client:
        project_id = _create_project_with_ingested_text(client, "Auto Extraction Auto Apply")

        extract_resp = client.post(f"/api/projects/{project_id}/characters/extract")
        assert extract_resp.status_code == 200
        payload = extract_resp.json()
        assert payload["auto_applied_count"] >= 1

        character_map_resp = client.get(f"/api/projects/{project_id}/characters")
        assert character_map_resp.status_code == 200
        names = {entry["name"] for entry in character_map_resp.json()["characters"]}
        assert {"Aria", "Nora"} & names


def test_integration_character_auto_extraction_uses_llm_first_pipeline(monkeypatch) -> None:
    def _fake_llm_first(
        *,
        session,  # noqa: ARG001
        project,  # noqa: ARG001
        project_id,  # noqa: ARG001
        chapter_rows,  # noqa: ARG001
        existing_name_keys,  # noqa: ARG001
        config,  # noqa: ARG001
    ):
        raw_payloads = [
            {
                "name": "Sunny",
                "verbalized_form": "Sunny",
                "gender": "unknown",
                "aliases": [],
                "notes": None,
                "source": "auto",
                "confidence": 0.87,
                "inferred_gender": "unknown",
                "inferred_confidence": 0.0,
                "inferred_source_trace": [],
                "source_trace": [
                    {
                        "kind": "llm_extraction",
                        "chapter_index": 1,
                        "span_start": 0,
                        "span_end": 5,
                        "excerpt": "Sunny watched the gate.",
                        "weight": 0.87,
                    }
                ],
            }
        ]
        return (raw_payloads, raw_payloads)

    monkeypatch.setattr(app_main, "_extract_character_candidates_llm_first", _fake_llm_first)
    monkeypatch.setattr(app_main, "_refine_character_payloads_with_llm", lambda **kwargs: kwargs["payloads"])

    with TestClient(app) as client:
        project_id = _create_project_with_ingested_text(client, "LLM First Extraction")
        extract_resp = client.post(f"/api/projects/{project_id}/characters/extract")
        assert extract_resp.status_code == 200
        payload = extract_resp.json()
        assert payload["candidate_count"] == 1
        assert payload["candidates"][0]["name"] == "Sunny"
        assert payload["proposal_count"] == 1
        assert payload["auto_applied_count"] == 1

        character_map_resp = client.get(f"/api/projects/{project_id}/characters")
        assert character_map_resp.status_code == 200
        assert {row["name"] for row in character_map_resp.json()["characters"]} == {"Sunny"}


def test_integration_character_auto_extraction_falls_back_when_llm_first_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(app_main, "_extract_character_candidates_llm_first", lambda **kwargs: None)

    def _fake_rule_extractor(chapters, known_names=None, min_confidence=0.35, max_candidates=250):  # noqa: ARG001
        return [
            CandidateEvidence(
                name="Aria",
                confidence=0.82,
                source_trace=[
                    CandidateSourceTrace(
                        kind="dialogue_attribution",
                        chapter_index=1,
                        span_start=0,
                        span_end=4,
                        excerpt="Aria said the gate is locked.",
                        weight=0.82,
                    )
                ],
            )
        ]

    monkeypatch.setattr(app_main, "extract_character_candidates_from_texts", _fake_rule_extractor)
    monkeypatch.setattr(app_main, "_refine_character_payloads_with_llm", lambda **kwargs: kwargs["payloads"])

    with TestClient(app) as client:
        project_id = _create_project_with_ingested_text(client, "Fallback Extraction")
        extract_resp = client.post(
            f"/api/projects/{project_id}/characters/extract",
            json={"auto_apply_to_character_map": False},
        )
        assert extract_resp.status_code == 200
        payload = extract_resp.json()
        assert payload["candidate_count"] == 1
        assert payload["candidates"][0]["name"] == "Aria"
        assert payload["proposal_count"] == 1
        assert payload["auto_applied_count"] == 0


def test_integration_character_extraction_job_lifecycle_completes(monkeypatch) -> None:
    def _run_inline(job_id: str):
        app_main.run_character_extraction_job_by_id(job_id)
        return ("thread", None)

    monkeypatch.setattr(app_main, "_dispatch_character_extraction_job", _run_inline)

    with TestClient(app) as client:
        project_id = _create_project_with_ingested_text(client, "Async Extraction Job")
        start_resp = client.post(
            f"/api/projects/{project_id}/characters/extract/jobs",
            json={"auto_apply_to_character_map": False},
        )
        assert start_resp.status_code == 202
        start_payload = start_resp.json()
        assert start_payload["project_id"] == project_id
        assert start_payload["job_id"]
        assert start_payload["executor_name"] == "thread"

        status_resp = client.get(
            f"/api/projects/{project_id}/characters/extract/jobs/{start_payload['job_id']}",
        )
        assert status_resp.status_code == 200
        status_payload = status_resp.json()
        assert status_payload["status"] == "completed"
        assert status_payload["progress"] == 100
        assert status_payload["result"] is not None
        assert status_payload["result"]["candidate_count"] >= 1
        assert status_payload["result"]["proposal_count"] >= 1


def test_integration_character_extraction_job_status_not_found() -> None:
    with TestClient(app) as client:
        project_id = _create_project_with_ingested_text(client, "Async Extraction Missing Job")
        status_resp = client.get(
            f"/api/projects/{project_id}/characters/extract/jobs/not-a-real-job-id",
        )
        assert status_resp.status_code == 404
        assert status_resp.json()["detail"] == "Character extraction job not found."


def test_integration_character_auto_extraction_rejects_empty_chapters() -> None:
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "No Chapters Project"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        extract_resp = client.post(f"/api/projects/{project_id}/characters/extract")
        assert extract_resp.status_code == 400
        assert extract_resp.json()["detail"] == "No chapters available for character auto-extraction."


def test_integration_character_proposal_review_approve_moves_into_character_map() -> None:
    with TestClient(app) as client:
        project_id = _create_project_with_ingested_text(client, "Proposal Review Approve")

        extract_resp = client.post(
            f"/api/projects/{project_id}/characters/extract",
            json={"auto_apply_to_character_map": False},
        )
        assert extract_resp.status_code == 200
        extract_payload = extract_resp.json()
        assert extract_payload["proposal_count"] > 0

        proposals_resp = client.get(f"/api/projects/{project_id}/characters/proposals")
        assert proposals_resp.status_code == 200
        proposals_payload = proposals_resp.json()
        assert proposals_payload["proposal_count"] > 0
        approve_id = proposals_payload["proposals"][0]["id"]

        review_resp = client.post(
            f"/api/projects/{project_id}/characters/proposals/review",
            json={"approve_ids": [approve_id], "reject_ids": [], "reviewed_by": "test-suite"},
        )
        assert review_resp.status_code == 200
        review_payload = review_resp.json()
        assert review_payload["approved_count"] == 1
        assert review_payload["rejected_count"] == 0
        assert review_payload["character_map_finalized"] is False

        character_map_resp = client.get(f"/api/projects/{project_id}/characters")
        assert character_map_resp.status_code == 200
        assert len(character_map_resp.json()["characters"]) == 1

        proposals_after_resp = client.get(f"/api/projects/{project_id}/characters/proposals")
        assert proposals_after_resp.status_code == 200
        assert proposals_after_resp.json()["proposal_count"] == max(proposals_payload["proposal_count"] - 1, 0)


def test_integration_character_proposal_review_reject_keeps_character_map_unchanged() -> None:
    with TestClient(app) as client:
        project_id = _create_project_with_ingested_text(client, "Proposal Review Reject")

        extract_resp = client.post(
            f"/api/projects/{project_id}/characters/extract",
            json={"auto_apply_to_character_map": False},
        )
        assert extract_resp.status_code == 200
        proposals_resp = client.get(f"/api/projects/{project_id}/characters/proposals")
        assert proposals_resp.status_code == 200
        proposals_payload = proposals_resp.json()
        assert proposals_payload["proposal_count"] > 0
        reject_id = proposals_payload["proposals"][0]["id"]

        review_resp = client.post(
            f"/api/projects/{project_id}/characters/proposals/review",
            json={"approve_ids": [], "reject_ids": [reject_id]},
        )
        assert review_resp.status_code == 200
        review_payload = review_resp.json()
        assert review_payload["approved_count"] == 0
        assert review_payload["rejected_count"] == 1
        assert review_payload["characters"] == []

        character_map_resp = client.get(f"/api/projects/{project_id}/characters")
        assert character_map_resp.status_code == 200
        assert character_map_resp.json()["characters"] == []

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


def test_unit_merge_character_candidates_keeps_manual_gender_over_auto() -> None:
    merged = merge_character_candidates(
        [
            {
                "name": "Kira",
                "verbalized_form": "Kira",
                "gender": "unknown",
                "aliases": [],
                "notes": "manual entry",
                "source": "manual",
                "confidence": 1.0,
                "source_trace": [],
            },
            {
                "name": "kira",
                "verbalized_form": "Kira",
                "gender": "female",
                "aliases": [],
                "notes": "auto sample",
                "source": "auto",
                "confidence": 0.8,
                "source_trace": [],
            },
        ]
    )

    assert len(merged) == 1
    assert merged[0]["name"] == "Kira"
    assert merged[0]["gender"] == "unknown"
    assert merged[0]["source"] == "merged:auto|user_import"


def test_unit_merge_character_candidates_order_does_not_change_manual_authority() -> None:
    merged = merge_character_candidates(
        [
            {
                "name": "Kira",
                "verbalized_form": "Kira",
                "gender": "female",
                "aliases": [],
                "notes": "auto sample",
                "source": "auto",
                "confidence": 0.8,
                "source_trace": [],
            },
            {
                "name": "kira",
                "verbalized_form": "Kira",
                "gender": "unknown",
                "aliases": [],
                "notes": "manual entry",
                "source": "manual",
                "confidence": 1.0,
                "source_trace": [],
            },
        ]
    )

    assert len(merged) == 1
    assert merged[0]["gender"] == "unknown"
    assert merged[0]["source"] == "merged:auto|user_import"


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
        **_: object,
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
        **_: object,
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


def test_integration_character_merge_candidates_reports_ambiguous_alias_collision_warning() -> None:
    with TestClient(app) as client:
        project_id = _create_project_with_ingested_text(client, "Merge Candidate Collision Warning")

        existing_import = client.post(
            f"/api/projects/{project_id}/characters/import",
            files={
                "file": (
                    "characters.json",
                    io.BytesIO(
                        b'{'
                        b'"Kai":{"verbalized_form":"Kai","gender":"male","aliases":["Captain","K."],"source":"manual","confidence":1.0},'
                        b'"Lio":{"verbalized_form":"Lio","gender":"female","aliases":["captain","A."],"source":"manual","confidence":1.0}'
                        b'}'
                    ),
                    "application/json",
                )
            },
        )
        assert existing_import.status_code == 200

        merged_resp = client.post(
            f"/api/projects/{project_id}/characters/merged-candidates",
            json={"include_auto": False},
        )
        assert merged_resp.status_code == 200

        merged_payload = merged_resp.json()
        assert merged_payload["status"] == "complete"
        warnings = merged_payload.get("warnings", [])
        assert isinstance(warnings, list)
        assert len(warnings) == 1

        warning = warnings[0]
        assert warning["type"] == "ambiguous_alias_collision"
        assert warning["source"] == "characters.merged-candidates"
        assert warning["alias"].lower() == "captain"
        assert set(warning["canonical_names"]) == {"Kai", "Lio"}


def test_integration_character_auto_extraction_reports_low_confidence_warning(monkeypatch) -> None:
    def _fake_extract_character_candidates_from_texts(
        _: object,
        known_names: set[str] | None = None,  # noqa: ARG001
        **__: object,
    ) -> list[CandidateEvidence]:
        return [
            CandidateEvidence(
                name="Mira",
                confidence=0.58,
                source_trace=[
                    CandidateSourceTrace(
                        kind="dialogue_attribution",
                        chapter_index=1,
                        span_start=0,
                        span_end=4,
                        excerpt="Mira said.",
                        weight=0.6,
                    )
                ],
            ),
            CandidateEvidence(
                name="Jalen",
                confidence=0.82,
                source_trace=[
                    CandidateSourceTrace(
                        kind="dialogue_attribution",
                        chapter_index=1,
                        span_start=20,
                        span_end=25,
                        excerpt="Jalen shouted.",
                        weight=1.0,
                    )
                ],
            ),
        ]

    monkeypatch.setattr(app_main, "extract_character_candidates_from_texts", _fake_extract_character_candidates_from_texts)

    with TestClient(app) as client:
        project_id = _create_project_with_ingested_text(client, "Auto Extract Low Confidence Warning")

        extract_resp = client.post(f"/api/projects/{project_id}/characters/extract")
        assert extract_resp.status_code == 200
        payload = extract_resp.json()
        warnings = payload.get("warnings", [])
        assert any(
            item["type"] == "low_confidence_character_candidate"
            and item["alias"] == "Mira"
            and item["source"] == "characters.extract"
            for item in warnings
        )


def test_integration_character_auto_extraction_reports_duplicate_canonical_candidates_warning(monkeypatch) -> None:
    def _fake_extract_character_candidates_from_texts(
        _: object,
        known_names: set[str] | None = None,  # noqa: ARG001
        **__: object,
    ) -> list[CandidateEvidence]:
        return [
            CandidateEvidence(
                name="Mira",
                confidence=0.91,
                source_trace=[
                    CandidateSourceTrace(
                        kind="dialogue_attribution",
                        chapter_index=1,
                        span_start=0,
                        span_end=4,
                        excerpt="Mira said.",
                        weight=1.0,
                    )
                ],
            ),
            CandidateEvidence(
                name="mira",
                confidence=0.82,
                source_trace=[
                    CandidateSourceTrace(
                        kind="narrative_attribution",
                        chapter_index=2,
                        span_start=20,
                        span_end=25,
                        excerpt="Mira appeared.",
                        weight=0.8,
                    )
                ],
            ),
        ]

    monkeypatch.setattr(app_main, "extract_character_candidates_from_texts", _fake_extract_character_candidates_from_texts)

    with TestClient(app) as client:
        project_id = _create_project_with_ingested_text(client, "Auto Extract Duplicate Canonical Warning")

        extract_resp = client.post(f"/api/projects/{project_id}/characters/extract")
        assert extract_resp.status_code == 200
        payload = extract_resp.json()
        warnings = payload.get("warnings", [])

        duplicate_warnings = [
            item
            for item in warnings
            if item["type"] == "duplicate_canonical_candidates"
            and item["source"] == "characters.extract"
        ]
        assert len(duplicate_warnings) == 1
        warning = duplicate_warnings[0]
        assert warning["alias"] == "Mira"
        assert set(warning["canonical_names"]) == {"Mira", "mira"}
        assert warning["message"].startswith("Duplicate canonical candidate 'Mira' appeared")


def test_integration_character_merge_candidates_reports_low_confidence_warning(monkeypatch) -> None:
    def _fake_extract_character_candidates_from_texts(
        _: object,
        known_names: set[str] | None = None,  # noqa: ARG001
        **__: object,
    ) -> list[CandidateEvidence]:
        return [
            CandidateEvidence(
                name="Mira",
                confidence=0.49,
                source_trace=[
                    CandidateSourceTrace(
                        kind="narrative_attribution",
                        chapter_index=1,
                        span_start=2,
                        span_end=6,
                        excerpt="Looked and smiled.",
                        weight=0.6,
                    )
                ],
            ),
        ]

    monkeypatch.setattr(app_main, "extract_character_candidates_from_texts", _fake_extract_character_candidates_from_texts)

    with TestClient(app) as client:
        project_id = _create_project_with_ingested_text(client, "Merged Candidates Low Confidence Warning")

        merged_resp = client.post(
            f"/api/projects/{project_id}/characters/merged-candidates",
            json={"include_auto": True},
        )
        assert merged_resp.status_code == 200
        merged_payload = merged_resp.json()
        warnings = merged_payload.get("warnings", [])
        assert any(
            item["type"] == "low_confidence_character_candidate"
            and item["alias"] == "Mira"
            and item["source"] == "characters.merged-candidates"
            for item in warnings
        )
