from app.chart_contracts import build_tension_graph_contract
from app.schemas import TensionGraphContractResponse


def test_build_tension_graph_contract_from_export_payload() -> None:
    academic_reports = {
        "smoothed_tension_curve": {
            "window_size": 6,
            "tension_curve": [
                {
                    "position": 1,
                    "chapter_id": 1,
                    "segment_index": 1,
                    "segment_id": "1-001",
                    "smoothed_tension": 0.32,
                },
                {
                    "position": 2,
                    "chapter_id": 1,
                    "segment_index": 2,
                    "segment_id": "1-002",
                    "smoothed_tension": 0.37,
                },
            ],
        },
        "tension_peak_markers": {
            "peaks": [
                {
                    "position": 2,
                    "segment_id": "1-002",
                    "chapter_id": 1,
                    "segment_index": 2,
                    "peak_type": "tension_peak",
                    "severity": "major",
                    "prominence": 0.12,
                    "neighbors": {
                        "previous_tension": 0.23,
                        "next_tension": 0.27,
                    },
                    "tension_value": 0.35,
                }
            ],
        },
        "tension_plateau_regions": {
            "regions": [
                {
                    "region_type": "tension_plateau",
                    "start_position": 10,
                    "end_position": 12,
                    "length": 3,
                    "segment_count": 3,
                    "segment_ids": ["1-010", "1-011", "1-012"],
                    "segment_indices": [10, 11, 12],
                    "chapter_ids": [1],
                    "average_tension": 0.41,
                    "tension_value_range": {
                        "min": 0.39,
                        "max": 0.42,
                        "delta": 0.03,
                    },
                },
            ],
        },
    }

    contract = build_tension_graph_contract(academic_reports)

    assert isinstance(contract, TensionGraphContractResponse)
    assert contract.metric_id == "smoothed_tension_curve"
    assert contract.metric_label == "Smoothed tension curve"
    assert contract.source_path == ["smoothed_tension_curve", "tension_curve"]
    assert contract.value_key == "smoothed_tension"
    assert contract.points[0].position == 1
    assert contract.points[0].smoothed_tension == 0.32
    assert contract.peak_markers[0].severity == "major"
    assert contract.plateau_regions[0].region_type == "tension_plateau"
    assert contract.metadata["smoothed_window_size"] == 6
