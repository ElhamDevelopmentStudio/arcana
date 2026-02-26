from app.chart_contracts import build_polarity_graph_contract
from app.schemas import PolarityGraphResponse


def test_build_polarity_graph_contract_from_export_payload() -> None:
    academic_reports = {
        "rolling_window_emotional_curves": {
            "window_size": 5,
            "valence_curve": [
                {
                    "position": 1,
                    "chapter_id": 1,
                    "segment_index": 1,
                    "segment_id": "1-001",
                    "rolling_mean_valence": -0.12,
                    "rolling_mean_intensity": 0.47,
                },
                {
                    "position": 2,
                    "chapter_id": 1,
                    "segment_index": 2,
                    "segment_id": "1-002",
                    "rolling_mean_valence": 0.08,
                    "rolling_mean_intensity": 0.55,
                },
            ],
        },
        "time_series": {
            "volatility_markers": [
                {
                    "position": 2,
                    "from_segment_id": "1-001",
                    "segment_id": "1-002",
                    "volatility_index": 0.26,
                    "level": "moderate",
                    "evidence": {
                        "valence_delta": 0.12,
                        "intensity_delta": 0.08,
                        "tension_delta": -0.01,
                        "dominance_delta": 0.10,
                    },
                    "reasons": ["emotion pivot", "volume shift"],
                    "from_raw_tags": {"tension_value": 0.18},
                    "to_raw_tags": {"tension_value": 0.19},
                }
            ]
        },
    }

    contract = build_polarity_graph_contract(academic_reports)

    assert isinstance(contract, PolarityGraphResponse)
    assert contract.metric_id == "rolling_emotional_polarity"
    assert contract.metric_label == "Rolling emotional polarity"
    assert contract.source_path == ["rolling_window_emotional_curves", "valence_curve"]
    assert contract.value_key == "rolling_mean_valence"
    assert contract.points[0].position == 1
    assert contract.points[0].rolling_mean_valence == -0.12
    assert contract.points[0].rolling_mean_intensity == 0.47
    assert contract.volatility_markers[0].segment_id == "1-002"
    assert contract.volatility_markers[0].chapter_id == 1
    assert contract.volatility_markers[0].segment_index == 2
    assert contract.volatility_markers[0].level == "moderate"
    assert contract.volatility_markers[0].triggers == ["emotion pivot", "volume shift"]
    assert contract.volatility_markers[0].from_tension == 0.18
    assert contract.volatility_markers[0].to_tension == 0.19
    assert contract.metadata["rolling_window_size"] == 5
    assert contract.metadata["volatility_markers_count"] == 1


def test_build_polarity_graph_contract_requires_rolling_window_payload() -> None:
    try:
        build_polarity_graph_contract({"smoothed_tension_curve": {}})
    except ValueError as exc:
        assert "rolling_window_emotional_curves is missing" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing rolling window payload")
