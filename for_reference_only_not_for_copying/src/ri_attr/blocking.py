#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Thresholds:
    speech_strong: float = 0.36
    speech_weak: float = 0.33
    non_speech_strong: float = 0.38
    max_gap: int = 3
    min_speech_sids: int = 2


def load_preds(preds_path: Path) -> dict[str, dict[str, float]]:
    preds: dict[str, dict[str, float]] = {}
    with preds_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            entry = json.loads(line)
            sid = entry.get("sid")
            probs = entry.get("probs")
            if sid and isinstance(probs, dict):
                preds[sid] = probs
    return preds


def load_labels(labels_path: Path) -> dict[str, str]:
    labels: dict[str, str] = {}
    with labels_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            entry = json.loads(line)
            sid = entry.get("sid")
            mode = entry.get("mode")
            if sid and mode:
                labels[sid] = mode
    return labels


def _override_probs(mode: str) -> dict[str, float]:
    if mode == "EXTERNAL_SPEECH":
        return {"NARRATION": 0.0, "INTERNAL_THOUGHT": 0.0, "EXTERNAL_SPEECH": 1.0}
    if mode == "INTERNAL_THOUGHT":
        return {"NARRATION": 0.0, "INTERNAL_THOUGHT": 1.0, "EXTERNAL_SPEECH": 0.0}
    return {"NARRATION": 1.0, "INTERNAL_THOUGHT": 0.0, "EXTERNAL_SPEECH": 0.0}


def _get_probs(
    sid: str,
    preds: dict[str, dict[str, float]],
    labels: dict[str, str] | None,
    use_labels: bool,
) -> dict[str, float]:
    if use_labels and labels and sid in labels:
        return _override_probs(labels[sid])
    return preds.get(
        sid,
        {"NARRATION": 0.0, "INTERNAL_THOUGHT": 0.0, "EXTERNAL_SPEECH": 0.0},
    )


def build_blocks_for_chapter(
    chapter_path: Path,
    preds: dict[str, dict[str, float]],
    labels: dict[str, str] | None,
    thresholds: Thresholds,
    use_labels: bool = True,
) -> dict:
    payload = json.loads(chapter_path.read_text(encoding="utf-8"))
    chapter = payload.get("chapter")
    source_file = payload.get("source_file")
    sentences = payload.get("sentences") or []

    sids = [entry["sid"] for entry in sentences]
    probs_list = [
        _get_probs(sid, preds, labels, use_labels) for sid in sids
    ]

    missing = Counter()
    for sid, probs in zip(sids, probs_list):
        if not probs or sum(probs.values()) == 0.0:
            missing["missing_preds"] += 1
    if missing["missing_preds"]:
        print(f"[WARN] {chapter_path.name}: {missing['missing_preds']} sids missing predictions")

    blocks = []
    in_block = False
    current_sids: list[str] = []
    interrupted_by: list[str] = []
    gap_count = 0
    span_start_sid = None
    span_end_sid = None

    def finalize_block():
        nonlocal current_sids, interrupted_by, in_block, gap_count, span_start_sid, span_end_sid
        if len(current_sids) >= thresholds.min_speech_sids:
            block_id = f"{chapter}-B{len(blocks)+1:04d}"
            blocks.append(
                {
                    "block_id": block_id,
                    "span_start_sid": span_start_sid,
                    "span_end_sid": span_end_sid,
                    "sids": current_sids,
                    "interrupted_by": interrupted_by,
                    "notes": "",
                }
            )
        in_block = False
        current_sids = []
        interrupted_by = []
        gap_count = 0
        span_start_sid = None
        span_end_sid = None

    for idx, sid in enumerate(sids):
        probs = probs_list[idx]
        pS = probs.get("EXTERNAL_SPEECH", 0.0)
        pN = probs.get("NARRATION", 0.0)
        pT = probs.get("INTERNAL_THOUGHT", 0.0)
        p_non_speech = max(pN, pT)

        if not in_block:
            if pS >= thresholds.speech_strong:
                left_ok = idx > 0 and probs_list[idx - 1].get("EXTERNAL_SPEECH", 0.0) >= thresholds.speech_weak
                right_ok = idx + 1 < len(sids) and probs_list[idx + 1].get("EXTERNAL_SPEECH", 0.0) >= thresholds.speech_weak
                if left_ok or right_ok:
                    in_block = True
                    span_start_sid = sid
                    if pS >= thresholds.speech_weak:
                        current_sids.append(sid)
                        gap_count = 0
                    else:
                        interrupted_by.append(sid)
                        gap_count = 1
                    span_end_sid = sid
            continue

        if pS >= thresholds.speech_weak:
            current_sids.append(sid)
            gap_count = 0
        elif p_non_speech >= thresholds.non_speech_strong:
            interrupted_by.append(sid)
            gap_count += 1
        else:
            interrupted_by.append(sid)
            gap_count += 1
        span_end_sid = sid

        if gap_count >= thresholds.max_gap:
            finalize_block()

    if in_block:
        finalize_block()

    return {
        "chapter": chapter,
        "source_file": source_file,
        "thresholds": {
            "speech_strong": thresholds.speech_strong,
            "speech_weak": thresholds.speech_weak,
            "non_speech_strong": thresholds.non_speech_strong,
            "max_gap": thresholds.max_gap,
            "min_speech_sids": thresholds.min_speech_sids,
        },
        "blocks": blocks,
    }


def iter_chapter_files(sentences_dir: Path) -> Iterable[Path]:
    def _chapter_num(path: Path) -> int:
        match = re.match(r"chapter_(\d+)\.json$", path.name)
        return int(match.group(1)) if match else 0

    return sorted(sentences_dir.glob("chapter_*.json"), key=_chapter_num)
