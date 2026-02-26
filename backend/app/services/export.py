import csv
import io
import json
import hashlib
from collections.abc import Mapping
from datetime import datetime, timezone
from math import inf
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models import Chapter, LLMCall, Project, Run, Segment


AUTHOR_DIAGNOSTIC_REQUIREMENTS = [
    ("ADR-001", "pacing_volatility_overview"),
    ("ADR-002", "monotony_risk_detector"),
    ("ADR-003", "character_imbalance_alerts"),
    ("ADR-004", "emotional_cadence_diagnostics"),
    ("ADR-005", "revision_priority_queue"),
    ("ADR-006", "diagnostics_manifest_and_provenance"),
]

_MONOTONY_WINDOW_SIZE = 6
_MONOTONY_TENSION_TOLERANCE = 0.06
_MONOTONY_EMOTION_TOLERANCE = 0.25
_MONOTONY_INTENSITY_TOLERANCE = 0.28
_EMOTIONAL_MONOTONY_WINDOW_SIZE = 6
_EMOTIONAL_MONOTONY_REPEAT_RATIO = 0.85
_EMOTIONAL_MONOTONY_VALENCE_TOLERANCE = 0.30
_EMOTIONAL_MONOTONY_INTENSITY_TOLERANCE = 0.40
_CHARACTER_DOMINANCE_OUTLIER_SHARE_THRESHOLD = 0.75
_CHARACTER_DOMINANCE_OUTLIER_GAP_THRESHOLD = 0.25
_CHARACTER_DOMINANCE_OUTLIER_MIN_SEGMENTS = 4
_CHARACTER_DISAPPEARANCE_MIN_TOTAL_SEGMENTS = 6
_CHARACTER_DISAPPEARANCE_MIN_APPEARED_CHAPTERS = 2
_CHARACTER_DISAPPEARANCE_MIN_GAP_CHAPTERS = 1
_DIALOGUE_DENSITY_ANOMALY_MIN_TOTAL_SEGMENTS = 6
_DIALOGUE_DENSITY_ANOMALY_MIN_CHAPTER_RUN = 2
_DIALOGUE_DENSITY_ANOMALY_DEVIATION_THRESHOLD = 0.28

ALLOWED_ACADEMIC_EXPORT_FORMATS: tuple[str, ...] = (
    "json",
    "csv",
    "time_series_json",
    "graph_json",
)


def _resolve_allowed_export_formats_from_run_config(run_config: Mapping[str, Any] | None) -> list[str]:
    raw_formats = None if not isinstance(run_config, Mapping) else run_config.get("export_formats")
    if raw_formats is None:
        return []
    if not isinstance(raw_formats, (list, tuple, set)):
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for raw_format in raw_formats:
        if not isinstance(raw_format, str):
            continue
        normalized_format = raw_format.strip().lower()
        if not normalized_format:
            continue
        if normalized_format not in ALLOWED_ACADEMIC_EXPORT_FORMATS:
            continue
        if normalized_format not in seen:
            normalized.append(normalized_format)
            seen.add(normalized_format)

    return normalized


def resolve_run_allowed_export_formats(run: Run) -> list[str]:
    return _resolve_allowed_export_formats_from_run_config(run.config_json)


def _serialize_datetime_to_utc_iso(value: datetime | None) -> str | None:
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).isoformat()
    return value.astimezone(timezone.utc).isoformat()


def _sanitize_provider_config_for_export(provider_config: object) -> dict[str, dict[str, Any]]:
    if not isinstance(provider_config, Mapping):
        return {}

    sanitized: dict[str, dict[str, Any]] = {}
    for provider_name, config in provider_config.items():
        if not isinstance(config, Mapping):
            continue

        normalized_provider_name = str(provider_name).strip().lower()
        if not normalized_provider_name:
            continue

        sanitized_config: dict[str, Any] = {}
        for key, value in config.items():
            if not isinstance(key, str):
                continue
            normalized_key = key.strip().lower()
            if normalized_key in {"api_key", "api_keys"}:
                continue
            sanitized_config[key] = value

        sanitized[normalized_provider_name] = sanitized_config

    return sanitized


def _sanitize_run_config_for_export(run_config: object) -> dict[str, Any]:
    if not isinstance(run_config, Mapping):
        return {}

    sanitized = dict(run_config)

    if "provider_config" in sanitized:
        sanitized["provider_config"] = _sanitize_provider_config_for_export(sanitized["provider_config"])

    sanitized.pop("provider_api_keys", None)
    return sanitized


def _compute_range(values: list[float]) -> float:
    if not values:
        return 0.0
    return max(values) - min(values)


