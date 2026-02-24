#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


MALE_PRONOUNS = ["he", "him", "his"]
FEMALE_PRONOUNS = ["she", "her", "hers"]

MALE_TITLES = ["king", "lord", "sir", "patriarch", "father"]
FEMALE_TITLES = ["queen", "lady", "madam", "princess", "mother"]


@dataclass(frozen=True)
class GenderScores:
    male: float = 0.0
    female: float = 0.0


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
            if sid and mode:
                labels[sid] = mode
    return labels


def compile_alias_regex(aliases: Iterable[str]) -> re.Pattern:
    ordered = sorted(set(aliases), key=len, reverse=True)
    escaped = [re.escape(alias) for alias in ordered if alias]
    pattern = r"\b(?:" + "|".join(escaped) + r")\b"
    return re.compile(pattern, re.IGNORECASE)


def _select_non_overlapping(matches: list[re.Match]) -> list[re.Match]:
    kept: list[re.Match] = []
    for match in matches:
        span = match.span()
        contained = False
        for other in matches:
            if other is match:
                continue
            if other.span()[0] <= span[0] and other.span()[1] >= span[1]:
                if other.span() != span:
                    contained = True
                    break
        if not contained:
            kept.append(match)
    return kept


def _should_count_pronouns(sid: str, labels: dict[str, str] | None, interrupted_by: set[str]) -> bool:
    if labels and sid in labels:
        mode = labels[sid]
        return mode == "EXTERNAL_SPEECH"
    return sid not in interrupted_by


def _add_evidence(evidence: dict[tuple[str, str], dict], ev_type: str, value: str, gender: str) -> None:
    key = (ev_type, value)
    if key not in evidence:
        evidence[key] = {"type": ev_type, "value": value, "gender": gender}


def resolve_chapter_blocks(
    chapter_payload: dict,
    blocks_payload: dict,
    alias_to_gender: dict[str, str],
    alias_to_canonical: dict[str, list[str] | str],
    alias_to_speaker: dict[str, bool],
    labels: dict[str, str] | None = None,
) -> dict:
    sentences = chapter_payload.get("sentences") or []
    sid_to_text = {entry["sid"]: entry["text"] for entry in sentences}

    alias_regex = compile_alias_regex(alias_to_canonical.keys())
    male_pronoun_re = re.compile(r"\b(?:" + "|".join(MALE_PRONOUNS) + r")\b", re.IGNORECASE)
    female_pronoun_re = re.compile(r"\b(?:" + "|".join(FEMALE_PRONOUNS) + r")\b", re.IGNORECASE)
    male_title_re = re.compile(r"\b(?:" + "|".join(MALE_TITLES) + r")\b", re.IGNORECASE)
    female_title_re = re.compile(r"\b(?:" + "|".join(FEMALE_TITLES) + r")\b", re.IGNORECASE)

    resolved_blocks = []
    last_gender = "unknown"
    last_confidence = 0.0

    for block in blocks_payload.get("blocks", []):
        block_sids = list(block.get("sids", []))
        interrupted_by = set(block.get("interrupted_by", []))
        span_sids = []
        in_span = False
        for entry in sentences:
            sid = entry["sid"]
            if sid == block.get("span_start_sid"):
                in_span = True
            if in_span:
                span_sids.append(sid)
            if sid == block.get("span_end_sid"):
                if in_span:
                    break

        male_score = 0.0
        female_score = 0.0
        evidence_map: dict[tuple[str, str], dict] = {}

        for sid in span_sids:
            text = sid_to_text.get(sid, "")
            if not text:
                continue

            matches = list(alias_regex.finditer(text))
            matches = _select_non_overlapping(matches)
            for match in matches:
                alias_text = match.group(0)
                alias_key = alias_text.lower()
                if not alias_to_speaker.get(alias_key, False):
                    continue
                gender = alias_to_gender.get(alias_key)
                if gender == "male":
                    male_score += 3.0
                    _add_evidence(evidence_map, "name", alias_text, "male")
                elif gender == "female":
                    female_score += 3.0
                    _add_evidence(evidence_map, "name", alias_text, "female")

            if _should_count_pronouns(sid, labels, interrupted_by):
                for m in male_pronoun_re.finditer(text):
                    male_score += 1.0
                    _add_evidence(evidence_map, "pronoun", m.group(0).lower(), "male")
                for m in female_pronoun_re.finditer(text):
                    female_score += 1.0
                    _add_evidence(evidence_map, "pronoun", m.group(0).lower(), "female")

            for m in male_title_re.finditer(text):
                male_score += 0.5
                _add_evidence(evidence_map, "title", m.group(0).lower(), "male")
            for m in female_title_re.finditer(text):
                female_score += 0.5
                _add_evidence(evidence_map, "title", m.group(0).lower(), "female")

        resolved_gender = "unknown"
        confidence = 0.0
        conflict = male_score > 0 and female_score > 0

        if male_score == 0 and female_score == 0:
            resolved_gender = "unknown"
            confidence = 0.0
        elif male_score > 0 and female_score == 0:
            resolved_gender = "male"
            confidence = min(1.0, male_score / (male_score + 1.0))
        elif female_score > 0 and male_score == 0:
            resolved_gender = "female"
            confidence = min(1.0, female_score / (female_score + 1.0))
        else:
            if last_gender != "unknown" and last_confidence >= 0.6:
                resolved_gender = last_gender
                confidence = max(0.0, last_confidence - 0.2)
                _add_evidence(evidence_map, "conflict", "inertia", resolved_gender)
            else:
                resolved_gender = "unknown"
                confidence = 0.0

        if resolved_gender != "unknown":
            last_gender = resolved_gender
            last_confidence = confidence

        resolved_block = dict(block)
        resolved_block["resolved_gender"] = resolved_gender
        resolved_block["gender_confidence"] = round(float(confidence), 4)
        resolved_block["gender_evidence"] = list(evidence_map.values())
        resolved_blocks.append(resolved_block)

    return {
        "chapter": blocks_payload.get("chapter"),
        "source_file": blocks_payload.get("source_file"),
        "blocks": resolved_blocks,
    }
