#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


LABELS = {"NARRATION", "INTERNAL_THOUGHT", "EXTERNAL_SPEECH"}
MAX_CHARS = 900
MAX_SENTENCES = 4


@dataclass(frozen=True)
class Segment:
    segment_id: str
    speaker: str
    sids: list[str]
    text: str


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_labels(labels_path: Path) -> dict[str, str]:
    labels: dict[str, str] = {}
    with labels_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            entry = json.loads(line)
            sid = entry.get("sid")
            mode = entry.get("mode")
            if sid and mode in LABELS:
                labels[sid] = mode
    return labels


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


def mode_for_sid(
    sid: str,
    labels: dict[str, str] | None,
    preds: dict[str, dict[str, float]],
) -> str:
    if labels and sid in labels:
        return labels[sid]
    probs = preds.get(sid)
    if not probs:
        return "NARRATION"
    return max(probs.items(), key=lambda kv: kv[1])[0]


def build_block_lookup(blocks_payload: dict, sentences: list[dict]) -> dict[str, dict]:
    sid_to_block: dict[str, dict] = {}
    blocks = blocks_payload.get("blocks", [])
    sid_sequence = [entry["sid"] for entry in sentences]
    sid_to_index = {sid: idx for idx, sid in enumerate(sid_sequence)}

    for block in blocks:
        start_sid = block.get("span_start_sid")
        end_sid = block.get("span_end_sid")
        if start_sid not in sid_to_index or end_sid not in sid_to_index:
            continue
        start_idx = sid_to_index[start_sid]
        end_idx = sid_to_index[end_sid]
        if end_idx < start_idx:
            start_idx, end_idx = end_idx, start_idx
        for sid in sid_sequence[start_idx : end_idx + 1]:
            sid_to_block[sid] = block
    return sid_to_block


def assemble_text(sentences: list[str]) -> str:
    if not sentences:
        return ""
    text = sentences[0]
    for prev, cur in zip(sentences, sentences[1:]):
        if prev.endswith("\n"):
            text += cur
        else:
            text += " " + cur
    return text


def is_section_header(text: str) -> bool:
    if not text:
        return False
    stripped = text.strip()
    if not stripped:
        return False
    if stripped.isupper():
        return True
    if stripped.endswith(":") and len(stripped) <= 60 and stripped.count(" ") <= 6:
        return True
    return False


def is_strong_boundary(text: str) -> bool:
    stripped = text.lstrip()
    if stripped.startswith("Chapter") or stripped.startswith("CHAPTER"):
        return True
    if text.endswith("\n\n"):
        return True
    return is_section_header(text)


def build_segments(
    chapter_payload: dict,
    blocks_payload: dict,
    preds: dict[str, dict[str, float]],
    labels: dict[str, str] | None,
) -> dict:
    sentences = chapter_payload.get("sentences") or []
    sid_to_text = {entry["sid"]: entry["text"] for entry in sentences}
    sid_sequence = [entry["sid"] for entry in sentences]

    sid_to_block = build_block_lookup(blocks_payload, sentences)

    segments: list[Segment] = []
    current_speaker = None
    current_sids: list[str] = []
    current_texts: list[str] = []
    current_text_len = 0

    for sid in sid_sequence:
        mode = mode_for_sid(sid, labels, preds)
        if mode in {"NARRATION", "INTERNAL_THOUGHT"}:
            speaker = "narrator"
        else:
            block = sid_to_block.get(sid)
            if not block:
                speaker = "narrator"
            else:
                resolved = block.get("resolved_gender")
                if resolved == "male":
                    speaker = "male"
                elif resolved == "female":
                    speaker = "female"
                else:
                    speaker = "narrator"

        sentence_text = sid_to_text.get(sid, "")
        boundary = is_strong_boundary(sentence_text)

        if current_speaker is None:
            current_speaker = speaker

        def finalize_segment():
            nonlocal current_sids, current_texts, current_text_len, current_speaker
            if not current_sids:
                return
            segment_id = f"{chapter_payload.get('chapter')}-S{len(segments)+1:04d}"
            segments.append(
                Segment(
                    segment_id=segment_id,
                    speaker=current_speaker,
                    sids=current_sids,
                    text=assemble_text(current_texts),
                )
            )
            current_sids = []
            current_texts = []
            current_text_len = 0

        if speaker != current_speaker and current_sids:
            finalize_segment()
            current_speaker = speaker

        if boundary and current_sids:
            finalize_segment()

        if current_texts:
            sep_len = 0 if current_texts[-1].endswith("\n") else 1
            projected_len = current_text_len + sep_len + len(sentence_text)
        else:
            projected_len = len(sentence_text)

        if current_sids and (
            projected_len > MAX_CHARS or len(current_sids) >= MAX_SENTENCES
        ):
            finalize_segment()

        current_sids.append(sid)
        current_texts.append(sentence_text)
        if len(current_texts) == 1:
            current_text_len = len(sentence_text)
        else:
            current_text_len = projected_len

        if boundary:
            finalize_segment()

    if current_sids:
        segment_id = f"{chapter_payload.get('chapter')}-S{len(segments)+1:04d}"
        segments.append(
            Segment(
                segment_id=segment_id,
                speaker=current_speaker,
                sids=current_sids,
                text=assemble_text(current_texts),
            )
        )

    return {
        "chapter": chapter_payload.get("chapter"),
        "source_file": chapter_payload.get("source_file"),
        "segments": [segment.__dict__ for segment in segments],
    }
