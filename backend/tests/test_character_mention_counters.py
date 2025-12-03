import os
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

os.environ["DATABASE_URL"] = "sqlite:///./test_nipc_character_mentions.db"

from app.config import clear_settings_cache
from app.database import init_db, reset_engine
from app.main import app
from app.models import Chapter, Character
from app.services.character_analytics import (
    build_character_last_appearance_chapter_indices,
    build_character_first_appearance_chapter_indices,
    build_character_mentions_per_1000_words,
    build_character_mentions_by_chapter,
)


def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipc_character_mentions.db")
    if db_file.exists():
        db_file.unlink()


def _chapter(chapter_index: int, text: str, project_id: int = 1) -> Chapter:
    return Chapter(
        project_id=project_id,
        chapter_index=chapter_index,
        chapter_internal_id=f"ch-{chapter_index:04d}",
        chapter_title=f"Chapter {chapter_index}",
        raw_text=text,
        original_text_snapshot=text,
        normalized_text=text,
        normalized_text_snapshot=text,
        original_to_normalized_offset_map=[],
    )


def test_unit_character_mentions_by_chapter_counts_canonical_and_alias_matches() -> None:
    chapters = [
        _chapter(1, '"Sunny looked around," Sunny said. Captain nodded.'),
        _chapter(2, "Lio entered. Captain was praised."),
    ]

    characters = [
        Character(
            name="Sunny",
            verbalized_form="Sunny",
            gender="male",
            aliases=["Captain"],
            notes=None,
            source="manual",
            confidence=1.0,
        ),
        Character(
            name="Lio",
            verbalized_form="Lio",
            gender="female",
            aliases=[],
            notes=None,
            source="manual",
            confidence=1.0,
        ),
    ]

    results = build_character_mentions_by_chapter(chapters=chapters, characters=characters)

    assert len(results) == 2
    assert results[0].chapter_index == 1
    assert results[0].mention_counts["Sunny"] == 3
    assert results[0].mention_counts["Lio"] == 0
    assert results[1].mention_counts["Sunny"] == 1
    assert results[1].mention_counts["Lio"] == 1


def test_unit_character_mentions_by_chapter_ignores_ambiguous_alias_matches() -> None:
    chapters = [
        _chapter(1, "Kai spoke. Captain returned with the crew."),
    ]

    characters = [
        Character(
            name="Kai",
            verbalized_form="Kai",
            gender="male",
            aliases=["Captain"],
            notes=None,
            source="manual",
            confidence=1.0,
        ),
        Character(
            name="Lio",
            verbalized_form="Lio",
            gender="female",
            aliases=["captain"],
            notes=None,
            source="manual",
            confidence=1.0,
        ),
    ]

    results = build_character_mentions_by_chapter(chapters=chapters, characters=characters)
    assert len(results) == 1
    assert results[0].mention_counts["Kai"] == 1
    assert results[0].mention_counts["Lio"] == 0


def test_unit_character_first_appearance_chapter_indices() -> None:
    chapters = [
        _chapter(1, "Sunny said hello. Nobody was not here."),
        _chapter(2, "Sunny and Captain entered."),
        _chapter(3, "Nephis appeared. Lio replied."),
    ]

    characters = [
        Character(
            name="Sunny",
            verbalized_form="Sunny",
            gender="female",
            aliases=["Sun"],
            notes=None,
            source="manual",
            confidence=1.0,
        ),
        Character(
            name="Lio",
            verbalized_form="Lio",
            gender="male",
            aliases=[],
            notes=None,
            source="manual",
            confidence=1.0,
        ),
        Character(
            name="Captain",
            verbalized_form="Captain",
            gender="male",
            aliases=["Cap"],
            notes=None,
            source="manual",
            confidence=1.0,
        ),
        Character(
            name="Nephis",
            verbalized_form="Nephis",
            gender="female",
            aliases=[],
            notes=None,
            source="manual",
            confidence=1.0,
        ),
        Character(
            name="Ghost",
            verbalized_form="Ghost",
            gender="unknown",
            aliases=[],
            notes=None,
            source="manual",
            confidence=1.0,
        ),
    ]

    chapter_counts = build_character_mentions_by_chapter(chapters=chapters, characters=characters)
    first_appearance = build_character_first_appearance_chapter_indices(chapter_counts)

    assert first_appearance["Sunny"] == 1
    assert first_appearance["Lio"] == 3
    assert first_appearance["Nephis"] == 3
    assert first_appearance["Captain"] == 2
    assert first_appearance["Ghost"] is None


