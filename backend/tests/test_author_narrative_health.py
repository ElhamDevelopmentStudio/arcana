from datetime import datetime, timezone
from types import SimpleNamespace

from app.schemas import NarrativeHealthReport
from app.services.export import (
    _build_author_narrative_health_report,
    _build_character_dominance_findings,
    _build_emotional_monotony_findings,
    _build_chapter_level_character_dominance,
    _build_monotony_risk_findings,
)


def _build_segments_for_test(
    values: list[tuple[float, float, float]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    segments: list[dict[str, object]] = []
    tension_curve: list[dict[str, object]] = []
    for index, (tension, valence, intensity) in enumerate(values, start=1):
        segments.append(
            {
                "chapter_id": 1,
                "segment_index": index,
                "segment_id": f"1-{index}",
                "emotion_valence": valence,
                "emotion_intensity": intensity,
                "emotion_primary_label": "neutral",
            }
        )
        tension_curve.append(
            {
                "position": index,
                "segment_id": f"1-{index}",
                "segment_index": index,
                "chapter_id": 1,
                "smoothed_tension": tension,
            }
        )
    return segments, tension_curve


def _build_segments_for_labels_test(
    values: list[tuple[str, float, float]],
) -> list[dict[str, object]]:
    segments: list[dict[str, object]] = []
    for index, (label, valence, intensity) in enumerate(values, start=1):
        segments.append(
            {
                "chapter_id": 1,
                "segment_index": index,
                "segment_id": f"1-{index}",
                "emotion_primary_label": label,
                "emotion_valence": valence,
                "emotion_intensity": intensity,
            }
        )
    return segments


def _build_segments_for_dominance_test(
    chapter_id: int,
    segments: list[tuple[str, float | None]],
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for index, (speaker, dominance) in enumerate(segments, start=1):
        result.append(
            {
                "chapter_id": chapter_id,
                "segment_index": index,
                "segment_id": f"{chapter_id}-{index}",
                "speaker": speaker,
                "speaker_id": index,
                "dominance_contribution": {"value": dominance},
            }
        )
    return result


def test_unit_build_character_dominance_findings_detects_over_dominant_character() -> None:
    segments = _build_segments_for_dominance_test(
        3,
        [
            ("Hero", 1.0),
            ("Hero", 1.0),
            ("Hero", 1.0),
            ("Narrator", 0.1),
            ("Hero", 1.0),
            ("Sidekick", 0.2),
            ("Narrator", 0.1),
            ("Hero", 1.0),
            ("Hero", 1.0),
            ("Hero", 1.0),
            ("Hero", 1.0),
            ("Hero", 1.0),
        ],
    )
    chapter_level_character_dominance = _build_chapter_level_character_dominance(
        segments=segments,
        top_characters_limit=3,
    )
    findings = _build_character_dominance_findings(chapter_level_character_dominance)

    assert len(findings) == 1
    finding = findings[0]
    assert finding["requirement_id"] == "ADR-003"
    assert finding["requirement_name"] == "character_imbalance_alerts"
    assert finding["location"]["start_chapter"] == 3
    assert finding["location"]["end_chapter"] == 3
    assert finding["trigger_metric"] == "character_dominance_outlier"
    assert finding["evidence_trace"]["top_character"] == "Hero"
    assert finding["evidence_trace"]["lead_share_gap"] > 0.4
    assert finding["severity"] > 0.7


def test_unit_build_character_dominance_findings_skips_balanced_dialogue() -> None:
    segments = _build_segments_for_dominance_test(
        3,
        [
            ("Hero", 1.0),
            ("Hero", 1.0),
            ("Sidekick", 1.0),
            ("Sidekick", 1.0),
            ("Hero", 1.0),
            ("Sidekick", 1.0),
            ("Narrator", 0.8),
            ("Narrator", 0.8),
        ],
    )
    chapter_level_character_dominance = _build_chapter_level_character_dominance(
        segments=segments,
        top_characters_limit=3,
    )
    findings = _build_character_dominance_findings(chapter_level_character_dominance)

    assert findings == []


def test_unit_build_monotony_risk_findings_detects_flatline_region() -> None:
    values = [
        (0.42, 0.02, 0.31),
        (0.44, 0.03, 0.30),
        (0.43, 0.01, 0.32),
        (0.41, 0.00, 0.31),
        (0.42, 0.04, 0.30),
        (0.43, 0.02, 0.33),
        (0.44, 0.03, 0.34),
        (0.42, 0.01, 0.29),
    ]
    segments, tension_curve = _build_segments_for_test(values)
    findings = _build_monotony_risk_findings(
        segments=segments,
        smoothed_tension_curve=tension_curve,
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding["requirement_id"] == "ADR-002"
    assert finding["requirement_name"] == "monotony_risk_detector"
    assert finding["location"]["start_segment"] == 1
    assert finding["location"]["end_segment"] == len(values)
    assert finding["trigger_metric"] == "low_tension_and_emotion_variance_window"
    assert finding["severity"] > 0.5
    assert finding["evidence_trace"]["window_length"] == len(values)
    assert finding["evidence_trace"]["tension_range"] < 0.06


def test_unit_build_emotional_monotony_findings_detects_repeated_tone_pattern() -> None:
    segments = _build_segments_for_labels_test(
        [
            ("calm", 0.06, 0.18),
            ("calm", 0.04, 0.20),
            ("calm", 0.05, 0.19),
            ("calm", 0.07, 0.22),
            ("calm", 0.03, 0.17),
            ("calm", 0.08, 0.21),
            ("calm", 0.06, 0.20),
            ("tense", 0.09, 0.18),
        ]
    )
    findings = _build_emotional_monotony_findings(segments)

    assert len(findings) == 1
    finding = findings[0]
    assert finding["requirement_id"] == "ADR-002"
    assert finding["trigger_metric"] == "repeated_tone_pattern"
    assert finding["location"]["start_segment"] == 1
    assert finding["location"]["end_segment"] == 8
    assert finding["evidence_trace"]["window_length"] == 8
    assert finding["evidence_trace"]["dominant_tone"] == "calm"
    assert finding["evidence_trace"]["dominant_tone_ratio"] >= 0.85


def test_unit_build_emotional_monotony_findings_rejects_varied_tones() -> None:
    segments = _build_segments_for_labels_test(
        [
            ("calm", 0.10, 0.10),
            ("tense", 0.60, 0.80),
            ("joy", 0.90, 0.90),
            ("sorrow", -0.70, 0.20),
            ("anger", -0.20, 0.80),
            ("joy", 0.70, 0.75),
            ("tense", 0.65, 0.70),
            ("calm", 0.20, 0.30),
        ]
    )
    findings = _build_emotional_monotony_findings(segments)
    assert findings == []


def test_unit_build_monotony_risk_findings_no_flatline_for_variable_series() -> None:
    values = [
        (0.12, -0.8, 0.10),
        (0.32, 0.40, 0.55),
        (0.71, -0.20, 0.80),
        (0.30, 0.55, 0.20),
        (0.88, -0.05, 0.90),
        (0.16, 0.10, 0.35),
        (0.64, -0.45, 0.72),
        (0.48, 0.35, 0.40),
    ]
    segments, tension_curve = _build_segments_for_test(values)
    findings = _build_monotony_risk_findings(
        segments=segments,
        smoothed_tension_curve=tension_curve,
    )
    assert findings == []


def test_unit_narrative_health_report_includes_emotional_monotony_findings() -> None:
    values = [
        (0.42, 0.02, 0.31),
        (0.44, 0.03, 0.30),
        (0.43, 0.01, 0.32),
        (0.41, 0.00, 0.31),
        (0.42, 0.04, 0.30),
        (0.43, 0.02, 0.33),
        (0.44, 0.03, 0.34),
    ]
    segments, tension_curve = _build_segments_for_test(values)
    monotony_findings = _build_monotony_risk_findings(
        segments=segments,
        smoothed_tension_curve=tension_curve,
    )
    emotional_findings = _build_emotional_monotony_findings(
        _build_segments_for_labels_test(
            [
                ("calm", 0.02, 0.31),
                ("calm", 0.03, 0.30),
                ("calm", 0.01, 0.32),
                ("calm", 0.00, 0.31),
                ("calm", 0.04, 0.30),
                ("calm", 0.02, 0.33),
                ("calm", 0.03, 0.34),
            ]
        )
    )

    project = SimpleNamespace(id=101, title="Monotony Project", selected_mode="author", selected_modes=["author"])
    run = SimpleNamespace(id=202, status="completed")
    report = _build_author_narrative_health_report(
        project=project,
        run=run,
        generated_at=datetime(2026, 2, 25, tzinfo=timezone.utc),
        segment_count=len(segments),
        monotony_findings=monotony_findings,
        emotional_monotony_findings=emotional_findings,
    )
    parsed_report = NarrativeHealthReport.model_validate(report)

    requirement_lookup = {entry.requirement_id: entry for entry in parsed_report.requirements}
    assert requirement_lookup["ADR-002"].status == "implemented"
    assert requirement_lookup["ADR-003"].status == "implemented"
    assert requirement_lookup["ADR-003"].finding_count == 0
    assert len(requirement_lookup["ADR-002"].findings) == 2
    assert len(requirement_lookup["ADR-003"].findings) == 0
    assert len(parsed_report.findings) == 2
    assert parsed_report.findings[0].requirement_id == "ADR-002"
    possible_severities = {monotony_findings[0]["severity"], emotional_findings[0]["severity"]}
    assert parsed_report.findings[0].severity in possible_severities
