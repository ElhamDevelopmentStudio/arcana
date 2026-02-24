#!/usr/bin/env python3
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from rapidfuzz import fuzz


@dataclass(frozen=True)
class AlignmentResult:
    start_sec: float
    end_sec: float
    score: float
    matched_words: int
    total_words: int


def _normalize_word(word: str) -> str:
    return re.sub(r"[^a-z0-9']+", "", word.lower())


def _tokenize(text: str) -> list[str]:
    return [_normalize_word(w) for w in text.split() if _normalize_word(w)]


def _compact_words(words: Iterable[str]) -> str:
    return " ".join([w for w in words if w])


def _best_alignment(transcript_tokens: list[str], target_tokens: list[str]) -> tuple[tuple[int, int] | None, float]:
    if not transcript_tokens or not target_tokens:
        return None, -1.0
    target_str = _compact_words(target_tokens)
    best_score = -1.0
    best_range = None
    max_window = int(len(target_tokens) * 1.6) + 3
    for i in range(len(transcript_tokens)):
        for j in range(i + 1, min(len(transcript_tokens) + 1, i + max_window + 1)):
            window_tokens = transcript_tokens[i:j]
            window_str = _compact_words(window_tokens)
            if not window_str:
                continue
            score = float(fuzz.ratio(window_str, target_str))
            if score > best_score:
                best_score = score
                best_range = (i, j)
    return best_range, best_score


class WhisperAligner:
    def __init__(self, model_name: str, device: str = "cpu", compute_type: str = "int8") -> None:
        try:
            from faster_whisper import WhisperModel  # type: ignore
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "Missing dependency: faster-whisper is required for alignment"
            ) from exc

        self.model = WhisperModel(model_name, device=device, compute_type=compute_type)

    def transcribe_words(self, audio_path: str) -> list[dict]:
        segments, _info = self.model.transcribe(
            audio_path,
            word_timestamps=True,
            vad_filter=False,
        )
        words: list[dict] = []
        for segment in segments:
            if not getattr(segment, "words", None):
                continue
            for word in segment.words:
                token = _normalize_word(word.word)
                if not token:
                    continue
                words.append({"word": token, "start": float(word.start), "end": float(word.end)})
        return words

    def align_with_words(
        self, audio_path: str, target_text: str, min_score: float = 70.0
    ) -> tuple[AlignmentResult | None, list[str]]:
        target_tokens = _tokenize(target_text)
        if not target_tokens:
            return None, []

        words = self.transcribe_words(audio_path)
        if not words:
            return None, []

        transcript_tokens = [w["word"] for w in words]
        best_range, best_score = _best_alignment(transcript_tokens, target_tokens)

        if best_range is None or best_score < min_score:
            return None, transcript_tokens

        start_idx, end_idx = best_range
        start_sec = words[start_idx]["start"]
        end_sec = words[end_idx - 1]["end"]
        result = AlignmentResult(
            start_sec=start_sec,
            end_sec=end_sec,
            score=best_score,
            matched_words=end_idx - start_idx,
            total_words=len(target_tokens),
        )
        return result, transcript_tokens

    def align(self, audio_path: str, target_text: str, min_score: float = 70.0) -> AlignmentResult | None:
        result, _ = self.align_with_words(audio_path, target_text, min_score=min_score)
        return result

    def score(self, audio_path: str, target_text: str) -> float:
        result = self.align(audio_path, target_text, min_score=0.0)
        return result.score if result else 0.0