def test_unit_character_last_appearance_chapter_indices() -> None:
    chapters = [
        _chapter(1, "Sunny said hello and Captain entered."),
        _chapter(2, "Sunny and Nephis argued while Captain replied."),
        _chapter(3, "Nephis stood in silence."),
    ]

    characters = [
        Character(
            name="Sunny",
            verbalized_form="Sunny",
            gender="female",
            aliases=["Sun"],
            notes=None,
            source="manual",
            confidence=1.0,
        ),
        Character(
            name="Lio",
            verbalized_form="Lio",
            gender="male",
            aliases=[],
            notes=None,
            source="manual",
            confidence=1.0,
        ),
        Character(
            name="Captain",
            verbalized_form="Captain",
            gender="male",
            aliases=["Cap"],
            notes=None,
            source="manual",
            confidence=1.0,
        ),
        Character(
            name="Nephis",
            verbalized_form="Nephis",
            gender="female",
            aliases=[],
            notes=None,
            source="manual",
            confidence=1.0,
        ),
        Character(
            name="Ghost",
            verbalized_form="Ghost",
            gender="unknown",
            aliases=[],
            notes=None,
            source="manual",
            confidence=1.0,
        ),
    ]

    chapter_counts = build_character_mentions_by_chapter(chapters=chapters, characters=characters)
    last_appearance = build_character_last_appearance_chapter_indices(chapter_counts)

    assert last_appearance["Sunny"] == 2
    assert last_appearance["Captain"] == 2
    assert last_appearance["Nephis"] == 3
    assert last_appearance["Lio"] is None
    assert last_appearance["Ghost"] is None


def test_unit_character_mentions_per_1000_words() -> None:
    chapters = [
        _chapter(1, "Sunny and Captain walked slowly."),
        _chapter(2, "Nephis and Lio arrived."),
        _chapter(3, "Sunny and Captain returned with Lio."),
    ]

    characters = [
        Character(
            name="Sunny",
            verbalized_form="Sunny",
            gender="female",
            aliases=["Sun"],
            notes=None,
            source="manual",
            confidence=1.0,
        ),
        Character(
            name="Lio",
            verbalized_form="Lio",
            gender="male",
            aliases=[],
            notes=None,
            source="manual",
            confidence=1.0,
        ),
        Character(
            name="Captain",
            verbalized_form="Captain",
            gender="male",
            aliases=["Cap"],
            notes=None,
            source="manual",
            confidence=1.0,
        ),
        Character(
            name="Nephis",
            verbalized_form="Nephis",
            gender="female",
            aliases=[],
            notes=None,
            source="manual",
            confidence=1.0,
        ),
        Character(
            name="Ghost",
            verbalized_form="Ghost",
            gender="male",
            aliases=[],
            notes=None,
            source="manual",
            confidence=1.0,
        ),
    ]

    chapter_counts = build_character_mentions_by_chapter(chapters=chapters, characters=characters)
    mentions_per_1000_words = build_character_mentions_per_1000_words(chapter_counts, chapters)

    expected_total_words = 15
    assert mentions_per_1000_words["Sunny"] == pytest.approx((2 * 1000) / expected_total_words, rel=1e-9)
    assert mentions_per_1000_words["Captain"] == pytest.approx((2 * 1000) / expected_total_words, rel=1e-9)
    assert mentions_per_1000_words["Lio"] == pytest.approx((2 * 1000) / expected_total_words, rel=1e-9)
    assert mentions_per_1000_words["Nephis"] == pytest.approx((1 * 1000) / expected_total_words, rel=1e-9)
    assert mentions_per_1000_words["Ghost"] == 0.0


def test_integration_pipeline_run_stores_per_chapter_mention_counts() -> None:
    sample_text = (
        "Chapter 1\n"
        '"Sunny spoke, "Sunny said hello."\n\n'
        "Nephis smiled and then Sunny left."
    )
    with TestClient(app) as client:
        project_resp = client.post("/api/projects", json={"title": "Mention Counter Integration"})
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        ingest_resp = client.post(
            f"/api/projects/{project_id}/ingest/txt",
            files={"file": ("sample.txt", sample_text.encode("utf-8"), "text/plain")},
        )
        assert ingest_resp.status_code == 200

        import_resp = client.post(
            f"/api/projects/{project_id}/characters/import",
            files={
                "file": (
                    "characters.json",
                    b'{"Sunny":{"verbalized_form":"Sunny","gender":"female","aliases":["Sun"]},"Nephis":{"verbalized_form":"Nephis","gender":"female"}}',
                    "application/json",
                )
            },
        )
        assert import_resp.status_code == 200

        run_resp = client.post(
            f"/api/projects/{project_id}/runs",
            json={
                "max_segment_chars": 120,
                "llm_enabled": False,
                "provider_name": "openrouter",
                "max_calls_per_day": 2,
                "allow_unfinalized_character_map": True,
            },
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        detail_resp = client.get(f"/api/projects/{project_id}/runs/{run_id}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        counts = detail["config"]["character_mentions_by_chapter"]
        assert counts and isinstance(counts, list)
        assert counts[0]["chapter_index"] == 1
        assert counts[0]["mention_counts"]["Sunny"] == 3

        first_appearance = detail["config"]["character_first_appearance_chapter_index"]
        assert first_appearance == {"Nephis": 1, "Sunny": 1}

        last_appearance = detail["config"]["character_last_appearance_chapter_index"]
        assert last_appearance == {"Nephis": 1, "Sunny": 1}

        mentions_per_1000_words = detail["config"]["character_mentions_per_1000_words"]
        assert set(mentions_per_1000_words.keys()) == {"Nephis", "Sunny"}
