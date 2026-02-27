from __future__ import annotations

import json
from pathlib import Path

from app.services.character_extraction import extract_character_candidates_from_texts


def test_unit_character_extraction_v2_detects_narrative_only_mentions() -> None:
    chapters = [
        "Chapter 1\nSunny walked through the market. Sunny looked over his shoulder.",
        "Chapter 2\nNephis moved toward the door while Sunny waited.",
    ]

    candidates = extract_character_candidates_from_texts(chapters)
    names = {candidate.name for candidate in candidates}
    assert "Sunny" in names
    assert "Nephis" in names


def test_unit_character_extraction_v2_filters_obvious_non_character_terms() -> None:
    chapters = [
        "Chapter 1\nAuthority increased. Update List opened. Training Sneakers were equipped.",
        "Chapter 2\nSynchronization Complete. Updated Features displayed.",
    ]

    candidates = extract_character_candidates_from_texts(chapters)
    names = {candidate.name for candidate in candidates}
    assert "Authority" not in names
    assert "Update List" not in names
    assert "Training Sneakers" not in names
    assert "Synchronization Complete" not in names


def test_unit_character_extraction_v2_suppresses_common_non_person_capitalized_tokens() -> None:
    chapters = [
        "Sunny stood before the Academy gates. Actually, he wanted to leave.",
        "Acting calm, Sunny walked away from the Academy.",
    ]

    candidates = extract_character_candidates_from_texts(chapters)
    names = {candidate.name for candidate in candidates}
    assert "Sunny" in names
    assert "Academy" not in names
    assert "Actually" not in names
    assert "Acting" not in names


def test_unit_character_extraction_v2_ignores_system_field_labels_and_extracts_name_field_value() -> None:
    chapters = [
        (
            "Name: Sunny\n"
            "Aspect Rank: Divine\n"
            "Aspect Description: Shadow Lord\n"
            "Attributes: Fated, Shadow Slave\n"
            "Flaw: True Name disclosed.\n"
        )
    ]

    candidates = extract_character_candidates_from_texts(chapters)
    names = {candidate.name for candidate in candidates}
    assert "Sunny" in names
    assert "Name" not in names
    assert "Aspect Rank" not in names
    assert "Aspect Description" not in names
    assert "Attributes" not in names
    assert "Flaw" not in names


def test_regression_character_extraction_gold_fixture_recall_gate() -> None:
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "character_extraction_gold_en.json"
    fixture_payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    chapters = fixture_payload["chapters"]
    expected_names = {str(name).strip().lower() for name in fixture_payload["expected_names"]}
    allowed_false_positive_count = int(fixture_payload["allowed_false_positive_count"])

    candidates = extract_character_candidates_from_texts(chapters, min_confidence=0.35)
    predicted_names = {candidate.name.strip().lower() for candidate in candidates}

    matched = expected_names & predicted_names
    recall = (len(matched) / len(expected_names)) if expected_names else 1.0
    false_positive_count = len(predicted_names - expected_names)

    assert recall >= 0.65
    assert false_positive_count <= allowed_false_positive_count
