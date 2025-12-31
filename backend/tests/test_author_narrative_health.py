from datetime import datetime, timezone
from types import SimpleNamespace

from app.schemas import NarrativeHealthReport
from app.services.export import _build_author_narrative_health_report, _build_monotony_risk_findings


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


def test_unit_narrative_health_report_includes_monotony_findings() -> None:
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
    findings = _build_monotony_risk_findings(
        segments=segments,
        smoothed_tension_curve=tension_curve,
    )

    project = SimpleNamespace(id=101, title="Monotony Project", selected_mode="author", selected_modes=["author"])
    run = SimpleNamespace(id=202, status="completed")
    report = _build_author_narrative_health_report(
        project=project,
        run=run,
        generated_at=datetime(2026, 2, 25, tzinfo=timezone.utc),
        segment_count=len(segments),
        monotony_findings=findings,
    )
    parsed_report = NarrativeHealthReport.model_validate(report)

    assert parsed_report.project_reference["project_id"] == 101
    assert parsed_report.run_reference["run_id"] == 202
    requirement_lookup = {entry.requirement_id: entry for entry in parsed_report.requirements}
    assert requirement_lookup["ADR-002"].status == "implemented"
    assert len(requirement_lookup["ADR-002"].findings) == 1
    assert parsed_report.findings[0].requirement_id == "ADR-002"
    assert parsed_report.findings[0].severity == findings[0]["severity"]