def _build_chapter_type_classification(
    segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not segments:
        return []

    chapter_payloads: dict[int, dict[str, Any]] = {}
    chapter_order: list[int] = []
    for segment in segments:
        chapter_id = segment.get("chapter_id")
        if not isinstance(chapter_id, int):
            continue
        if chapter_id not in chapter_payloads:
            chapter_order.append(chapter_id)
            chapter_payloads[chapter_id] = {
                "tension_values": [],
                "intensity_values": [],
                "valence_values": [],
                "dialogue_segment_count": 0,
                "segment_count": 0,
            }

        payload = chapter_payloads[chapter_id]
        payload["segment_count"] += 1
        payload["tension_values"].append(
            _to_number(_to_dict(segment.get("tension_contribution")).get("value")) or 0.0
        )
        payload["intensity_values"].append(
            _to_number(segment.get("emotion_intensity")) or 0.0
        )
        payload["valence_values"].append(_to_number(segment.get("emotion_valence")) or 0.0)
        segment_type = segment.get("type")
        if isinstance(segment_type, str) and segment_type.strip().lower() == "dialogue":
            payload["dialogue_segment_count"] += 1

    if not chapter_order:
        return []

    chapter_summaries: list[dict[str, Any]] = []
    for chapter_id in chapter_order:
        payload = chapter_payloads[chapter_id]
        segment_count = int(payload["segment_count"])
        if segment_count <= 0:
            continue
        tension_values = [float(value) for value in payload["tension_values"]]
        intensity_values = [float(value) for value in payload["intensity_values"]]
        valence_values = [float(value) for value in payload["valence_values"]]
        dialogue_segments = int(payload["dialogue_segment_count"])

        avg_tension = sum(tension_values) / segment_count
        avg_intensity = sum(intensity_values) / segment_count
        avg_valence = sum(valence_values) / segment_count
        tension_range = max(tension_values) - min(tension_values) if tension_values else 0.0
        chapter_summaries.append(
            {
                "chapter_id": chapter_id,
                "segment_count": segment_count,
                "avg_tension": avg_tension,
                "avg_intensity": avg_intensity,
                "avg_valence": avg_valence,
                "tension_range": tension_range,
                "dialogue_ratio": dialogue_segments / segment_count,
            }
        )

    if not chapter_summaries:
        return []

    chapter_count = len(chapter_summaries)
    avg_tensions = [summary["avg_tension"] for summary in chapter_summaries]
    avg_intensities = [summary["avg_intensity"] for summary in chapter_summaries]

    min_tension = min(avg_tensions)
    max_tension = max(avg_tensions)
    tension_span = max_tension - min_tension if max_tension > min_tension else 0.0
    min_intensity = min(avg_intensities)
    max_intensity = max(avg_intensities)
    intensity_span = max_intensity - min_intensity if max_intensity > min_intensity else 0.0

    def _to_zero_to_one(value: float, min_value: float, span: float) -> float:
        if span <= 0.0:
            return 0.5
        normalized = (value - min_value) / span
        if normalized < 0.0:
            return 0.0
        if normalized > 1.0:
            return 1.0
        return normalized

    classifications: list[dict[str, Any]] = []
    for index, summary in enumerate(chapter_summaries):
        chapter_id = int(summary["chapter_id"])
        normalized_tension = _to_zero_to_one(summary["avg_tension"], min_tension, tension_span)
        normalized_intensity = _to_zero_to_one(summary["avg_intensity"], min_intensity, intensity_span)
        position_ratio = (index + 1) / chapter_count if chapter_count > 0 else 0.0

        prev_summary = chapter_summaries[index - 1] if index > 0 else None
        next_summary = chapter_summaries[index + 1] if index + 1 < chapter_count else None
        prev_delta = None
        next_delta = None
        if prev_summary is not None:
            prev_delta = summary["avg_tension"] - prev_summary["avg_tension"]
        if next_summary is not None:
            next_delta = next_summary["avg_tension"] - summary["avg_tension"]

        setup_score = 0.0
        setup_reasons: list[str] = []
        if index == 0:
            setup_score += 0.55
            setup_reasons.append("opening chapter in progression")
        if position_ratio <= 0.30:
            setup_score += 0.20
            setup_reasons.append("early chapter position")
        if normalized_tension <= 0.45:
            setup_score += 0.20
            setup_reasons.append("low tension baseline compared to chapter range")
        if summary["dialogue_ratio"] <= 0.45:
            setup_score += 0.10
            setup_reasons.append("moderate dialogue density")
        if prev_delta is not None and prev_delta <= 0.02:
            setup_score += 0.05
            setup_reasons.append("no strong tension ramp from previous chapter")

        build_up_score = 0.0
        build_up_reasons: list[str] = []
        if prev_delta is not None and prev_delta > 0.0:
            build_up_score += min(0.45, max(0.0, prev_delta) * 4.0)
            build_up_reasons.append("tension rises from previous chapter")
        if prev_delta is not None and prev_delta > 0.04:
            build_up_score += 0.15
            build_up_reasons.append("strong positive tension delta")
        if 0.10 <= normalized_tension <= 0.70:
            build_up_score += 0.20
            build_up_reasons.append("mid-tension trajectory")
        if next_delta is not None and next_delta > 0.0 and position_ratio < 0.85:
            build_up_score += 0.10
            build_up_reasons.append("upward next chapter tendency")

        confrontation_score = 0.0
        confrontation_reasons: list[str] = []
        if normalized_tension >= 0.62:
            confrontation_score += 0.55
            confrontation_reasons.append("high relative tension level")
        elif normalized_tension >= 0.45:
            confrontation_score += 0.30
            confrontation_reasons.append("above-average tension level")
        if normalized_intensity >= 0.65:
            confrontation_score += 0.20
            confrontation_reasons.append("high emotional intensity")
        if summary["tension_range"] >= 0.06:
            confrontation_score += 0.10
            confrontation_reasons.append("noticeable within-chapter tension spread")
        if summary["dialogue_ratio"] >= 0.55:
            confrontation_score += 0.10
            confrontation_reasons.append("high dialogue concentration")

        resolution_score = 0.0
        resolution_reasons: list[str] = []
        if index == chapter_count - 1:
            resolution_score += 0.55
            resolution_reasons.append("final chapter in sequence")
        if position_ratio >= 0.75:
            resolution_score += 0.20
            resolution_reasons.append("late chapter position")
        if prev_delta is not None and prev_delta < 0.0:
            resolution_score += min(0.25, abs(prev_delta) * 3.0)
            resolution_reasons.append("tension decreases from previous chapter")
        if normalized_tension <= 0.50:
            resolution_score += 0.20
            resolution_reasons.append("lower relative tension")
        if summary["tension_range"] <= 0.05:
            resolution_score += 0.10
            resolution_reasons.append("stable within-chapter arc")

        transitional_score = 0.10
        transitional_reasons: list[str] = ["non-dominant cue pattern"]
        if index not in {0, chapter_count - 1} and normalized_tension > 0.35 and normalized_tension < 0.65:
            transitional_score += 0.15
            transitional_reasons.append("balanced midrange tension profile")
        if summary["segment_count"] <= 3:
            transitional_score += 0.10
            transitional_reasons.append("short chapter window")

        best_type = "transitional"
        best_score = transitional_score
        best_reasons = transitional_reasons

        all_scores = [
            ("setup", setup_score, setup_reasons),
            ("build-up", build_up_score, build_up_reasons),
            ("confrontation", confrontation_score, confrontation_reasons),
            ("resolution", resolution_score, resolution_reasons),
        ]
        for chapter_type, score, reasons in all_scores:
            if score > best_score:
                best_type = chapter_type
                best_score = score
                best_reasons = reasons

        if not best_reasons and best_type == "transitional":
            best_reasons = ["default transitional classification"]

        clipped_score = max(0.05, min(1.0, best_score))
        classifications.append(
            {
                "chapter_id": chapter_id,
                "chapter_type": best_type,
                "confidence": round(clipped_score, 4),
                "reasons": best_reasons,
                "features": {
                    "position_ratio": round(position_ratio, 4),
                    "segment_count": segment_count,
                    "avg_tension": round(float(summary["avg_tension"]), 4),
                    "avg_intensity": round(float(summary["avg_intensity"]), 4),
                    "avg_valence": round(float(summary["avg_valence"]), 4),
                    "tension_range": round(float(summary["tension_range"]), 4),
                    "dialogue_ratio": round(float(summary["dialogue_ratio"]), 4),
                    "tension_delta_from_previous_chapter": None
                    if prev_delta is None
                    else round(float(prev_delta), 4),
                    "tension_delta_to_next_chapter": None
                    if next_delta is None
                    else round(float(next_delta), 4),
                },
            }
        )

    return classifications


def _compute_variance(values: list[float]) -> float:
    count = len(values)
    if count == 0:
        return 0.0
    mean = sum(values) / count
    return sum((value - mean) ** 2 for value in values) / count


def _build_emotional_monotony_findings(
    segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if len(segments) < _EMOTIONAL_MONOTONY_WINDOW_SIZE:
        return []

    valence_values: list[float] = []
    intensity_values: list[float] = []
    labels: list[str | None] = []
    for segment in segments:
        valence_values.append(_to_number(segment.get("emotion_valence")) or 0.0)
        intensity_values.append(_to_number(segment.get("emotion_intensity")) or 0.0)
        label = segment.get("emotion_primary_label")
        labels.append(label.strip().lower() if isinstance(label, str) else None)

    def is_low_variation_and_repetitive(start_index: int, end_index: int) -> bool:
        valence_slice = valence_values[start_index : end_index + 1]
        intensity_slice = intensity_values[start_index : end_index + 1]
        label_slice = labels[start_index : end_index + 1]
        if len(valence_slice) != (end_index - start_index + 1) or len(intensity_slice) != (end_index - start_index + 1):
            return False
        if _compute_range(valence_slice) > _EMOTIONAL_MONOTONY_VALENCE_TOLERANCE:
            return False
        if _compute_range(intensity_slice) > _EMOTIONAL_MONOTONY_INTENSITY_TOLERANCE:
            return False

        valid_labels = [label for label in label_slice if isinstance(label, str)]
        if len(valid_labels) == 0:
            return False

        mode_counts: dict[str, int] = {}
        for label in valid_labels:
            mode_counts[label] = mode_counts.get(label, 0) + 1
        dominant_label_count = max(mode_counts.values())
        label_count = len(valid_labels)
        if label_count == 0:
            return False
        repeat_ratio = dominant_label_count / label_count
        return repeat_ratio >= _EMOTIONAL_MONOTONY_REPEAT_RATIO

    findings: list[dict[str, Any]] = []
    start_index = 0
    while start_index <= len(segments) - _EMOTIONAL_MONOTONY_WINDOW_SIZE:
        end_index = start_index + _EMOTIONAL_MONOTONY_WINDOW_SIZE - 1
        if not is_low_variation_and_repetitive(start_index, end_index):
            start_index += 1
            continue

        while end_index + 1 < len(segments) and is_low_variation_and_repetitive(
            start_index, end_index + 1
        ):
            end_index += 1

        valence_slice = valence_values[start_index : end_index + 1]
        intensity_slice = intensity_values[start_index : end_index + 1]
        label_slice = labels[start_index : end_index + 1]
        segment_slice = segments[start_index : end_index + 1]
        valid_labels = [label for label in label_slice if isinstance(label, str)]
        mode_counts: dict[str, int] = {}
        for label in valid_labels:
            mode_counts[label] = mode_counts.get(label, 0) + 1
        dominant_label, dominant_count = sorted(mode_counts.items(), key=lambda item: item[1], reverse=True)[0]
        repeat_ratio = dominant_count / len(valid_labels) if valid_labels else 0.0

        valence_score = 1.0 - (_compute_range(valence_slice) / _EMOTIONAL_MONOTONY_VALENCE_TOLERANCE)
        intensity_score = 1.0 - (_compute_range(intensity_slice) / _EMOTIONAL_MONOTONY_INTENSITY_TOLERANCE)
        repetition_score = repeat_ratio
        severity = round(
            (0.55 * repetition_score + 0.25 * max(0.0, valence_score) + 0.20 * max(0.0, intensity_score))
            * min(1.0, len(valence_slice) / 10.0),
            4,
        )

        first_segment = segment_slice[0]
        last_segment = segment_slice[-1]
        start_chapter = first_segment.get("chapter_id")
        end_chapter = last_segment.get("chapter_id")
        start_segment = first_segment.get("segment_index")
        end_segment = last_segment.get("segment_index")
        if not isinstance(start_chapter, int):
            start_chapter = None
        if not isinstance(end_chapter, int):
            end_chapter = None
        if not isinstance(start_segment, int):
            start_segment = None
        if not isinstance(end_segment, int):
            end_segment = None

        findings.append(
            {
                "requirement_id": "ADR-002",
                "requirement_name": "monotony_risk_detector",
                "location": {
                    "start_chapter": start_chapter,
                    "end_chapter": end_chapter,
                    "start_segment": start_segment,
                    "end_segment": end_segment,
                },
                "trigger_metric": "repeated_tone_pattern",
                "severity": severity,
                "evidence": {
                    "window_start_position": start_index + 1,
                    "window_end_position": end_index + 1,
                    "window_length": len(valence_slice),
                    "dominant_tone": dominant_label,
                    "dominant_tone_ratio": round(repeat_ratio, 4),
                    "valence_range": round(_compute_range(valence_slice), 4),
                    "valence_variance": round(_compute_variance(valence_slice), 6),
                    "intensity_range": round(_compute_range(intensity_slice), 4),
                    "intensity_variance": round(_compute_variance(intensity_slice), 6),
                    "tone_counts": sorted(mode_counts.items(), key=lambda item: item[1], reverse=True),
                    "start_segment_id": first_segment.get("segment_id"),
                    "end_segment_id": last_segment.get("segment_id"),
                },
            }
        )
        start_index = end_index + 1

    return findings


def _build_character_dominance_findings(
    chapter_level_character_dominance: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for chapter_summary in chapter_level_character_dominance:
        chapter_id = chapter_summary.get("chapter_id")
        if not isinstance(chapter_id, int):
            continue

        chapter_segment_count = chapter_summary.get("chapter_segment_count")
        if (
            not isinstance(chapter_segment_count, int)
            or chapter_segment_count < _CHARACTER_DOMINANCE_OUTLIER_MIN_SEGMENTS
        ):
            continue

        distribution = chapter_summary.get("character_dominance_distribution")
        if not isinstance(distribution, list) or len(distribution) < 2:
            continue

        top_character = distribution[0]
        second_character = distribution[1]
        top_share = _to_number(top_character.get("dominance_share"))
        second_share = _to_number(second_character.get("dominance_share"))
        if top_share is None or second_share is None:
            continue

        lead_gap = top_share - second_share
        if (
            top_share < _CHARACTER_DOMINANCE_OUTLIER_SHARE_THRESHOLD
            or lead_gap < _CHARACTER_DOMINANCE_OUTLIER_GAP_THRESHOLD
        ):
            continue

        dominance_share_score = min(
            1.0,
            max(
                0.0,
                (top_share - _CHARACTER_DOMINANCE_OUTLIER_SHARE_THRESHOLD)
                / (1 - _CHARACTER_DOMINANCE_OUTLIER_SHARE_THRESHOLD),
            ),
        )
        gap_score = min(
            1.0,
            lead_gap / _CHARACTER_DOMINANCE_OUTLIER_GAP_THRESHOLD,
        )
        segment_score = min(1.0, chapter_segment_count / 20.0)
        severity = round(
            0.55 * dominance_share_score
            + 0.30 * gap_score
            + 0.15 * segment_score,
            4,
        )

        findings.append(
            {
                "requirement_id": "ADR-003",
                "requirement_name": "character_imbalance_alerts",
                "location": {
                    "start_chapter": chapter_id,
                    "end_chapter": chapter_id,
                },
                "trigger_metric": "character_dominance_outlier",
                "severity": min(1.0, severity),
                "evidence": {
                    "chapter_id": chapter_id,
                    "chapter_segment_count": chapter_segment_count,
                    "top_character": top_character.get("speaker"),
                    "top_character_id": top_character.get("speaker_id"),
                    "top_character_share": round(top_share, 4),
                    "next_character": second_character.get("speaker"),
                    "next_character_id": second_character.get("speaker_id"),
                    "next_character_share": round(second_share, 4),
                    "lead_share_gap": round(lead_gap, 4),
                    "share_threshold": _CHARACTER_DOMINANCE_OUTLIER_SHARE_THRESHOLD,
                    "share_gap_threshold": _CHARACTER_DOMINANCE_OUTLIER_GAP_THRESHOLD,
                },
            }
        )

    return findings


def _build_disappearing_character_findings(
    segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not segments:
        return []

    chapter_speaker_counts: dict[str, set[int]] = {}
    chapter_segment_counts: dict[str, int] = {}
    canonical_speaker_labels: dict[str, str] = {}
    chapter_indices: set[int] = set()

    for segment in segments:
        chapter_id = segment.get("chapter_id")
        if not isinstance(chapter_id, int):
            continue
        speaker = segment.get("speaker")
        if not isinstance(speaker, str):
            continue

        speaker_label = speaker.strip()
        if not speaker_label or speaker_label.lower() == "unknown":
            continue
        speaker_key = speaker_label.lower()
        if not speaker_key:
            continue

        chapter_indices.add(chapter_id)
        chapter_speaker_counts.setdefault(speaker_key, set()).add(chapter_id)
        chapter_segment_counts[speaker_key] = chapter_segment_counts.get(speaker_key, 0) + 1
        if speaker_key not in canonical_speaker_labels:
            canonical_speaker_labels[speaker_key] = speaker_label

    if len(chapter_indices) < 3:
        return []

    final_chapter = max(chapter_indices)
    findings: list[dict[str, Any]] = []
    for speaker_key in sorted(chapter_speaker_counts):
        speaker_chapters = sorted(chapter_speaker_counts[speaker_key])
        if len(speaker_chapters) < _CHARACTER_DISAPPEARANCE_MIN_APPEARED_CHAPTERS:
            continue

        total_segment_mentions = chapter_segment_counts.get(speaker_key, 0)
        if total_segment_mentions < _CHARACTER_DISAPPEARANCE_MIN_TOTAL_SEGMENTS:
            continue

        first_seen = speaker_chapters[0]
        last_seen = speaker_chapters[-1]
        if last_seen >= final_chapter:
            continue

        missing_chapter_count = final_chapter - last_seen
        if missing_chapter_count < _CHARACTER_DISAPPEARANCE_MIN_GAP_CHAPTERS:
            continue

        start_chapter = last_seen + 1
        severity = round(
            min(1.0, 0.55 * min(1.0, total_segment_mentions / 12.0) + 0.30 * min(1.0, missing_chapter_count / 4.0) + 0.15),
            4,
        )

        findings.append(
            {
                "requirement_id": "ADR-005",
                "requirement_name": "revision_priority_queue",
                "location": {
                    "start_chapter": start_chapter,
                    "end_chapter": final_chapter,
                },
                "trigger_metric": "character_disappearance",
                "severity": severity,
                "evidence": {
                    "speaker": canonical_speaker_labels.get(speaker_key, speaker_key),
                    "speaker_key": speaker_key,
                    "first_seen_chapter": first_seen,
                    "last_seen_chapter": last_seen,
                    "total_seen_chapters": len(speaker_chapters),
                    "total_segment_mentions": total_segment_mentions,
                    "final_chapter": final_chapter,
                    "missing_chapter_count": missing_chapter_count,
                    "disappearance_start_chapter": start_chapter,
                    "disappearance_end_chapter": final_chapter,
                    "min_total_segments_threshold": _CHARACTER_DISAPPEARANCE_MIN_TOTAL_SEGMENTS,
                    "min_gap_threshold": _CHARACTER_DISAPPEARANCE_MIN_GAP_CHAPTERS,
                },
            }
        )

    return findings


def _build_dialogue_density_anomaly_findings(
    segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    chapter_aggregates: dict[int, dict[str, int]] = {}
    for segment in segments:
        chapter_id = segment.get("chapter_id")
        if not isinstance(chapter_id, int):
            continue
        if chapter_id not in chapter_aggregates:
            chapter_aggregates[chapter_id] = {"total": 0, "dialogue": 0}

        chapter_aggregates[chapter_id]["total"] += 1
        segment_type = segment.get("type")
        if isinstance(segment_type, str) and segment_type.strip().lower() == "dialogue":
            chapter_aggregates[chapter_id]["dialogue"] += 1

    if not chapter_aggregates:
        return []

    chapter_densities: list[dict[str, Any]] = []
    for chapter_id in sorted(chapter_aggregates):
        payload = chapter_aggregates[chapter_id]
        total_segments = payload.get("total", 0)
        if total_segments < _DIALOGUE_DENSITY_ANOMALY_MIN_TOTAL_SEGMENTS:
            continue

        dialogue_count = payload.get("dialogue", 0)
        density = dialogue_count / total_segments
        chapter_densities.append(
            {
                "chapter_id": chapter_id,
                "total_segments": total_segments,
                "dialogue_segments": dialogue_count,
                "dialogue_density": density,
            }
        )

    if len(chapter_densities) < 3:
        return []

    global_dialogue_density = sum(
        chapter_density["dialogue_density"] for chapter_density in chapter_densities
    ) / len(chapter_densities)

    def _local_excess(index: int) -> float | None:
        current = chapter_densities[index]
        density = current["dialogue_density"]
        return density - global_dialogue_density

    findings: list[dict[str, Any]] = []
    current_run: list[dict[str, Any]] = []
    current_direction: int = 0

    def _flush_current_run() -> None:
        nonlocal current_run, current_direction, findings
        if not current_run or len(current_run) < _DIALOGUE_DENSITY_ANOMALY_MIN_CHAPTER_RUN:
            return

        direction = current_direction
        if direction == 0:
            return

        start_chapter = current_run[0]["chapter_id"]
        end_chapter = current_run[-1]["chapter_id"]
        average_excess = sum(item["excess"] for item in current_run) / len(current_run)
        max_excess = max(abs(item["excess"]) for item in current_run)
        avg_segments = sum(item["total_segments"] for item in current_run) / len(current_run)
        severity = round(
            min(
                1.0,
                0.65 * min(1.0, abs(average_excess) * 1.8)
                + 0.25 * min(1.0, len(current_run) / 5.0)
                + 0.10 * min(1.0, avg_segments / 12.0),
            ),
            4,
        )
        trigger_metric = (
            "elevated_dialogue_density"
            if direction == 1
            else "reduced_dialogue_density"
        )

        findings.append(
            {
                "requirement_id": "ADR-006",
                "requirement_name": "dialogue_density_anomaly_detector",
                "location": {
                    "start_chapter": start_chapter,
                    "end_chapter": end_chapter,
                },
                "trigger_metric": trigger_metric,
                "severity": severity,
                "evidence": {
                    "global_dialogue_density": round(global_dialogue_density, 4),
                    "anomaly_direction": "dialogue_heavy" if direction == 1 else "dialogue_sparse",
                    "mean_excess": round(average_excess, 4),
                    "max_excess": round(max_excess, 4),
                    "chapter_window": len(current_run),
                    "anomaly_threshold": _DIALOGUE_DENSITY_ANOMALY_DEVIATION_THRESHOLD,
                    "chapter_profile": [
                        {
                            "chapter_id": item["chapter_id"],
                            "dialogue_density": item["dialogue_density"],
                            "total_segments": item["total_segments"],
                            "dialogue_segments": item["dialogue_segments"],
                            "excess": round(item["excess"], 4),
                        }
                        for item in current_run
                    ],
                },
            }
        )

    for index in range(len(chapter_densities)):
        chapter_density = chapter_densities[index]
        excess = _local_excess(index)
        if excess is None:
            continue

        if abs(excess) < _DIALOGUE_DENSITY_ANOMALY_DEVIATION_THRESHOLD:
            _flush_current_run()
            current_run = []
            current_direction = 0
            continue

        direction = 1 if excess > 0 else -1
        entry = {
            **chapter_density,
            "excess": excess,
            "direction": direction,
        }

        if current_direction == 0:
            current_run = [entry]
            current_direction = direction
            continue

        if direction != current_direction:
            _flush_current_run()
            current_run = [entry]
            current_direction = direction
            continue

        current_run.append(entry)

    _flush_current_run()
    return findings


def _build_monotony_risk_findings(
    segments: list[dict[str, Any]],
    smoothed_tension_curve: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    limit = min(len(segments), len(smoothed_tension_curve))
    if limit < _MONOTONY_WINDOW_SIZE:
        return []

    tension_values: list[float] = []
    valence_values: list[float] = []
    intensity_values: list[float] = []
    for index in range(limit):
        tension_values.append(_to_number(smoothed_tension_curve[index].get("smoothed_tension")) or 0.0)
        valence_values.append(_to_number(segments[index].get("emotion_valence")) or 0.0)
        intensity_values.append(_to_number(segments[index].get("emotion_intensity")) or 0.0)

    def is_low_variance_window(start_index: int, end_index: int) -> bool:
        tension_slice = tension_values[start_index : end_index + 1]
        valence_slice = valence_values[start_index : end_index + 1]
        intensity_slice = intensity_values[start_index : end_index + 1]
        if (
            len(tension_slice) != (end_index - start_index + 1)
            or len(valence_slice) != (end_index - start_index + 1)
            or len(intensity_slice) != (end_index - start_index + 1)
        ):
            return False
        if (
            _compute_range(tension_slice) > _MONOTONY_TENSION_TOLERANCE
            or _compute_range(valence_slice) > _MONOTONY_EMOTION_TOLERANCE
            or _compute_range(intensity_slice) > _MONOTONY_INTENSITY_TOLERANCE
        ):
            return False
        return True

    findings: list[dict[str, Any]] = []
    start_index = 0
    while start_index <= limit - _MONOTONY_WINDOW_SIZE:
        end_index = start_index + _MONOTONY_WINDOW_SIZE - 1
        if not is_low_variance_window(start_index, end_index):
            start_index += 1
            continue

        while end_index + 1 < limit and is_low_variance_window(start_index, end_index + 1):
            end_index += 1

        tension_slice = tension_values[start_index : end_index + 1]
        valence_slice = valence_values[start_index : end_index + 1]
        intensity_slice = intensity_values[start_index : end_index + 1]
        segment_slice = segments[start_index : end_index + 1]

        flatness_scores = [
            1.0 - (_compute_range(tension_slice) / _MONOTONY_TENSION_TOLERANCE),
            1.0 - (_compute_range(valence_slice) / _MONOTONY_EMOTION_TOLERANCE),
            1.0 - (_compute_range(intensity_slice) / _MONOTONY_INTENSITY_TOLERANCE),
        ]
        flatness_score = max(0.0, sum(score for score in flatness_scores if score > 0.0) / 3)
        length_score = min(1.0, (len(tension_slice) - _MONOTONY_WINDOW_SIZE + 1) / 4)
        severity = round((0.75 * flatness_score + 0.25 * length_score), 4)

        first_segment = segment_slice[0]
        last_segment = segment_slice[-1]
        start_chapter = first_segment.get("chapter_id")
        end_chapter = last_segment.get("chapter_id")
        start_segment = first_segment.get("segment_index")
        end_segment = last_segment.get("segment_index")
        if not isinstance(start_chapter, int):
            start_chapter = None
        if not isinstance(end_chapter, int):
            end_chapter = None
        if not isinstance(start_segment, int):
            start_segment = None
        if not isinstance(end_segment, int):
            end_segment = None

        findings.append(
            {
                "requirement_id": "ADR-002",
                "requirement_name": "monotony_risk_detector",
                "location": {
                    "start_chapter": start_chapter,
                    "end_chapter": end_chapter,
                    "start_segment": start_segment,
                    "end_segment": end_segment,
                },
                "trigger_metric": "low_tension_and_emotion_variance_window",
                "severity": severity,
                "evidence": {
                    "window_start_position": start_index + 1,
                    "window_end_position": end_index + 1,
                    "window_length": len(tension_slice),
                    "tension_range": round(_compute_range(tension_slice), 4),
                    "tension_variance": round(_compute_variance(tension_slice), 6),
                    "valence_range": round(_compute_range(valence_slice), 4),
                    "valence_variance": round(_compute_variance(valence_slice), 6),
                    "intensity_range": round(_compute_range(intensity_slice), 4),
                    "intensity_variance": round(_compute_variance(intensity_slice), 6),
                    "start_segment_id": first_segment.get("segment_id"),
                    "end_segment_id": last_segment.get("segment_id"),
                },
            }
        )

        start_index = end_index + 1

    return findings


def _to_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _build_tag_bundle(segment_json: Mapping[str, Any]) -> dict[str, Any]:
    confidence = _to_dict(segment_json.get("confidence"))
    return {
        "type": segment_json.get("type"),
        "speaker": segment_json.get("speaker"),
        "speaker_id": segment_json.get("speaker_id"),
        "gender": segment_json.get("gender"),
        "emotion": {
            "valence": segment_json.get("emotion_valence"),
            "intensity": segment_json.get("emotion_intensity"),
            "primary_label": segment_json.get("emotion_primary_label"),
            "secondary_label": segment_json.get("emotion_secondary_label"),
            "state": segment_json.get("emotion_state"),
            "evidence": _to_dict(segment_json.get("emotion_evidence")),
            "confidence": confidence.get("emotion"),
        },
        "type_confidence": confidence.get("type"),
        "speaker_confidence": confidence.get("speaker"),
        "tension": {
            **_to_dict(segment_json.get("tension_contribution")),
            "confidence": confidence.get("tension"),
        },
        "dominance": {
            **_to_dict(segment_json.get("dominance_contribution")),
            "confidence": confidence.get("dominance"),
        },
        "summary_tag": _to_dict(segment_json.get("summary_tag")),
        "type_evidence": _to_dict(segment_json.get("type_evidence")),
        "speaker_evidence": _to_dict(segment_json.get("speaker_evidence")),
        "sub_segment_boundaries": segment_json.get("sub_segment_boundaries", []),
        "confidence": confidence,
    }


def _normalize_segment_for_export(segment_json: Any) -> dict[str, Any]:
    if not isinstance(segment_json, Mapping):
        return {}
    segment_payload = dict(segment_json)
    segment_payload["tag_bundle"] = _build_tag_bundle(segment_payload)
    return segment_payload


def _build_project_config_snapshot(project: Project) -> dict[str, Any]:
    return {
        "configuration_snapshot_id": project.configuration_snapshot_id,
        "selected_mode": project.selected_mode,
        "selected_modes": list(project.selected_modes or []),
        "voice_config": dict(project.voice_config_json or {}),
        "default_voices": {
            "narrator": project.default_narrator_voice,
            "male": project.default_male_voice,
            "female": project.default_female_voice,
            "neutral": project.default_neutral_voice,
            "unknown": project.default_unknown_voice,
        },
    }


def _load_run_llm_calls(session: Session, run: Run) -> list[dict[str, Any]]:
    llm_calls = (
        session.query(LLMCall)
        .filter(LLMCall.run_id == run.id)
        .order_by(LLMCall.created_at.asc(), LLMCall.id.asc())
        .all()
    )
    return [
        {
            "id": call.id,
            "provider": call.provider,
            "task_type": call.task_type,
            "success": call.success,
            "request_count": call.request_count,
            "token_usage_estimate": call.token_usage_estimate,
            "model_identifier": call.model_identifier,
            "called_at": _serialize_datetime_to_utc_iso(call.called_at),
            "detail": call.detail,
            "created_at": call.created_at.isoformat(),
        }
        for call in llm_calls
    ]


def _build_export_reports(project: Project, run: Run, segment_count: int, ordered_by: list[str]) -> dict[str, Any]:
    run_snapshot = _sanitize_run_config_for_export(run.config_json)
    project_ingestion_log = dict(project.ingestion_log_json or {})
    return {
        "project": {
            "id": project.id,
            "title": project.title,
            "configuration_snapshot_id": project.configuration_snapshot_id,
            "selected_mode": project.selected_mode,
        },
        "run": {
            "id": run.id,
            "status": run.status,
            "segment_count": segment_count,
            "ordered_by": ordered_by,
        },
        "normalization_report": project_ingestion_log.get("normalization_report", {}),
        "character_analytics_snapshot": {
            key: run_snapshot.get(key)
            for key in (
                "character_mentions_by_chapter",
                "character_first_appearance_chapter_index",
                "character_last_appearance_chapter_index",
                "character_mentions_per_1000_words",
                "character_dialogue_line_counts",
            )
            if run_snapshot.get(key) is not None
        },
        "mode_profile_snapshot": _to_dict(run_snapshot.get("voice_config")),
        "generated_at": run.finished_at.isoformat() if run.finished_at else run.started_at.isoformat(),
    }


def _build_author_narrative_health_report(
    project: Project,
    run: Run,
    generated_at: datetime,
    segment_count: int,
    monotony_findings: list[dict[str, Any]] | None = None,
    emotional_monotony_findings: list[dict[str, Any]] | None = None,
    character_dominance_findings: list[dict[str, Any]] | None = None,
    disappearing_character_findings: list[dict[str, Any]] | None = None,
    dialogue_density_findings: list[dict[str, Any]] | None = None,
    chapter_type_classification: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    generated_at_iso = generated_at.isoformat()
    resolved_monotony_findings = monotony_findings or []
    resolved_emotional_monotony_findings = emotional_monotony_findings or []
    resolved_character_dominance_findings = character_dominance_findings or []
    resolved_disappearing_character_findings = disappearing_character_findings or []
    resolved_dialogue_density_findings = dialogue_density_findings or []
    resolved_chapter_type_classification = chapter_type_classification or []
    combined_findings = (
        resolved_monotony_findings
        + resolved_emotional_monotony_findings
        + resolved_character_dominance_findings
        + resolved_disappearing_character_findings
        + resolved_dialogue_density_findings
    )
    finding_by_requirement: dict[str, list[dict[str, Any]]] = {
        "ADR-002": resolved_monotony_findings + resolved_emotional_monotony_findings,
        "ADR-003": resolved_character_dominance_findings,
        "ADR-005": resolved_disappearing_character_findings,
        "ADR-006": resolved_dialogue_density_findings,
    }
    implemented_requirements = {"ADR-002", "ADR-003", "ADR-005", "ADR-006"}
    requirements = [
        {
            "requirement_id": requirement_id,
            "requirement_name": requirement_name,
            "status": "implemented" if requirement_id in implemented_requirements else "not_implemented",
            "finding_count": len(finding_by_requirement.get(requirement_id, [])),
            "findings": list(finding_by_requirement.get(requirement_id, [])),
        }
        for requirement_id, requirement_name in AUTHOR_DIAGNOSTIC_REQUIREMENTS
    ]

    return {
        "schema_version": "1.0.0",
        "output_schema": "author_narrative_health_json",
        "generated_at": generated_at_iso,
        "generated_by": "build_run_export",
        "project_reference": {
            "project_id": project.id,
            "project_title": project.title,
            "selected_mode": project.selected_mode,
            "selected_modes": list(project.selected_modes or []),
        },
        "run_reference": {
            "run_id": run.id,
            "status": run.status,
            "segment_count": segment_count,
            "ordered_by": ["chapter_index", "segment_index"],
        },
        "chapter_type_classification": resolved_chapter_type_classification,
        "requirements": requirements,
        "findings": combined_findings,
    }


def _build_json_fingerprint(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _build_comparative_run_signature(segments: list[dict[str, Any]]) -> str:
    signature_rows: list[dict[str, Any]] = []
    for segment in segments:
        signature_rows.append(
            {
                "chapter_index": segment.get("chapter_index"),
                "segment_index": segment.get("segment_index"),
                "speaker": segment.get("speaker"),
                "normalized_text": segment.get("normalized_text") or "",
            }
        )
    return _build_json_fingerprint(signature_rows)


def _build_comparative_run_metrics_snapshot(
    project: Project,
    run: Run,
    segments: list[dict[str, Any]],
    ordered_by: list[str],
) -> dict[str, Any]:
    chapter_indices = sorted(
        {
            int(chapter_index)
            for chapter_index in (segment.get("chapter_index") for segment in segments)
            if isinstance(chapter_index, int)
        }
    )
    segment_signature = _build_comparative_run_signature(segments)
    run_snapshot = _sanitize_run_config_for_export(run.config_json)

    return {
        "snapshot_type": "comparative_run_metrics_snapshot",
        "schema_version": "1.0.0",
        "generated_by": "build_run_export",
        "project_reference": {
            "project_id": project.id,
            "project_title": project.title,
            "configuration_snapshot_id": project.configuration_snapshot_id,
            "selected_mode": project.selected_mode,
            "selected_modes": list(project.selected_modes or []),
        },
        "run_reference": {
            "run_id": run.id,
            "status": run.status,
            "ordered_by": ordered_by,
            "segment_count": len(segments),
            "chapter_count": len(chapter_indices),
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        },
        "reproducibility": {
            "run_config_fingerprint": _build_json_fingerprint(run_snapshot),
            "project_config_fingerprint": _build_json_fingerprint(_build_project_config_snapshot(project)),
            "input_signature": {
                "segment_signature": segment_signature,
                "chapter_indices": chapter_indices,
            },
        },
        "run_config_snapshot": run_snapshot,
        "project_config_snapshot": _build_project_config_snapshot(project),
    }


def _build_academic_export_output_inventory(
    academic_reports: dict[str, Any],
    generated_at: str,
    schema_version: str,
    allowed_export_formats: list[str],
) -> list[dict[str, Any]]:
    allowed_formats = set(allowed_export_formats)

    def _record_count(value: Any) -> int | None:
        if value is None:
            return None
        if isinstance(value, list):
            return len(value)
        if isinstance(value, dict):
            return len(value)
        return 1

    def _build_entry(
        output_id: str,
        output_name: str,
        supported_formats: list[str],
        data_keys: list[str] | None = None,
        available: bool = True,
        reason: str | None = None,
    ) -> dict[str, Any]:
        payloads = [
            academic_reports.get(key) for key in (data_keys or [])
        ]
        record_counts = [_record_count(payload) for payload in payloads]
        available_formats = [
            supported_format for supported_format in supported_formats if supported_format in allowed_formats
        ]
        is_available = bool(available_formats) if available else False

        return {
            "output_id": output_id,
            "output_name": output_name,
            "supported_formats": supported_formats,
            "status": "available" if is_available else "not_implemented",
            "available_formats": available_formats,
            "data_keys": data_keys or [],
            "data_record_counts": record_counts,
            "evidence": {
                "generated_by": f"academic_export_schema_{schema_version.replace('.', '_')}",
                "generated_at": generated_at,
                "status_reason": reason
                if reason is not None
                else (None if is_available else "No allowed formats enabled for this output."),
            },
        }

    return [
        _build_entry(
            output_id="AO-001",
            output_name="chapter_emotion_metrics_series",
            supported_formats=["json", "csv", "time_series_json"],
            data_keys=[
                "chapter_level_valence_means",
                "chapter_level_valence_variance",
            ],
            available=True,
        ),
        _build_entry(
            output_id="AO-002",
            output_name="chapter_tension_curve_summary",
            supported_formats=["json", "csv", "time_series_json"],
            data_keys=[
                "chapter_level_raw_tension",
                "smoothed_tension_curve",
                "tension_peak_markers",
                "tension_plateau_regions",
            ],
            available=True,
        ),
        _build_entry(
            output_id="AO-003",
            output_name="character_dominance_series",
            supported_formats=["json", "csv", "time_series_json"],
            data_keys=["chapter_level_character_dominance"],
            available=True,
        ),
        _build_entry(
            output_id="AO-004",
            output_name="character_cooccurrence_graph",
            supported_formats=["json", "graph_json", "csv"],
            data_keys=["character_cooccurrence_graph", "character_cooccurrence_centrality_table"],
            available=True,
        ),
        _build_entry(
            output_id="AO-005",
            output_name="comparative_run_metrics_snapshot",
            supported_formats=["json", "csv"],
            data_keys=["comparative_run_metrics_snapshot"],
            available=True,
        ),
        _build_entry(
            output_id="AO-006",
            output_name="academic_export_manifest",
            supported_formats=["json"],
            data_keys=["academic_export_manifest"],
            available=True,
        ),
    ]


def _build_academic_export_manifest(
    project: Project,
    run: Run,
    academic_reports: dict[str, Any],
    generated_at: datetime,
    allowed_export_formats: list[str],
) -> dict[str, Any]:
    generated_at_iso = generated_at.isoformat()
    schema_version = "1.0.0"
    inventory = _build_academic_export_output_inventory(
        academic_reports=academic_reports,
        generated_at=generated_at_iso,
        schema_version=schema_version,
        allowed_export_formats=allowed_export_formats,
    )

    return {
        "schema_version": schema_version,
        "output_schema": "academic_json",
        "export_format": "json",
        "generated_at": generated_at_iso,
        "generated_by": "build_run_export",
        "project_id": project.id,
        "run_id": run.id,
        "run_status": run.status,
        "ordered_by": ["chapter_index", "segment_index"],
        "outputs": inventory,
    }


def _build_segment_rows_query(run_id: int, from_chapter_index: int | None, from_segment_index: int | None):
    base_query = (
        select(Segment.segment_json)
        .join(Chapter, Chapter.id == Segment.chapter_id)
        .where(Segment.run_id == run_id)
        .order_by(Chapter.chapter_index.asc(), Segment.segment_index.asc())
    )
    if from_chapter_index is None and from_segment_index is None:
        return base_query

    if from_chapter_index is None or from_segment_index is None:
        raise ValueError("from_chapter_index and from_segment_index must be provided together")

    return base_query.where(
        or_(
            Chapter.chapter_index > from_chapter_index,
            and_(
                Chapter.chapter_index == from_chapter_index,
                Segment.segment_index > from_segment_index,
            ),
        )
    )


def _to_number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _compute_scene_state(
    segment_position: int,
    emotion_valence: float,
    emotion_intensity: float,
    tension_value: float,
    dominance_value: float,
    prev_tension: float | None,
    emotion_delta: float,
    tension_delta: float,
    summary_tone: str,
) -> tuple[str, list[str], dict[str, Any]]:
    tension_band = (
        "high" if tension_value >= 0.70 else "moderate" if tension_value >= 0.40 else "low"
    )
    if summary_tone == "dark_irony":
        tone_hint = "dark_irony"
    else:
        tone_hint = summary_tone or "neutral"

    momentum = "steady"
    if prev_tension is not None:
        if tension_delta >= 0.12:
            momentum = "rising"
        elif tension_delta <= -0.12:
            momentum = "dropping"

    state = "scene_stable"
    reasons: list[str] = []
    evidence: dict[str, Any] = {
        "segment_position": segment_position,
        "tension_band": tension_band,
        "momentum": momentum,
        "summary_tone": tone_hint,
        "emotion_bias": (
            "positive"
            if emotion_valence >= 0.25
            else "negative" if emotion_valence <= -0.25 else "neutral"
        ),
        "dominance_band": "high" if dominance_value >= 0.75 else "moderate" if dominance_value >= 0.40 else "low",
    }

    if tension_band == "high":
        if momentum == "rising":
            state = "climb_to_peak"
            reasons.append("tension_rising_high")
        elif momentum == "dropping":
            state = "peak_fade"
            reasons.append("tension_rolling_from_peak")
        else:
            state = "high_tension_hold"
            reasons.append("sustained_high_tension")
    elif tension_band == "moderate":
        if momentum == "rising":
            state = "rising_scene"
            reasons.append("tension_building")
        elif momentum == "dropping":
            state = "cooling_scene"
            reasons.append("tension_releasing")
        elif abs(emotion_delta) >= 0.20:
            state = "emotional_turn"
            reasons.append("emotion_turning")
        else:
            state = "stable_scene"
            reasons.append("moderate_hold")
    else:
        if prev_tension is not None and momentum == "rising":
            state = "low_tension_reentry"
            reasons.append("low_band_rising")
        elif tone_hint == "dark_irony":
            state = "low_tension_with_irony"
            reasons.append("tone_marker_retention")
        else:
            state = "low_tension_settle"
            reasons.append("low_band_settled")

    if tone_hint in {"dark_irony", "dark", "fearful", "violent"}:
        evidence["critical_tone_present"] = True
    if emotion_intensity >= 0.70:
        evidence["high_emotional_intensity"] = True

    if prev_tension is None:
        state = f"scene_entry_{state}"
        reasons.append("first_segment_context")

    return state, reasons, evidence


def _build_volatility_marker(
    position: int,
    from_segment: Mapping[str, Any],
    segment: Mapping[str, Any],
    valence_delta: float,
    intensity_delta: float,
    tension_delta: float,
    dominance_delta: float,
) -> dict[str, Any]:
    abs_valence_delta = abs(valence_delta)
    abs_intensity_delta = abs(intensity_delta)
    abs_tension_delta = abs(tension_delta)
    abs_dominance_delta = abs(dominance_delta)

    weighted_score = (
        0.45 * abs_valence_delta
        + 0.20 * abs_intensity_delta
        + 0.25 * abs_tension_delta
        + 0.10 * abs_dominance_delta
    )
    volatility_index = min(1.0, round(weighted_score / 1.75, 4))

    volatility_level = (
        "high"
        if volatility_index >= 0.65
        else "moderate" if volatility_index >= 0.35 else "low"
    )
    triggers: list[str] = []
    if abs_valence_delta >= 0.35:
        triggers.append("valence_jump")
    if abs_intensity_delta >= 0.25:
        triggers.append("intensity_jump")
    if abs_tension_delta >= 0.20:
        triggers.append("tension_jump")
    if abs_dominance_delta >= 0.20:
        triggers.append("dominance_jump")

    return {
        "position": position,
        "from_segment_id": from_segment.get("segment_id"),
        "from_chapter_id": from_segment.get("chapter_id"),
        "from_segment_index": from_segment.get("segment_index"),
        "segment_id": segment.get("segment_id"),
        "chapter_id": segment.get("chapter_id"),
        "segment_index": segment.get("segment_index"),
        "volatility_index": volatility_index,
        "level": volatility_level,
        "valence_delta": valence_delta,
        "intensity_delta": intensity_delta,
        "tension_delta": tension_delta,
        "dominance_delta": dominance_delta,
        "triggers": triggers,
        "from_tension": _to_number(_to_dict(from_segment.get("tension_contribution")).get("value")),
        "to_tension": _to_number(_to_dict(segment.get("tension_contribution")).get("value")),
    }


def _build_abrupt_change_hint(
    transition_position: int,
    from_segment: Mapping[str, Any],
    to_segment: Mapping[str, Any],
    volatility_marker: Mapping[str, Any],
) -> dict[str, Any]:
    valence_delta = float(volatility_marker.get("valence_delta", 0.0) or 0.0)
    intensity_delta = float(volatility_marker.get("intensity_delta", 0.0) or 0.0)
    tension_delta = float(volatility_marker.get("tension_delta", 0.0) or 0.0)
    dominance_delta = float(volatility_marker.get("dominance_delta", 0.0) or 0.0)
    volatility_index = float(volatility_marker.get("volatility_index", 0.0) or 0.0)

    fields_to_smooth: list[str] = []
    reasons: list[str] = []
    if abs(valence_delta) >= 0.25:
        fields_to_smooth.append("emotion_valence")
        reasons.append("large_valence_delta")
    if abs(intensity_delta) >= 0.20:
        fields_to_smooth.append("emotion_intensity")
        reasons.append("large_emotion_intensity_delta")
    if abs(tension_delta) >= 0.18:
        fields_to_smooth.append("tension")
        reasons.append("large_tension_delta")
    if abs(dominance_delta) >= 0.18:
        fields_to_smooth.append("dominance")
        reasons.append("large_dominance_delta")

    if not reasons:
        reasons.append("low_transition_volatility")

    severity = (
        "high"
        if volatility_index >= 0.65
        else "moderate" if volatility_index >= 0.35 else "low"
    )
    avoid = severity in {"moderate", "high"}

    return {
        "position": transition_position,
        "from_segment_id": from_segment.get("segment_id"),
        "from_chapter_id": from_segment.get("chapter_id"),
        "from_segment_index": from_segment.get("segment_index"),
        "segment_id": to_segment.get("segment_id"),
        "chapter_id": to_segment.get("chapter_id"),
        "segment_index": to_segment.get("segment_index"),
        "avoid": avoid,
        "severity": severity,
        "volatility_index": volatility_index,
        "fields_to_smooth": fields_to_smooth,
        "reasons": reasons,
        "suggestions": {
            "smoothing_strategy": (
                "micro_crossfade" if avoid else "preserve_raw_tags"
            ),
            "preserve_raw_tags": True,
        },
        "from_raw_tags": {
            "type": from_segment.get("type"),
            "speaker": from_segment.get("speaker"),
            "emotion_primary_label": from_segment.get("emotion_primary_label"),
            "dominance_value": _to_number(_to_dict(from_segment.get("dominance_contribution")).get("value")),
            "tension_value": _to_number(_to_dict(from_segment.get("tension_contribution")).get("value")),
        },
        "to_raw_tags": {
            "type": to_segment.get("type"),
            "speaker": to_segment.get("speaker"),
            "emotion_primary_label": to_segment.get("emotion_primary_label"),
            "dominance_value": _to_number(_to_dict(to_segment.get("dominance_contribution")).get("value")),
            "tension_value": _to_number(_to_dict(to_segment.get("tension_contribution")).get("value")),
        },
        "evidence": {
            "valence_delta": valence_delta,
            "intensity_delta": intensity_delta,
            "tension_delta": tension_delta,
            "dominance_delta": dominance_delta,
        },
    }


def _build_time_series(segments: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    emotion_valence = []
    emotion_intensity = []
    tension = []
    dominance = []
    emotion_delta = []
    scene_states = []
    volatility_markers = []
    abrupt_change_hints: list[dict[str, Any]] = []
    previous_segment = None
    previous_values = {"valence": None, "intensity": None, "tension": None, "dominance": None}
    previous_tension = None

    for position, segment in enumerate(segments, start=1):
        chapter_id = segment.get("chapter_id")
        segment_id = segment.get("segment_id")
        segment_index = segment.get("segment_index")
        timestamped_point = {
            "position": position,
            "chapter_id": chapter_id,
            "segment_index": segment_index,
            "segment_id": segment_id,
        }

        valence = _to_number(segment.get("emotion_valence"))
        intensity = _to_number(segment.get("emotion_intensity"))
        tension_value = _to_number(_to_dict(segment.get("tension_contribution")).get("value"))
        dominance_value = _to_number(_to_dict(segment.get("dominance_contribution")).get("value"))
        summary_tone = str(_to_dict(segment.get("summary_tag")).get("dominant_tone", ""))

        if previous_segment is not None:
            valence_delta = (valence or 0.0) - (previous_values["valence"] or 0.0)
            intensity_delta = (intensity or 0.0) - (previous_values["intensity"] or 0.0)
            tension_delta = (tension_value or 0.0) - (previous_values["tension"] or 0.0)
            dominance_delta = (dominance_value or 0.0) - (previous_values["dominance"] or 0.0)
            previous_tension = previous_values["tension"]
        else:
            valence_delta = 0.0
            intensity_delta = 0.0
            tension_delta = 0.0
            dominance_delta = 0.0
            previous_tension = None

        if previous_segment is not None:
            emotion_delta.append(
                {
                    "position": position,
                    "segment_id": segment_id,
                    "from_segment_id": previous_segment.get("segment_id"),
                    "from_chapter_id": previous_segment.get("chapter_id"),
                    "from_segment_index": previous_segment.get("segment_index"),
                    "chapter_id": chapter_id,
                    "segment_index": segment_index,
                    "valence_delta": valence_delta,
                    "intensity_delta": intensity_delta,
                    "tension_delta": tension_delta,
                    "dominance_delta": dominance_delta,
                }
            )
            volatility_markers.append(
                _build_volatility_marker(
                    position=position,
                    from_segment=previous_segment,
                    segment=segment,
                    valence_delta=valence_delta,
                    intensity_delta=intensity_delta,
                    tension_delta=tension_delta,
                    dominance_delta=dominance_delta,
                )
            )
            abrupt_change_hints.append(
                _build_abrupt_change_hint(
                    transition_position=position,
                    from_segment=previous_segment,
                    to_segment=segment,
                    volatility_marker=volatility_markers[-1],
                )
            )

        scene_state, reasons, evidence = _compute_scene_state(
            segment_position=position,
            emotion_valence=valence or 0.0,
            emotion_intensity=intensity if intensity is not None else 0.0,
            tension_value=tension_value or 0.0,
            dominance_value=dominance_value or 0.0,
            prev_tension=previous_tension,
            emotion_delta=valence_delta,
            tension_delta=tension_delta,
            summary_tone=summary_tone,
        )
        scene_states.append(
            {
                **timestamped_point,
                "state": scene_state,
                "reasons": reasons,
                "evidence": evidence,
            }
        )

        emotion_valence.append({**timestamped_point, "value": valence if valence is not None else 0.0})
        emotion_intensity.append({**timestamped_point, "value": intensity if intensity is not None else 0.0})
        tension.append({**timestamped_point, "value": tension_value if tension_value is not None else 0.0})
        dominance.append({**timestamped_point, "value": dominance_value if dominance_value is not None else 0.0})
        previous_segment = segment
        previous_values["valence"] = valence if valence is not None else 0.0
        previous_values["intensity"] = intensity if intensity is not None else 0.0
        previous_values["tension"] = tension_value if tension_value is not None else 0.0
        previous_values["dominance"] = dominance_value if dominance_value is not None else 0.0

    return {
        "emotion_valence": emotion_valence,
        "emotion_intensity": emotion_intensity,
        "tension": tension,
        "dominance": dominance,
        "emotion_delta": emotion_delta,
        "scene_states": scene_states,
        "volatility_markers": volatility_markers,
        "avoid_abrupt_change_hints": abrupt_change_hints,
    }


def _build_chapter_level_valence_means(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    totals: dict[int, float] = {}
    counts: dict[int, int] = {}

    for segment in segments:
        chapter_id = segment.get("chapter_id")
        if not isinstance(chapter_id, int):
            continue
        valence = _to_number(segment.get("emotion_valence"))
        if valence is None:
            continue
        totals[chapter_id] = totals.get(chapter_id, 0.0) + valence
        counts[chapter_id] = counts.get(chapter_id, 0) + 1

    chapter_level_valence_means = []
    for chapter_id in sorted(totals.keys()):
        count = counts.get(chapter_id, 0)
        if count <= 0:
            continue
        chapter_level_valence_means.append(
            {
                "chapter_id": chapter_id,
                "valence_mean": round(totals[chapter_id] / count, 4),
                "segment_count": count,
            }
        )
    return chapter_level_valence_means


def _build_chapter_level_valence_variance(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    totals: dict[int, float] = {}
    counts: dict[int, int] = {}
    sum_squares: dict[int, float] = {}

    for segment in segments:
        chapter_id = segment.get("chapter_id")
        if not isinstance(chapter_id, int):
            continue
        valence = _to_number(segment.get("emotion_valence"))
        if valence is None:
            continue
        totals[chapter_id] = totals.get(chapter_id, 0.0) + valence
        sum_squares[chapter_id] = sum_squares.get(chapter_id, 0.0) + (valence * valence)
        counts[chapter_id] = counts.get(chapter_id, 0) + 1

    chapter_level_valence_variance = []
    for chapter_id in sorted(totals.keys()):
        count = counts.get(chapter_id, 0)
        if count <= 0:
            continue
        mean = totals[chapter_id] / count
        variance = sum_squares[chapter_id] / count - (mean * mean)
        chapter_level_valence_variance.append(
            {
                "chapter_id": chapter_id,
                "valence_variance": round(max(0.0, variance), 4),
                "segment_count": count,
            }
        )
    return chapter_level_valence_variance


def _build_chapter_level_emotional_volatility_index(
    segments: list[dict[str, Any]],
    volatility_markers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    marker_by_segment_id: dict[str, float] = {}
    for marker in volatility_markers:
        segment_id = marker.get("segment_id")
        if isinstance(segment_id, str):
            marker_by_segment_id[segment_id] = float(marker.get("volatility_index", 0.0) or 0.0)

    totals: dict[int, float] = {}
    counts: dict[int, int] = {}
    for segment in segments:
        chapter_id = segment.get("chapter_id")
        segment_id = segment.get("segment_id")
        if not isinstance(chapter_id, int) or not isinstance(segment_id, str):
            continue
        if segment_id not in marker_by_segment_id:
            continue
        volatility_index = marker_by_segment_id[segment_id]
        totals[chapter_id] = totals.get(chapter_id, 0.0) + volatility_index
        counts[chapter_id] = counts.get(chapter_id, 0) + 1

    chapter_level_emotional_volatility_index = []
    for chapter_id in sorted(totals.keys()):
        count = counts.get(chapter_id, 0)
        if count <= 0:
            continue
        chapter_level_emotional_volatility_index.append(
            {
                "chapter_id": chapter_id,
                "emotional_volatility_index": round(totals[chapter_id] / count, 4),
                "segment_count": count,
            }
        )
    return chapter_level_emotional_volatility_index


def _build_normalized_pacing_signature(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not segments:
        return []

    segment_payloads: list[tuple[int, float, dict[str, Any]]] = []
    max_word_count = 0.0

    for index, segment in enumerate(segments):
        normalized_text = segment.get("normalized_text")
        if not isinstance(normalized_text, str):
            normalized_text = ""
        word_count = float(len(normalized_text.split()))
        max_word_count = max(max_word_count, word_count)
        segment_payloads.append(
            (
                index + 1,
                word_count,
                {
                    "segment_id": segment.get("segment_id"),
                    "chapter_id": segment.get("chapter_id"),
                    "segment_index": segment.get("segment_index"),
                },
            )
        )

    if max_word_count <= 0.0:
        normalized_curve: list[dict[str, Any]] = []
        for position, word_count, segment_meta in segment_payloads:
            normalized_curve.append(
                {
                    "position": position,
                    "signature_value": 0.0,
                    "segment_word_count": round(word_count, 4),
                    **segment_meta,
                }
            )
        return normalized_curve

    normalized_curve: list[dict[str, Any]] = []
    for position, word_count, segment_meta in segment_payloads:
        normalized_curve.append(
            {
                "position": position,
                "signature_value": round(word_count / max_word_count, 6),
                "segment_word_count": round(word_count, 4),
                **segment_meta,
            }
        )

    return normalized_curve


def _build_rolling_emotional_curves(
    segments: list[dict[str, Any]],
    window_size: int,
) -> dict[str, Any]:
    if window_size < 1:
        window_size = 1

    valence_values: list[float] = []
    intensity_values: list[float] = []
    for segment in segments:
        valence_values.append(_to_number(segment.get("emotion_valence")) or 0.0)
        intensity_values.append(_to_number(segment.get("emotion_intensity")) or 0.0)

    rolling_valence = []
    rolling_intensity = []
    for index, segment in enumerate(segments):
        start = max(0, index - window_size + 1)
        valence_window = valence_values[start : index + 1]
        intensity_window = intensity_values[start : index + 1]
        valence_mean = sum(valence_window) / len(valence_window) if valence_window else 0.0
        intensity_mean = (
            sum(intensity_window) / len(intensity_window) if intensity_window else 0.0
        )
        point_meta = {
            "position": index + 1,
            "chapter_id": segment.get("chapter_id"),
            "segment_index": segment.get("segment_index"),
            "segment_id": segment.get("segment_id"),
        }
        rolling_valence.append(
            {
                **point_meta,
                "rolling_mean_valence": round(valence_mean, 4),
            }
        )
        rolling_intensity.append(
            {
                **point_meta,
                "rolling_mean_intensity": round(intensity_mean, 4),
            }
        )

    return {
        "window_size": window_size,
        "valence_curve": rolling_valence,
        "intensity_curve": rolling_intensity,
    }


def _build_chapter_level_raw_tension(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    totals: dict[int, float] = {}
    counts: dict[int, int] = {}

    for segment in segments:
        chapter_id = segment.get("chapter_id")
        if not isinstance(chapter_id, int):
            continue
        tension_value = _to_number(_to_dict(segment.get("tension_contribution")).get("value"))
        if tension_value is None:
            continue
        totals[chapter_id] = totals.get(chapter_id, 0.0) + tension_value
        counts[chapter_id] = counts.get(chapter_id, 0) + 1

    chapter_level_raw_tension = []
    for chapter_id in sorted(totals.keys()):
        count = counts.get(chapter_id, 0)
        if count <= 0:
            continue
        chapter_level_raw_tension.append(
            {
                "chapter_id": chapter_id,
                "raw_tension_mean": round(totals[chapter_id] / count, 4),
                "raw_tension_sum": round(totals[chapter_id], 4),
                "segment_count": count,
            }
        )
    return chapter_level_raw_tension


def _build_smoothed_tension_curve(
    segments: list[dict[str, Any]],
    window_size: int,
) -> dict[str, Any]:
    if window_size < 1:
        window_size = 1

    tension_values: list[float] = []
    for segment in segments:
        tension_values.append(_to_number(_to_dict(segment.get("tension_contribution")).get("value")) or 0.0)

    smoothed_curve: list[dict[str, Any]] = []
    for index, segment in enumerate(segments):
        start = max(0, index - window_size + 1)
        tension_window = tension_values[start : index + 1]
        smoothed_tension = (
            sum(tension_window) / len(tension_window) if tension_window else 0.0
        )
        smoothed_curve.append(
            {
                "position": index + 1,
                "chapter_id": segment.get("chapter_id"),
                "segment_index": segment.get("segment_index"),
                "segment_id": segment.get("segment_id"),
                "smoothed_tension": round(smoothed_tension, 4),
            }
        )

    return {
        "window_size": window_size,
        "tension_curve": smoothed_curve,
    }


def _build_chapter_level_character_dominance(
    segments: list[dict[str, Any]],
    top_characters_limit: int = 3,
) -> list[dict[str, Any]]:
    if top_characters_limit < 1:
        top_characters_limit = 1

    per_chapter: dict[int, dict[str, dict[str, Any]]] = {}
    chapter_segment_counts: dict[int, int] = {}
    chapters_with_segments: list[int] = []

    for segment in segments:
        chapter_id = segment.get("chapter_id")
        if not isinstance(chapter_id, int):
            continue
        if chapter_id not in chapters_with_segments:
            chapters_with_segments.append(chapter_id)

        speaker = segment.get("speaker")
        if not isinstance(speaker, str):
            continue
        normalized_speaker = speaker.strip()
        if not normalized_speaker or normalized_speaker.lower() == "unknown":
            continue

        speaker_id = segment.get("speaker_id")
        normalized_key = normalized_speaker.lower()
        dominance_payload = _to_dict(segment.get("dominance_contribution"))
        if not dominance_payload:
            dominance_payload = _to_dict(segment.get("tag_bundle")).get("dominance", {})
        dominance_value = _to_number(dominance_payload.get("value"))
        if dominance_value is None:
            continue

        per_chapter.setdefault(chapter_id, {})
        chapter_payload = per_chapter[chapter_id]
        if normalized_key not in chapter_payload:
            chapter_payload[normalized_key] = {
                "speaker": normalized_speaker,
                "speaker_id": speaker_id if isinstance(speaker_id, int) else None,
                "segment_count": 0,
                "total_dominance": 0.0,
            }
        speaker_payload = chapter_payload[normalized_key]
        speaker_payload["segment_count"] = int(speaker_payload["segment_count"]) + 1
        speaker_payload["total_dominance"] = float(speaker_payload["total_dominance"]) + dominance_value
        if isinstance(speaker_id, int) and not isinstance(
            speaker_payload.get("speaker_id"), int
        ):
            speaker_payload["speaker_id"] = speaker_id
        chapter_segment_counts[chapter_id] = chapter_segment_counts.get(chapter_id, 0) + 1

    chapter_level_character_dominance = []
    for chapter_id in chapters_with_segments:
        speaker_payloads = per_chapter.get(chapter_id, {})
        if not speaker_payloads:
            chapter_level_character_dominance.append(
                {
                    "chapter_id": chapter_id,
                    "chapter_segment_count": chapter_segment_counts.get(chapter_id, 0),
                    "dominance_total": 0.0,
                    "character_dominance_distribution": [],
                    "key_characters": [],
                }
            )
            continue

        character_dominance_distribution: list[dict[str, Any]] = []
        total_dominance = 0.0
        for payload in speaker_payloads.values():
            total = float(payload["total_dominance"])
            total_dominance += total
        for payload in speaker_payloads.values():
            total = float(payload["total_dominance"])
            segment_count = int(payload["segment_count"])
            character_dominance_distribution.append(
                {
                    "speaker": payload["speaker"],
                    "speaker_id": payload["speaker_id"],
                    "segment_count": segment_count,
                    "total_dominance": round(total, 4),
                    "average_dominance": round(total / segment_count, 4)
                    if segment_count > 0
                    else 0.0,
                    "dominance_share": round(total / total_dominance, 4)
                    if total_dominance > 0
                    else 0.0,
                }
            )

        character_dominance_distribution.sort(
            key=lambda item: (
                -item["total_dominance"],
                -item["segment_count"],
                str(item["speaker"]).lower(),
            )
        )

        chapter_level_character_dominance.append(
            {
                "chapter_id": chapter_id,
                "chapter_segment_count": chapter_segment_counts.get(chapter_id, 0),
                "dominance_total": round(total_dominance, 4),
                "character_dominance_distribution": character_dominance_distribution,
                "key_characters": character_dominance_distribution[:top_characters_limit],
            }
        )

    return chapter_level_character_dominance


def _build_character_cooccurrence_graph(segments: list[dict[str, Any]]) -> dict[str, Any]:
    node_segments: dict[str, dict[str, Any]] = {}
    edges: dict[tuple[str, str], dict[str, Any]] = {}
    previous_speaker: str | None = None
    previous_chapter_id: int | None = None

    for segment in segments:
        chapter_id = segment.get("chapter_id")
        if not isinstance(chapter_id, int):
            continue

        speaker = segment.get("speaker")
        if not isinstance(speaker, str):
            continue
        normalized_speaker = speaker.strip()
        if not normalized_speaker or normalized_speaker.lower() == "unknown":
            previous_speaker = None
            previous_chapter_id = chapter_id
            continue

        speaker_key = normalized_speaker.lower()
        speaker_id = segment.get("speaker_id")
        if not isinstance(speaker_id, int):
            speaker_id = None

        node = node_segments.setdefault(
            speaker_key,
            {
                "character_key": speaker_key,
                "character_label": normalized_speaker,
                "speaker_id": speaker_id,
                "segment_count": 0,
                "chapter_ids": [],
            },
        )
        node["segment_count"] = int(node.get("segment_count", 0)) + 1
        if chapter_id not in node["chapter_ids"]:
            node["chapter_ids"].append(chapter_id)

        if (
            previous_speaker is not None
            and previous_chapter_id == chapter_id
            and previous_speaker != speaker_key
        ):
            source = min(previous_speaker, speaker_key)
            target = max(previous_speaker, speaker_key)
            edge = edges.setdefault(
                (source, target),
                {
                    "source": source,
                    "target": target,
                    "co_occurrence_count": 0,
                    "chapter_ids": [],
                },
            )
            edge["co_occurrence_count"] = int(edge["co_occurrence_count"]) + 1
            if chapter_id not in edge["chapter_ids"]:
                edge["chapter_ids"].append(chapter_id)

        previous_speaker = speaker_key
        previous_chapter_id = chapter_id

    for node in node_segments.values():
        node["chapter_ids"] = sorted(node["chapter_ids"])

    for edge in edges.values():
        edge["chapter_ids"] = sorted(edge["chapter_ids"])

    degree_by_node: dict[str, int] = {key: 0 for key in node_segments}
    for edge in edges.values():
        weight = int(edge["co_occurrence_count"])
        degree_by_node[edge["source"]] = degree_by_node[edge["source"]] + weight
        degree_by_node[edge["target"]] = degree_by_node[edge["target"]] + weight

    nodes: list[dict[str, Any]] = []
    for key in sorted(node_segments):
        node = node_segments[key]
        nodes.append(
            {
                **node,
                "chapter_count": len(node["chapter_ids"]),
                "adjacency_weight": degree_by_node.get(key, 0),
            }
        )

    normalized_edges: list[dict[str, Any]] = []
    for source, target in sorted(edges.keys()):
        edge = edges[(source, target)]
        normalized_edges.append(
            {
                "source": source,
                "target": target,
                "co_occurrence_count": edge["co_occurrence_count"],
                "weight": int(edge["co_occurrence_count"]),
                "chapter_ids": edge["chapter_ids"],
                "chapter_count": len(edge["chapter_ids"]),
            }
        )

    return {
        "nodes": nodes,
        "edges": normalized_edges,
        "metadata": {
            "node_count": len(nodes),
            "edge_count": len(normalized_edges),
            "scope": "adjacent_speaker_transitions_within_chapter",
            "undirected": True,
            "generated_by": "export_academic_graph",
        },
    }


def _build_character_cooccurrence_centrality_table(graph_report: dict[str, Any]) -> dict[str, Any]:
    nodes = [node for node in graph_report.get("nodes", []) if isinstance(node, dict)]
    edges = [edge for edge in graph_report.get("edges", []) if isinstance(edge, dict)]

    if not nodes:
        return {
            "metrics_table": [],
            "metadata": {
                "node_count": 0,
                "edge_count": 0,
                "centrality_metrics": [
                    "degree",
                    "degree_centrality",
                    "weighted_degree",
                    "weighted_degree_centrality",
                    "closeness_centrality",
                    "betweenness_centrality",
                ],
                "generated_by": "export_academic_centrality",
            },
        }

    node_lookup: dict[str, dict[str, Any]] = {}
    node_keys: list[str] = []
    for node in nodes:
        node_key = node.get("character_key")
        if isinstance(node_key, str):
            node_lookup[node_key] = node
            node_keys.append(node_key)

    if not node_keys:
        return {
            "metrics_table": [],
            "metadata": {
                "node_count": 0,
                "edge_count": len(edges),
                "centrality_metrics": [
                    "degree",
                    "degree_centrality",
                    "weighted_degree",
                    "weighted_degree_centrality",
                    "closeness_centrality",
                    "betweenness_centrality",
                ],
                "generated_by": "export_academic_centrality",
            },
        }

    node_set = set(node_keys)
    adjacency: dict[str, dict[str, float]] = {node_key: {} for node_key in node_set}

    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        weight = edge.get("co_occurrence_count", 0)
        if not isinstance(source, str) or not isinstance(target, str):
            continue
        if source not in node_set or target not in node_set or source == target:
            continue

        raw_weight = float(weight) if isinstance(weight, (int, float, str)) else 0.0
        if raw_weight <= 0:
            raw_weight = 0.0
        adjacency[source][target] = adjacency[source].get(target, 0.0) + raw_weight
        adjacency[target][source] = adjacency[target].get(source, 0.0) + raw_weight

    node_count = len(node_set)

    degree: dict[str, int] = {}
    weighted_degree: dict[str, float] = {}
    for node_key in node_keys:
        neighbors = adjacency.get(node_key, {})
        degree[node_key] = len(neighbors)
        weighted_degree[node_key] = round(sum(neighbors.values()), 4)

    closeness_centrality: dict[str, float] = {}
    for start_key in node_keys:
        distances: dict[str, float] = {node_key: inf for node_key in node_keys}
        distances[start_key] = 0.0
        settled: set[str] = set()

        while len(settled) < node_count:
            current_key = None
            current_distance = inf
            for candidate_key, candidate_distance in distances.items():
                if candidate_key in settled or candidate_distance >= current_distance:
                    continue
                current_key = candidate_key
                current_distance = candidate_distance

            if current_key is None or current_distance == inf:
                break

            settled.add(current_key)
            for neighbor_key, raw_weight in adjacency.get(current_key, {}).items():
                if neighbor_key in settled:
                    continue
                distance_through = current_distance + (1.0 / raw_weight if raw_weight > 0 else inf)
                if distance_through < distances[neighbor_key]:
                    distances[neighbor_key] = distance_through

        reachable_distances = [distance for key, distance in distances.items() if key != start_key and distance < inf]
        reachable_count = len(reachable_distances)
        if reachable_count == 0:
            closeness_centrality[start_key] = 0.0
            continue

        closeness_sum = sum(reachable_distances)
        if closeness_sum <= 0:
            closeness_centrality[start_key] = 0.0
            continue
        closeness_centrality[start_key] = round((reachable_count / closeness_sum) * ((reachable_count) / (node_count - 1)), 4)

    betweenness: dict[str, float] = {node_key: 0.0 for node_key in node_keys}
    for source_key in node_keys:
        stack: list[str] = []
        predecessors: dict[str, list[str]] = {node_key: [] for node_key in node_keys}
        sigma: dict[str, float] = {node_key: 0.0 for node_key in node_keys}
        distance: dict[str, float] = {node_key: inf for node_key in node_keys}
        sigma[source_key] = 1.0
        distance[source_key] = 0.0
        queue: list[tuple[float, str]] = [(0.0, source_key)]

        while queue:
            current_distance, current_key = queue.pop(0)
            if current_distance > distance[current_key]:
                continue
            stack.append(current_key)
            for neighbor_key, raw_weight in adjacency.get(current_key, {}).items():
                if raw_weight <= 0:
                    continue
                path_distance = current_distance + (1.0 / raw_weight)
                if path_distance < distance[neighbor_key] - 1e-12:
                    distance[neighbor_key] = path_distance
                    queue.append((path_distance, neighbor_key))
                    queue.sort(key=lambda item: item[0])
                    sigma[neighbor_key] = sigma[current_key]
                    predecessors[neighbor_key] = [current_key]
                elif abs(path_distance - distance[neighbor_key]) <= 1e-12:
                    sigma[neighbor_key] += sigma[current_key]
                    predecessors[neighbor_key].append(current_key)

        dependencies: dict[str, float] = {node_key: 0.0 for node_key in node_keys}
        while stack:
            current_key = stack.pop()
            current_sigma = sigma[current_key]
            for predecessor_key in predecessors[current_key]:
                predecessors_share = sigma[predecessor_key] / current_sigma if current_sigma > 0 else 0.0
                dependencies[predecessor_key] += predecessors_share * (1.0 + dependencies[current_key])
            if current_key != source_key:
                betweenness[current_key] += dependencies[current_key]

    if node_count > 2:
        normalization = 2.0 / ((node_count - 1) * (node_count - 2))
        for node_key in node_keys:
            betweenness[node_key] = round(betweenness[node_key] * normalization, 4)
    else:
        for node_key in node_keys:
            betweenness[node_key] = 0.0

    max_degree_possible = max(node_count - 1, 1)
    max_weight = max(weighted_degree.values()) if weighted_degree else 0.0
    max_weight = max_weight if max_weight > 0 else 1.0

    metrics_table = []
    for node_key in sorted(node_keys):
        total_weight = weighted_degree.get(node_key, 0.0)
        metrics_table.append(
            {
                "character_key": node_key,
                "character_label": node_lookup.get(node_key, {}).get("character_label", node_key),
                "speaker_id": node_lookup.get(node_key, {}).get("speaker_id"),
                "degree": degree.get(node_key, 0),
                "weighted_degree": round(total_weight, 4),
                "degree_centrality": round(degree.get(node_key, 0) / max_degree_possible, 4),
                "weighted_degree_centrality": round(total_weight / max_weight, 4),
                "closeness_centrality": closeness_centrality.get(node_key, 0.0),
                "betweenness_centrality": betweenness.get(node_key, 0.0),
            }
        )

    metrics_table.sort(
        key=lambda row: (
            -row["degree_centrality"],
            -row["weighted_degree"],
            str(row["character_key"]).lower(),
        )
    )

    for index, row in enumerate(metrics_table, start=1):
        row["rank"] = index

    return {
        "metrics_table": metrics_table,
        "metadata": {
            "node_count": node_count,
            "edge_count": len(edges),
            "distance_transform": "inverse_weight",
            "generated_by": "export_academic_centrality",
            "centrality_metrics": [
                "degree",
                "degree_centrality",
                "weighted_degree",
                "weighted_degree_centrality",
                "closeness_centrality",
                "betweenness_centrality",
            ],
        },
    }


def _build_tension_peak_markers(
    smoothed_tension_curve: list[dict[str, Any]],
    major_prominence_threshold: float = 0.18,
    minor_prominence_threshold: float = 0.10,
) -> dict[str, Any]:
    major_peak_count = 0
    minor_peak_count = 0
    peaks: list[dict[str, Any]] = []
    if len(smoothed_tension_curve) < 3:
        return {
            "peaks": peaks,
            "peak_count": 0,
            "major_peak_count": 0,
            "minor_peak_count": 0,
            "prominence_thresholds": {
                "major": major_prominence_threshold,
                "minor": minor_prominence_threshold,
            },
        }

    for position in range(1, len(smoothed_tension_curve) - 1):
        previous_point = smoothed_tension_curve[position - 1]
        current_point = smoothed_tension_curve[position]
        next_point = smoothed_tension_curve[position + 1]

        previous_tension = _to_number(previous_point.get("smoothed_tension"))
        current_tension = _to_number(current_point.get("smoothed_tension"))
        next_tension = _to_number(next_point.get("smoothed_tension"))

        if previous_tension is None or current_tension is None or next_tension is None:
            continue

        is_local_maximum = current_tension > previous_tension and current_tension > next_tension
        if not is_local_maximum:
            continue

        prominence = current_tension - max(previous_tension, next_tension)
        severity: str | None
        if current_tension >= 0.55 and prominence >= major_prominence_threshold:
            severity = "major"
            major_peak_count += 1
        elif current_tension >= 0.40 and prominence >= minor_prominence_threshold:
            severity = "minor"
            minor_peak_count += 1
        else:
            continue

        peaks.append(
            {
                "position": current_point.get("position"),
                "segment_id": current_point.get("segment_id"),
                "chapter_id": current_point.get("chapter_id"),
                "segment_index": current_point.get("segment_index"),
                "peak_type": "tension_peak",
                "severity": severity,
                "prominence": round(prominence, 4),
                "neighbors": {
                    "previous_tension": round(previous_tension, 4),
                    "next_tension": round(next_tension, 4),
                },
                "tension_value": round(current_tension, 4),
            }
        )

    return {
        "peaks": peaks,
        "peak_count": len(peaks),
        "major_peak_count": major_peak_count,
        "minor_peak_count": minor_peak_count,
        "prominence_thresholds": {
            "major": major_prominence_threshold,
            "minor": minor_prominence_threshold,
        },
    }


def _build_tension_plateau_regions(
    smoothed_tension_curve: list[dict[str, Any]],
    flatness_tolerance: float = 0.05,
    min_region_length: int = 3,
) -> dict[str, Any]:
    if min_region_length < 2:
        min_region_length = 2

    regions: list[dict[str, Any]] = []
    points = []
    for point in smoothed_tension_curve:
        if (
            _to_number(point.get("position")) is not None
            and _to_number(point.get("smoothed_tension")) is not None
        ):
            points.append(point)

    if len(points) < min_region_length:
        return {
            "regions": regions,
            "plateau_region_count": 0,
            "flatness_tolerance": flatness_tolerance,
            "min_region_length": min_region_length,
        }

    # Find maximal contiguous runs where adjacent smoothed tension values stay within tolerance.
    start = 0
    while start < len(points):
        end = start + 1
        while (
            end < len(points)
            and abs(
                (_to_number(points[end].get("smoothed_tension")) or 0.0)
                - (_to_number(points[end - 1].get("smoothed_tension")) or 0.0)
            )
            <= flatness_tolerance
        ):
            end += 1

        region_points = points[start:end]
        region_length = len(region_points)
        if region_length >= min_region_length:
            tension_values = [
                float(_to_number(region_point.get("smoothed_tension")) or 0.0)
                for region_point in region_points
            ]
            tension_min = min(tension_values)
            tension_max = max(tension_values)
            average_tension = sum(tension_values) / region_length
            start_point = region_points[0]
            end_point = region_points[-1]
            chapter_ids: list[int] = []
            segment_indices: list[int] = []
            segment_ids: list[str] = []
            for region_point in region_points:
                chapter_id = region_point.get("chapter_id")
                segment_index = region_point.get("segment_index")
                segment_id = region_point.get("segment_id")
                if isinstance(chapter_id, int):
                    if chapter_id not in chapter_ids:
                        chapter_ids.append(chapter_id)
                if isinstance(segment_index, int):
                    segment_indices.append(segment_index)
                if isinstance(segment_id, str):
                    segment_ids.append(segment_id)

            regions.append(
                {
                    "region_type": "tension_plateau",
                    "start_position": start_point.get("position"),
                    "end_position": end_point.get("position"),
                    "length": region_length,
                    "segment_count": region_length,
                    "segment_ids": segment_ids,
                    "segment_indices": segment_indices,
                    "chapter_ids": chapter_ids,
                    "average_tension": round(average_tension, 4),
                    "tension_value_range": {
                        "min": round(tension_min, 4),
                        "max": round(tension_max, 4),
                        "delta": round(tension_max - tension_min, 4),
                    },
                }
            )
        start = end

    return {
        "regions": regions,
        "plateau_region_count": len(regions),
        "flatness_tolerance": flatness_tolerance,
        "min_region_length": min_region_length,
    }


def _csv_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _serialize_csv_record(value: Any) -> str:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, (datetime,)):
        return value.isoformat()
    return json.dumps(value, ensure_ascii=False) if isinstance(value, bool) else str(value)


def _build_segment_csv_row(
    segment: Mapping[str, Any],
    project_id: int,
    run_id: int,
) -> dict[str, str]:
    parent_paragraph = _to_dict(segment.get("parent_paragraph_reference"))
    parent_sentence = _to_dict(segment.get("parent_sentence_reference"))
    original_span_pointer = _to_dict(segment.get("original_span_pointer"))
    tag_bundle = _to_dict(segment.get("tag_bundle"))
    confidence = _to_dict(tag_bundle.get("confidence"))
    emotion = _to_dict(tag_bundle.get("emotion"))
    tension = _to_dict(tag_bundle.get("tension"))
    dominance = _to_dict(tag_bundle.get("dominance"))

    sub_segment_boundaries = segment.get("sub_segment_boundaries", [])
    sub_segment_count = len(sub_segment_boundaries) if isinstance(sub_segment_boundaries, list) else 0

    return {
        "project_id": str(project_id),
        "run_id": str(run_id),
        "segment_id": _csv_cell(segment.get("segment_id")),
        "chapter_id": _csv_cell(segment.get("chapter_id")),
        "chapter_internal_id": _csv_cell(segment.get("chapter_internal_id")),
        "segment_index": _csv_cell(segment.get("segment_index")),
        "type": _csv_cell(segment.get("type")),
        "speaker": _csv_cell(segment.get("speaker")),
        "speaker_id": _csv_cell(segment.get("speaker_id")),
        "gender": _csv_cell(segment.get("gender")),
        "resolved_voice_id": _csv_cell(segment.get("resolved_voice_id")),
        "voice_id": _csv_cell(segment.get("voice_id")),
        "original_text": _csv_cell(segment.get("original_text")),
        "normalized_text": _csv_cell(segment.get("normalized_text")),
        "phonetic_text": _csv_cell(segment.get("phonetic_text")),
        "parent_paragraph_index": _csv_cell(parent_paragraph.get("paragraph_index")),
        "parent_paragraph_id": _csv_cell(parent_paragraph.get("paragraph_id")),
        "parent_sentence_start_index": _csv_cell(parent_sentence.get("sentence_start_index")),
        "parent_sentence_end_index": _csv_cell(parent_sentence.get("sentence_end_index")),
        "type_confidence": _csv_cell(confidence.get("type")),
        "speaker_confidence": _csv_cell(confidence.get("speaker")),
        "emotion_confidence": _csv_cell(confidence.get("emotion")),
        "gender_confidence": _csv_cell(confidence.get("gender")),
        "emotion_valence": _csv_cell(emotion.get("valence")),
        "emotion_intensity": _csv_cell(emotion.get("intensity")),
        "emotion_primary_label": _csv_cell(emotion.get("primary_label")),
        "emotion_secondary_label": _csv_cell(emotion.get("secondary_label")),
        "emotion_state": _csv_cell(emotion.get("state")),
        "emotion_evidence": _csv_cell(emotion.get("evidence")),
        "tension_contribution": _csv_cell(tension),
        "dominance_contribution": _csv_cell(dominance),
        "speaker_evidence": _csv_cell(segment.get("speaker_evidence")),
        "type_evidence": _csv_cell(segment.get("type_evidence")),
        "summary_tag": _csv_cell(segment.get("summary_tag")),
        "original_start_char": _csv_cell(original_span_pointer.get("original_start_char")),
        "original_end_char": _csv_cell(original_span_pointer.get("original_end_char")),
        "normalized_start_char": _csv_cell(original_span_pointer.get("normalized_start_char")),
        "normalized_end_char": _csv_cell(original_span_pointer.get("normalized_end_char")),
        "original_to_normalized_offset_map": _csv_cell(segment.get("original_to_normalized_offset_map")),
        "sub_segment_boundary_count": _csv_cell(sub_segment_count),
        "sub_segment_boundaries": _csv_cell(segment.get("sub_segment_boundaries")),
    }


def _build_academic_csv_rows(
    project: Project,
    run: Run,
    academic_reports: Mapping[str, Any],
    academic_manifest: Mapping[str, Any],
) -> list[dict[str, str]]:
    outputs = academic_manifest.get("outputs")
    output_rows: list[dict[str, str]] = []

    output_rows.append(
        {
            "record_type": "manifest",
            "output_id": "AO-MANIFEST",
            "output_name": "academic_export_manifest",
            "output_status": "available",
            "output_schema": academic_manifest.get("output_schema", "academic_json"),
            "supported_formats": json.dumps(["json"], ensure_ascii=False),
            "available_formats": json.dumps(["json"], ensure_ascii=False),
            "data_key": "academic_export_manifest",
            "record_index": "",
            "record_count": "",
            "record_payload": _serialize_csv_record(dict(academic_manifest)),
            "generated_by": academic_manifest.get("generated_by", "build_run_export"),
            "generated_at": academic_manifest.get("generated_at", ""),
            "status_reason": "",
            "project_id": str(project.id),
            "run_id": str(run.id),
            "run_status": str(run.status),
            "output_order": "0",
        }
    )

    if not isinstance(outputs, list):
        return output_rows

    for index, output in enumerate(outputs, start=1):
        if not isinstance(output, dict):
            continue

        output_id = str(output.get("output_id", ""))
        output_name = str(output.get("output_name", ""))
        supported_formats = _serialize_csv_record(output.get("supported_formats", []))
        available_formats = _serialize_csv_record(output.get("available_formats", []))
        status = str(output.get("status", "unknown"))
        data_keys = output.get("data_keys", [])
        reason = output.get("evidence", {}).get("status_reason") if isinstance(output.get("evidence"), Mapping) else None
        generated_by = output.get("evidence", {}).get("generated_by") if isinstance(output.get("evidence"), Mapping) else None

        output_rows.append(
            {
                "record_type": "output",
                "output_id": output_id,
                "output_name": output_name,
                "output_status": status,
                "output_schema": academic_manifest.get("output_schema", "academic_json"),
                "supported_formats": supported_formats,
                "available_formats": available_formats,
                "data_key": "",
                "record_index": "",
                "record_count": str(len(data_keys)) if isinstance(data_keys, list) else "",
                "record_payload": "",
                "generated_by": str(generated_by or ""),
                "generated_at": academic_manifest.get("generated_at", ""),
                "status_reason": str(reason or ""),
                "project_id": str(project.id),
                "run_id": str(run.id),
                "run_status": str(run.status),
                "output_order": str(index),
            }
        )

        if status != "available":
            continue

        for data_key in data_keys if isinstance(data_keys, list) else []:
            if not isinstance(data_key, str):
                continue
            value = academic_reports.get(data_key)

            if isinstance(value, list):
                for idx, record in enumerate(value):
                    output_rows.append(
                        {
                            "record_type": "data_record",
                            "output_id": output_id,
                            "output_name": output_name,
                            "output_status": status,
                            "output_schema": academic_manifest.get("output_schema", "academic_json"),
                            "supported_formats": supported_formats,
                            "available_formats": available_formats,
                            "data_key": data_key,
                            "record_index": str(idx),
                            "record_count": str(len(value)),
                            "record_payload": _serialize_csv_record(record),
                            "generated_by": str(generated_by or ""),
                            "generated_at": academic_manifest.get("generated_at", ""),
                            "status_reason": "",
                            "project_id": str(project.id),
                            "run_id": str(run.id),
                            "run_status": str(run.status),
                            "output_order": str(index),
                        }
                    )
            else:
                output_rows.append(
                    {
                        "record_type": "data_record",
                        "output_id": output_id,
                        "output_name": output_name,
                        "output_status": status,
                        "output_schema": academic_manifest.get("output_schema", "academic_json"),
                        "supported_formats": supported_formats,
                        "available_formats": available_formats,
                        "data_key": data_key,
                        "record_index": "0",
                        "record_count": "1",
                        "record_payload": _serialize_csv_record(value),
                        "generated_by": str(generated_by or ""),
                        "generated_at": academic_manifest.get("generated_at", ""),
                        "status_reason": "",
                        "project_id": str(project.id),
                        "run_id": str(run.id),
                        "run_status": str(run.status),
                        "output_order": str(index),
                    }
                )

    return output_rows


def build_run_export_academic_csv(
    project: Project,
    run: Run,
    academic_reports: Mapping[str, Any],
    academic_manifest: Mapping[str, Any],
) -> str:
    rows = _build_academic_csv_rows(
        project=project,
        run=run,
        academic_reports=academic_reports,
        academic_manifest=academic_manifest,
    )

    fieldnames = [
        "record_type",
        "output_order",
        "output_id",
        "output_name",
        "output_status",
        "output_schema",
        "supported_formats",
        "available_formats",
        "data_key",
        "record_index",
        "record_count",
        "record_payload",
        "status_reason",
        "generated_by",
        "generated_at",
        "project_id",
        "run_id",
        "run_status",
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return output.getvalue()


def build_run_export_graph_json(
    project: Project,
    run: Run,
    academic_reports: Mapping[str, Any],
    academic_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    graph_report = _to_dict(academic_reports.get("character_cooccurrence_graph"))
    centrality_report = _to_dict(academic_reports.get("character_cooccurrence_centrality_table"))
    generated_at = academic_manifest.get("generated_at", datetime.now(timezone.utc).isoformat())
    schema_version = "1.0.0"

    graph_payload = {
        "nodes": [node for node in _to_dict(graph_report).get("nodes", []) if isinstance(node, dict)],
        "edges": [edge for edge in _to_dict(graph_report).get("edges", []) if isinstance(edge, dict)],
        "metadata": _to_dict(graph_report).get("metadata", {}),
    }
    centrality_payload = {
        "metrics_table": [
            row for row in _to_dict(centrality_report).get("metrics_table", []) if isinstance(row, dict)
        ],
        "metadata": _to_dict(centrality_report).get("metadata", {}),
    }

    return {
        "schema_version": schema_version,
        "output_schema": "graph_json",
        "output_format": "graph_json",
        "output_id": "AO-004",
        "output_name": "character_cooccurrence_graph",
        "project_id": project.id,
        "run_id": run.id,
        "run_status": run.status,
        "generated_at": generated_at,
        "generated_by": "build_run_export_graph_json",
        "graph": graph_payload,
        "character_cooccurrence_centrality": centrality_payload,
        "manifest_snapshot": {
            "output_schema": academic_manifest.get("output_schema"),
            "generated_by": academic_manifest.get("generated_by"),
        },
    }


def build_run_export_csv(
    session: Session,
    project: Project,
    run: Run,
    from_chapter_index: int | None = None,
    from_segment_index: int | None = None,
) -> str:
    rows = session.execute(
        _build_segment_rows_query(run.id, from_chapter_index, from_segment_index)
    ).scalars()

    segments = [_normalize_segment_for_export(row) for row in list(rows)]
    if not segments:
        return ""

    fieldnames = [
        "project_id",
        "run_id",
        "segment_id",
        "chapter_id",
        "chapter_internal_id",
        "segment_index",
        "type",
        "speaker",
        "speaker_id",
        "gender",
        "resolved_voice_id",
        "voice_id",
        "original_text",
        "normalized_text",
        "phonetic_text",
        "parent_paragraph_index",
        "parent_paragraph_id",
        "parent_sentence_start_index",
        "parent_sentence_end_index",
        "type_confidence",
        "speaker_confidence",
        "emotion_confidence",
        "gender_confidence",
        "emotion_valence",
        "emotion_intensity",
        "emotion_primary_label",
        "emotion_secondary_label",
        "emotion_state",
        "emotion_evidence",
        "tension_contribution",
        "dominance_contribution",
        "speaker_evidence",
        "type_evidence",
        "summary_tag",
        "original_start_char",
        "original_end_char",
        "normalized_start_char",
        "normalized_end_char",
        "original_to_normalized_offset_map",
        "sub_segment_boundary_count",
        "sub_segment_boundaries",
    ]

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for segment in segments:
        writer.writerow(_build_segment_csv_row(segment, project_id=project.id, run_id=run.id))
    return output.getvalue()


def build_run_export(
    session: Session,
    project: Project,
    run: Run,
    from_chapter_index: int | None = None,
    from_segment_index: int | None = None,
) -> dict:
    generated_at = run.finished_at or run.started_at or datetime.now(timezone.utc)
    academic_export_formats = _resolve_allowed_export_formats_from_run_config(run.config_json)
    total_segments = session.query(Segment).filter(Segment.run_id == run.id).count()
    rows = session.execute(
        _build_segment_rows_query(run.id, from_chapter_index, from_segment_index)
    ).scalars()

    segments = [_normalize_segment_for_export(row) for row in list(rows)]
    time_series = _build_time_series(segments)
    smoothed_tension_curve = _build_smoothed_tension_curve(
        segments=segments,
        window_size=5,
    )
    monotony_findings = _build_monotony_risk_findings(
        segments=segments,
        smoothed_tension_curve=smoothed_tension_curve.get("tension_curve", []),
    )
    emotional_monotony_findings = _build_emotional_monotony_findings(segments=segments)
    chapter_level_character_dominance = _build_chapter_level_character_dominance(
        segments=segments,
        top_characters_limit=3,
    )
    character_dominance_findings = _build_character_dominance_findings(
        chapter_level_character_dominance=chapter_level_character_dominance,
    )
    disappearing_character_findings = _build_disappearing_character_findings(segments=segments)
    dialogue_density_findings = _build_dialogue_density_anomaly_findings(segments=segments)
    chapter_type_classification = _build_chapter_type_classification(segments=segments)
    character_cooccurrence_graph = _build_character_cooccurrence_graph(segments=segments)
    character_cooccurrence_centrality_table = _build_character_cooccurrence_centrality_table(
        graph_report=character_cooccurrence_graph,
    )
    ordered_by = ["chapter_index", "segment_index"]
    comparative_run_metrics_snapshot = _build_comparative_run_metrics_snapshot(
        project=project,
        run=run,
        segments=segments,
        ordered_by=ordered_by,
    )
    llm_calls = _load_run_llm_calls(session, run)
    ingestion_log = dict(project.ingestion_log_json or {})
    academic_reports = {
        "chapter_level_valence_means": _build_chapter_level_valence_means(segments),
        "chapter_level_valence_variance": _build_chapter_level_valence_variance(segments),
        "chapter_level_emotional_volatility_index": _build_chapter_level_emotional_volatility_index(
            segments=segments,
            volatility_markers=time_series["volatility_markers"],
        ),
        "chapter_level_character_dominance": chapter_level_character_dominance,
        "normalized_pacing_signature": _build_normalized_pacing_signature(segments=segments),
        "character_cooccurrence_graph": character_cooccurrence_graph,
        "character_cooccurrence_centrality_table": character_cooccurrence_centrality_table,
        "chapter_level_raw_tension": _build_chapter_level_raw_tension(segments),
        "smoothed_tension_curve": smoothed_tension_curve,
        "tension_peak_markers": _build_tension_peak_markers(
            smoothed_tension_curve=smoothed_tension_curve.get("tension_curve", []),
            major_prominence_threshold=0.18,
            minor_prominence_threshold=0.10,
        ),
        "tension_plateau_regions": _build_tension_plateau_regions(
            smoothed_tension_curve=smoothed_tension_curve.get("tension_curve", []),
            flatness_tolerance=0.05,
            min_region_length=3,
        ),
        "rolling_window_emotional_curves": _build_rolling_emotional_curves(
            segments=segments,
            window_size=5,
        ),
        "comparative_run_metrics_snapshot": comparative_run_metrics_snapshot,
    }
    manifest = {
        "schema_version": "1.0.0",
        "export_type": "audiobook_tts_package",
        "export_format": "json",
        "generated_at": generated_at.isoformat(),
        "project": {
            "id": project.id,
            "title": project.title,
            "configuration_snapshot_id": project.configuration_snapshot_id,
            "selected_mode": project.selected_mode,
        },
        "project_config_snapshot": _build_project_config_snapshot(project),
        "run": {
            "id": run.id,
            "status": run.status,
            "config_snapshot": _sanitize_run_config_for_export(run.config_json),
        },
        "segment_count": len(segments),
        "ordered_by": ordered_by,
        "logs": {
            "ingestion_log": ingestion_log,
            "llm_calls": llm_calls,
        },
        "narrative_health_report": _build_author_narrative_health_report(
            project=project,
            run=run,
            generated_at=generated_at,
            segment_count=len(segments),
            monotony_findings=monotony_findings,
            emotional_monotony_findings=emotional_monotony_findings,
            character_dominance_findings=character_dominance_findings,
            disappearing_character_findings=disappearing_character_findings,
            dialogue_density_findings=dialogue_density_findings,
            chapter_type_classification=chapter_type_classification,
        ),
        "reports": _build_export_reports(
            project=project,
            run=run,
            segment_count=len(segments),
            ordered_by=ordered_by,
        ),
        "academic_reports": academic_reports,
        "academic_export_manifest": _build_academic_export_manifest(
            project=project,
            run=run,
            academic_reports=academic_reports,
            generated_at=generated_at,
            allowed_export_formats=academic_export_formats,
        ),
    }

    return {
        "project_id": project.id,
        "project_title": project.title,
        "run_id": run.id,
        "status": run.status,
        "manifest": manifest,
        "segments": segments,
        "time_series": time_series,
        "cursor": {
            "from_chapter_index": from_chapter_index,
            "from_segment_index": from_segment_index,
            "returned_segment_count": len(segments),
            "total_segment_count": total_segments,
            "has_more_segments": len(segments) < total_segments,
            "next_resume_from": None
            if not segments
            else {
                "chapter_index": segments[-1].get("chapter_id"),
                "segment_index": segments[-1].get("segment_index"),
            },
        },
    }
