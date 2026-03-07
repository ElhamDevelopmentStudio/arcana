# Visualization Chart Contracts

Reference sources:
- [SRS.md](/Users/elhamdev/work/nipe/SRS.md) section `5. Visualization Requirements` and `4.10.2 Tension Modeling Outputs`
- [SRS_Expanded_Implementation_Checklist.md](/Users/elhamdev/work/nipe/SRS_Expanded_Implementation_Checklist.md) item `VR-001`

Purpose:
- Define the canonical contract for tension graph API payloads before implementing
  transport endpoints.

## VR-001 Tension Graph Contract

- contract_id: `TENSION_GRAPH_V1`
- metric_id: `smoothed_tension_curve`
- metric_label: `Smoothed tension curve`
- source_path:
  - `smoothed_tension_curve.tension_curve`
- value_key: `smoothed_tension`
- point_fields:
  - `position` (int, required, >= 1)
  - `smoothed_tension` (float, required, 0.0..1.0)
  - `chapter_id` (int, optional)
  - `segment_index` (int, optional)
  - `segment_id` (string, optional)
- peak_overlay_source:
  - payload_path: `tension_peak_markers.peaks`
  - required_fields: `position, severity, prominence, tension_value, neighbors.previous_tension, neighbors.next_tension`
- plateau_overlay_source:
  - payload_path: `tension_plateau_regions.regions`
  - required_fields: `start_position, end_position, length, segment_count, average_tension, tension_value_range.min, tension_value_range.max, tension_value_range.delta`

Example payload:

```json
{
  "metric_id": "smoothed_tension_curve",
  "metric_label": "Smoothed tension curve",
  "source_path": ["smoothed_tension_curve", "tension_curve"],
  "value_key": "smoothed_tension",
  "metadata": {
    "smoothed_window_size": 6,
    "peak_prominence_thresholds": {
      "major": 0.18,
      "minor": 0.10
    },
    "plateau_region_params": {
      "flatness_tolerance": 0.05,
      "min_region_length": 3
    }
  },
  "points": [
    {
      "position": 1,
      "smoothed_tension": 0.33,
      "chapter_id": 1,
      "segment_index": 1,
      "segment_id": "1-001"
    },
    {
      "position": 2,
      "smoothed_tension": 0.41,
      "chapter_id": 1,
      "segment_index": 2,
      "segment_id": "1-002"
    }
  ],
  "peak_markers": [
    {
      "position": 8,
      "segment_id": "2-005",
      "chapter_id": 2,
      "segment_index": 5,
      "peak_type": "tension_peak",
      "severity": "major",
      "prominence": 0.19,
      "previous_tension": 0.47,
      "next_tension": 0.45,
      "tension_value": 0.66
    }
  ],
  "plateau_regions": [
    {
      "region_type": "tension_plateau",
      "start_position": 12,
      "end_position": 18,
      "length": 7,
      "segment_count": 7,
      "segment_ids": ["3-012", "3-013", "3-014", "3-015", "3-016", "3-017", "3-018"],
      "segment_indices": [12, 13, 14, 15, 16, 17, 18],
      "chapter_ids": [3],
      "average_tension": 0.53,
      "tension_value_range": {
        "min": 0.49,
        "max": 0.56,
        "delta": 0.07
      }
    }
  ]
}
```
