import json
from pathlib import Path

from app.services.export import (
    _build_chapter_level_character_dominance,
    _build_character_dominance_findings,
    _build_disappearing_character_findings,
    _build_dialogue_density_anomaly_findings,
    _build_emotional_monotony_findings,
    _build_monotony_risk_findings,
    _build_smoothed_tension_curve,
)


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _load_warning_fixture(filename: str) -> list[dict[str, object]]:
    fixture_path = FIXTURES_DIR / filename
    with fixture_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload


def test_warning_fixture_monotony_flatline_triggers_tension_risk_warning() -> None:
    segments = _load_warning_fixture("author_warning_monotony_flatline.json")
    smoothed_tension_curve = _build_smoothed_tension_curve(segments=segments, window_size=6)[
        "tension_curve"
    ]
    findings = _build_monotony_risk_findings(
        segments=segments,
        smoothed_tension_curve=smoothed_tension_curve,
    )

    assert any(finding["requirement_id"] == "ADR-002" for finding in findings)


def test_warning_fixture_emotional_monotony_triggers_repeated_tone_warning() -> None:
    segments = _load_warning_fixture("author_warning_emotional_monotony.json")
    findings = _build_emotional_monotony_findings(segments=segments)

    assert len(findings) == 1
    assert findings[0]["requirement_id"] == "ADR-002"
    assert findings[0]["trigger_metric"] == "repeated_tone_pattern"


def test_warning_fixture_character_dominance_triggers_imbalance_warning() -> None:
    segments = _load_warning_fixture("author_warning_character_dominance.json")
    chapter_level_summary = _build_chapter_level_character_dominance(segments=segments)
    findings = _build_character_dominance_findings(
        chapter_level_character_dominance=chapter_level_summary
    )

    assert any(finding["requirement_id"] == "ADR-003" for finding in findings)


def test_warning_fixture_disappearing_character_triggers_disappearance_warning() -> None:
    segments = _load_warning_fixture("author_warning_disappearing_character.json")
    findings = _build_disappearing_character_findings(segments=segments)

    assert any(finding["requirement_id"] == "ADR-005" for finding in findings)


def test_warning_fixture_dialogue_density_triggers_dialogue_anomaly_warning() -> None:
    segments = _load_warning_fixture("author_warning_dialogue_density.json")
    findings = _build_dialogue_density_anomaly_findings(segments=segments)

    assert any(finding["requirement_id"] == "ADR-006" for finding in findings)
