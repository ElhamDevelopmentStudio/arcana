#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


DEFAULT_THRESHOLDS = {
    "min_segments": 5,
    "max_short_ratio": 0.25,
    "max_transition_density": 0.65,
    "min_avg_chars": 40,
    "max_empty_segments": 0,
}


@dataclass(frozen=True)
class PreflightResult:
    report: dict
    violations: list[str]


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_thresholds(path: Path | None) -> dict:
    thresholds = dict(DEFAULT_THRESHOLDS)
    if path and path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                thresholds.update({k: data[k] for k in data if k in thresholds})
        except Exception:
            pass
    return thresholds


def _segment_stats(segments: list[dict]) -> dict:
    lengths = [len(seg.get("text") or "") for seg in segments]
    total = len(segments)
    min_len = min(lengths) if lengths else 0
    max_len = max(lengths) if lengths else 0
    avg_len = sum(lengths) / total if total else 0.0
    short = [seg for seg, ln in zip(segments, lengths) if ln < 20]
    empty = [seg for seg, ln in zip(segments, lengths) if ln == 0]
    speaker_counts: dict[str, int] = {}
    gender_counts: dict[str, int] = {}
    for seg in segments:
        speaker = seg.get("speaker_role") or seg.get("speaker") or "unknown"
        gender = seg.get("speaker_gender") or "unknown"
        speaker_counts[speaker] = speaker_counts.get(speaker, 0) + 1
        gender_counts[gender] = gender_counts.get(gender, 0) + 1
    transitions = 0
    for prev, cur in zip(segments, segments[1:]):
        prev_role = prev.get("speaker_role") or prev.get("speaker")
        cur_role = cur.get("speaker_role") or cur.get("speaker")
        prev_gender = prev.get("speaker_gender")
        cur_gender = cur.get("speaker_gender")
        if prev_role != cur_role or prev_gender != cur_gender:
            transitions += 1
    transition_density = transitions / max(1, total - 1)
    dialogue_segments = [
        seg
        for seg in segments
        if (seg.get("speaker_role") or seg.get("speaker")) not in {"narrator", "internal_thought"}
    ]
    dialogue_ratio = len(dialogue_segments) / total if total else 0.0
    return {
        "total": total,
        "min_chars": min_len,
        "max_chars": max_len,
        "avg_chars": round(avg_len, 2),
        "short_segments": len(short),
        "short_ratio": round(len(short) / total, 3) if total else 0.0,
        "empty_segments": len(empty),
        "speaker_counts": speaker_counts,
        "gender_counts": gender_counts,
        "transitions": transitions,
        "transition_density": round(transition_density, 3),
        "dialogue_ratio": round(dialogue_ratio, 3),
    }


def evaluate_thresholds(report: dict, thresholds: dict) -> list[str]:
    stats = report.get("stats", {})
    violations: list[str] = []
    if stats.get("total", 0) < thresholds.get("min_segments", 0):
        violations.append("min_segments")
    if stats.get("short_ratio", 0.0) > thresholds.get("max_short_ratio", 1.0):
        violations.append("short_ratio")
    if stats.get("transition_density", 0.0) > thresholds.get("max_transition_density", 1.0):
        violations.append("transition_density")
    if stats.get("avg_chars", 0.0) < thresholds.get("min_avg_chars", 0.0):
        violations.append("avg_chars")
    if stats.get("empty_segments", 0) > thresholds.get("max_empty_segments", 0):
        violations.append("empty_segments")
    return violations


def run_preflight(segments_path: Path, thresholds: dict | None = None) -> PreflightResult:
    payload = load_json(segments_path)
    segments = payload.get("segments") or []
    chapter = payload.get("chapter")
    stats = _segment_stats(segments)
    report = {
        "chapter": chapter,
        "source_file": payload.get("source_file"),
        "segment_count": stats.get("total", 0),
        "stats": stats,
    }
    thresholds = thresholds or dict(DEFAULT_THRESHOLDS)
    violations = evaluate_thresholds(report, thresholds)
    report["thresholds"] = thresholds
    report["violations"] = violations
    return PreflightResult(report=report, violations=violations)
