from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.schemas import (
    TensionGraphContractResponse,
    TensionGraphPeakMarker,
    TensionGraphPlateauRegion,
    TensionGraphPoint,
    TensionGraphValueRange,
)

TENSION_GRAPH_METRIC_ID = "smoothed_tension_curve"
TENSION_GRAPH_METRIC_LABEL = "Smoothed tension curve"
TENSION_GRAPH_SOURCE_PATH = [TENSION_GRAPH_METRIC_ID, "tension_curve"]
TENSION_GRAPH_VALUE_KEY = "smoothed_tension"


def _coerce_tension_curve_points(
    value: object,
) -> list[TensionGraphPoint]:
    if not isinstance(value, list):
        return []

    points: list[TensionGraphPoint] = []
    for point in value:
        if not isinstance(point, dict):
            continue
        smoothed_tension = point.get(TENSION_GRAPH_VALUE_KEY)
        position = point.get("position")
        if smoothed_tension is None or position is None:
            continue
        points.append(
            TensionGraphPoint(
                position=int(position),
                smoothed_tension=float(smoothed_tension),
                chapter_id=point.get("chapter_id") if isinstance(point.get("chapter_id"), int) else None,
                segment_index=(
                    int(point.get("segment_index"))
                    if isinstance(point.get("segment_index"), int)
                    else None
                ),
                segment_id=(
                    str(point.get("segment_id")) if isinstance(point.get("segment_id"), str) else None
                ),
            )
        )
    return points


def _coerce_peak_markers(value: object) -> list[TensionGraphPeakMarker]:
    if not isinstance(value, dict):
        return []

    peaks = value.get("peaks")
    if not isinstance(peaks, list):
        return []

    result: list[TensionGraphPeakMarker] = []
    for marker in peaks:
        if not isinstance(marker, dict):
            continue
        neighbors = marker.get("neighbors")
        if not isinstance(neighbors, dict):
            continue
        previous_tension = neighbors.get("previous_tension")
        next_tension = neighbors.get("next_tension")
        if marker.get("tension_value") is None or previous_tension is None or next_tension is None:
            continue

        result.append(
            TensionGraphPeakMarker(
                position=marker.get("position"),
                segment_id=marker.get("segment_id") if isinstance(marker.get("segment_id"), str) else None,
                chapter_id=marker.get("chapter_id") if isinstance(marker.get("chapter_id"), int) else None,
                segment_index=(
                    int(marker.get("segment_index"))
                    if isinstance(marker.get("segment_index"), int)
                    else None
                ),
                peak_type=str(marker.get("peak_type")),
                severity=str(marker.get("severity")),
                prominence=float(marker.get("prominence")),
                previous_tension=float(previous_tension),
                next_tension=float(next_tension),
                tension_value=float(marker.get("tension_value")),
            )
        )
    return result


def _coerce_plateau_regions(value: object) -> list[TensionGraphPlateauRegion]:
    if not isinstance(value, dict):
        return []

    regions = value.get("regions")
    if not isinstance(regions, list):
        return []

    result: list[TensionGraphPlateauRegion] = []
    for region in regions:
        if not isinstance(region, dict):
            continue
        tension_value_range = region.get("tension_value_range")
        if not isinstance(tension_value_range, dict):
            continue

        segment_indices = region.get("segment_indices")
        segment_ids = region.get("segment_ids")
        chapter_ids = region.get("chapter_ids")
        result.append(
            TensionGraphPlateauRegion(
                region_type=str(region.get("region_type") or "tension_plateau"),
                start_position=region.get("start_position"),
                end_position=region.get("end_position"),
                length=int(region["length"]),
                segment_count=int(region["segment_count"]),
                segment_ids=[str(value_) for value_ in segment_ids] if isinstance(segment_ids, list) else [],
                segment_indices=[
                    int(value_) for value_ in segment_indices if isinstance(value_, int)
                ] if isinstance(segment_indices, list) else [],
                chapter_ids=[int(value_) for value_ in chapter_ids if isinstance(value_, int)] if isinstance(chapter_ids, list) else [],
                average_tension=float(region["average_tension"]),
                tension_value_range=TensionGraphValueRange(
                    min=float(tension_value_range["min"]),
                    max=float(tension_value_range["max"]),
                    delta=float(tension_value_range["delta"]),
                ),
            )
        )
    return result


def build_tension_graph_contract(
    academic_reports: Mapping[str, Any] | None,
) -> TensionGraphContractResponse:
    if academic_reports is None:
        raise ValueError("academic_reports is required to build tension graph contract")

    smoothed_curve_payload = academic_reports.get("smoothed_tension_curve")
    if not isinstance(smoothed_curve_payload, dict):
        raise ValueError("smoothed_tension_curve is missing")
    tension_curve_payload = smoothed_curve_payload.get("tension_curve")
    if not isinstance(tension_curve_payload, list):
        raise ValueError("smoothed_tension_curve.tension_curve is missing")

    peaks_payload = academic_reports.get("tension_peak_markers")
    plateau_payload = academic_reports.get("tension_plateau_regions")

    return TensionGraphContractResponse(
        metric_id=TENSION_GRAPH_METRIC_ID,
        metric_label=TENSION_GRAPH_METRIC_LABEL,
        source_path=TENSION_GRAPH_SOURCE_PATH,
        value_key=TENSION_GRAPH_VALUE_KEY,
        points=_coerce_tension_curve_points(tension_curve_payload),
        peak_markers=_coerce_peak_markers(peaks_payload),
        plateau_regions=_coerce_plateau_regions(plateau_payload),
        metadata={
            "smoothed_window_size": smoothed_curve_payload.get("window_size"),
            "peak_prominence_thresholds": (
                peaks_payload.get("prominence_thresholds")
                if isinstance(peaks_payload, dict)
                else None
            ),
            "plateau_region_params": (
                {
                    "flatness_tolerance": plateau_payload.get("flatness_tolerance"),
                    "min_region_length": plateau_payload.get("min_region_length"),
                }
                if isinstance(plateau_payload, dict)
                else None
            ),
        },
    )
