from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from dataclasses import dataclass
from platform import system
from contextlib import contextmanager
from hashlib import sha256
from uuid import uuid4
import time
from typing import Any
from typing import Iterator

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.services import llm_router
from app.config import get_settings
from app.models import (
    Chapter,
    Character,
    LLMCall,
    LLMCache,
    ProviderApiKeyUsageAudit,
    Project,
    RunChangelogEntry,
    PronunciationDictionary,
    Run,
    RunNormalizedCorpusBlob,
    Segment,
    SubSegmentTag,
)
from app.services.export import build_run_export
from app.services.segment_reconstruction import reconstruct_chapter_text_from_segments
from app.services.llm_router import (
    LLMRequest,
    LLMRouter,
    get_provider_api_keys,
    get_provider_runtime_settings,
    is_supported_provider,
)
from app.services.provider_toggle import is_provider_enabled
from app.services.character_merge import normalize_candidate_key
from app.services.character_analytics import (
    build_character_occurrence_analytics,
)
from app.services.llm_task_types import LLMTaskType
from app.services.phonetics import replace_pronunciations
from app.services.quota import (
    consume_quota,
    consume_api_key_quota,
    mark_provider_available,
    mark_api_key_rate_limited,
    mark_api_key_reset_at,
    mark_api_key_successful_call,
    mark_provider_rate_limited,
    mark_provider_reset_at,
    mark_provider_successful_call,
)
from app.services.segmentation import segment_text_with_parent_paragraph
from app.services.tagging import tag_segment
from app.services.normalization import build_segment_level_offset_map
from app.services.voice import (
    _normalize_internal_thought_voice_policy,
    build_effective_voice_config,
    resolve_voice,
)

_LOW_GENDER_CONFIDENCE = 0.0
_LOW_CONFIDENCE_GENDERS = frozenset({"neutral", "unknown"})
_AMBIGUOUS_CHARACTER_REFERENCE = object()
_LLM_CONFIDENCE_THRESHOLD_DEFAULT = 0.6
_PIPELINE_DEFAULT_CHUNK_MAX_CHARS = 120_000
_PIPELINE_CHUNK_MAX_CHARS_KEY = "pipeline_chunk_max_chars"
_PIPELINE_STAGE_ORDER = (
    "load_and_validate_source_data",
    "persist_normalized_corpus_blob",
    "load_project_artifacts",
    "clear_previous_run_artifacts",
    "resolve_incremental_recompute_scope",
    "build_chunking_plan",
    "copy_incremental_segments",
    "build_chunk_payloads",
    "merge_segment_payloads",
    "run_llm_probe",
    "derive_character_analytics",
    "finalize_run_and_build_export",
)
_PIPELINE_STAGE_PREDECESSORS: dict[str, tuple[str, ...]] = {
    "load_and_validate_source_data": (),
    "persist_normalized_corpus_blob": ("load_and_validate_source_data",),
    "load_project_artifacts": ("persist_normalized_corpus_blob",),
    "clear_previous_run_artifacts": ("load_project_artifacts",),
    "resolve_incremental_recompute_scope": ("clear_previous_run_artifacts",),
    "build_chunking_plan": ("resolve_incremental_recompute_scope",),
    "copy_incremental_segments": ("build_chunking_plan",),
    "merge_segment_payloads": ("build_chunk_payloads",),
    "build_chunk_payloads": ("build_chunking_plan", "copy_incremental_segments"),
    "run_llm_probe": ("merge_segment_payloads",),
    "derive_character_analytics": ("run_llm_probe",),
    "finalize_run_and_build_export": ("derive_character_analytics",),
}
_INCREMENTAL_RECOMPUTE_CONFIG_KEYS: tuple[str, ...] = (
    "mode",
    "max_segment_chars",
    "llm_enabled",
    "provider_name",
    "max_calls_per_day",
    "llm_confidence_threshold",
    "deep_semantic_refinement",
    "deterministic_mode",
    "deterministic_model_identifier",
    "deterministic_seed",
    "randomization_config",
    "pipeline_chunk_max_chars",
    "internal_thought_voice_policy",
    "internal_thought_voice",
    "provider_config",
    "provider_api_keys",
)


class PipelineError(RuntimeError):
    def __init__(self, message: str, *, metadata: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.metadata = metadata or {}


def _coerce_non_negative_chapter_index(value: object) -> int | None:
    try:
        index = int(value)
    except (TypeError, ValueError):
        return None
    if index <= 0:
        return None
    return index


def _compute_text_diff_preview(expected: str, reconstructed: str, *, max_length: int = 120) -> str:
    expected_norm = expected or ""
    reconstructed_norm = reconstructed or ""
    if expected_norm == reconstructed_norm:
        return ""

    mismatch_index = 0
    max_compare = max(len(expected_norm), len(reconstructed_norm))
    while mismatch_index < max_compare:
        expected_char = expected_norm[mismatch_index:mismatch_index+1]
        reconstructed_char = reconstructed_norm[mismatch_index:mismatch_index+1]
        if expected_char != reconstructed_char:
            break
        mismatch_index += 1
    else:
        mismatch_index = max_compare

    if mismatch_index >= max_compare:
        return ""

    start = max(0, mismatch_index - max_length // 2)
    end = min(max_compare, mismatch_index + max_length // 2)
    return expected_norm[start:end]


def _build_chapter_content_integrity_report(
    *,
    chapters: list[object],
    segment_payloads: list[dict[str, object]],
) -> dict[str, object]:
    normalized_by_chapter: dict[int, list[dict[str, object]]] = {}
    for segment_payload in segment_payloads:
        if not isinstance(segment_payload, dict):
            continue

        raw_chapter_id = segment_payload.get("chapter_id")
        chapter_index = _coerce_non_negative_chapter_index(raw_chapter_id)
        if chapter_index is None:
            continue

        normalized_by_chapter.setdefault(chapter_index, []).append(segment_payload)

    mismatched_chapters: list[dict[str, object]] = []
    for chapter in sorted(
        chapters,
        key=lambda item: (
            int(getattr(item, "chapter_index"))
            if _coerce_non_negative_chapter_index(getattr(item, "chapter_index", None)) is not None
            else 0
        ),
    ):
        chapter_index = _coerce_non_negative_chapter_index(getattr(chapter, "chapter_index", None))
        if chapter_index is None:
            continue
        expected_text = str(getattr(chapter, "normalized_text", "")) or ""
        payloads_for_chapter = normalized_by_chapter.get(chapter_index, [])
        reconstructed = reconstruct_chapter_text_from_segments(
            expected_text,
            payloads_for_chapter,
        )

        if reconstructed != expected_text:
            mismatch_entry = {
                "chapter_index": chapter_index,
                "expected_length": len(expected_text),
                "reconstructed_length": len(reconstructed),
                "preview": _compute_text_diff_preview(expected_text, reconstructed),
            }
            mismatched_chapters.append(mismatch_entry)

    return {
        "is_content_preserved": not mismatched_chapters,
        "total_chapters": len(chapters),
        "checked_chapters": len(chapters),
        "mismatched_chapters": mismatched_chapters,
    }


@dataclass(frozen=True)
class _PipelineChunkWorkItem:
    chapter_id: int
    chapter_index: int
    chapter_internal_id: str
    normalized_text: str
    original_to_normalized_offset_map: list[dict[str, int]]


class _RunScopedLLMSettings:
    def __init__(self, base_settings: object, provider_api_key_overrides: dict[str, object]) -> None:
        self._base_settings = base_settings
        self._provider_api_key_overrides = provider_api_key_overrides

    def __getattr__(self, key: str) -> object:
        if key in self._provider_api_key_overrides:
            return self._provider_api_key_overrides[key]
        return getattr(self._base_settings, key)


def _resolve_configuration_snapshot_id(project: Project, run: Run, run_config: dict[str, Any]) -> str:
    run_config_snapshot_id = run_config.get("configuration_snapshot_id")
    if isinstance(run_config_snapshot_id, str):
        normalized_snapshot_id = run_config_snapshot_id.strip()
        if normalized_snapshot_id:
            return normalized_snapshot_id

    project_snapshot_id = project.configuration_snapshot_id
    if isinstance(project_snapshot_id, str):
        normalized_project_snapshot_id = project_snapshot_id.strip()
        if normalized_project_snapshot_id:
            return normalized_project_snapshot_id

    return f"run-{run.id}"


def _coerce_provider_config_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _coerce_provider_config_api_keys(value: object) -> list[str]:
    if isinstance(value, str):
        raw_entries = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        raw_entries = [str(item) for item in value if item is not None]
    elif value is None:
        return []
    else:
        raw_entries = [str(value)]

    normalized = [entry.strip() for entry in raw_entries]
    return [entry for entry in normalized if entry]


def _coerce_positive_int(value: object, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _coerce_memory_bytes(value: object) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed


def _get_process_memory_bytes() -> int | None:
    try:
        import resource
    except ImportError:
        return None

    raw_usage = _coerce_memory_bytes(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if raw_usage is None:
        return None

    if system() == "Darwin":
        return raw_usage
    return raw_usage * 1024


def _collect_pipeline_step_record(
    step_name: str,
    *,
    start_time: float,
    end_time: float,
    start_memory_bytes: int | None,
    end_memory_bytes: int | None,
) -> dict[str, object]:
    return {
        "name": step_name,
        "duration_ms": int((end_time - start_time) * 1000),
        "memory_bytes_start": start_memory_bytes,
        "memory_bytes_end": end_memory_bytes,
        "memory_bytes_delta": (
            None
            if start_memory_bytes is None or end_memory_bytes is None
            else end_memory_bytes - start_memory_bytes
        ),
    }


@contextmanager
def _record_pipeline_step(
    step_records: list[dict[str, object]],
    step_name: str,
) -> Iterator[None]:
    start_time = time.perf_counter()
    start_memory = _get_process_memory_bytes()
    try:
        yield
    finally:
        end_time = time.perf_counter()
        end_memory = _get_process_memory_bytes()
        step_records.append(
            _collect_pipeline_step_record(
                step_name,
                start_time=start_time,
                end_time=end_time,
                start_memory_bytes=start_memory,
                end_memory_bytes=end_memory,
            )
        )


def _build_performance_telemetry_payload(
    *,
    step_records: list[dict[str, object]],
    total_duration_ms: int,
    status: str,
) -> dict[str, object]:
    return {
        "status": status,
        "total_duration_ms": total_duration_ms,
        "steps": list(step_records),
    }


def _append_pipeline_performance_changelog_entry(
    session: Session,
    *,
    run: Run,
    telemetry: dict[str, object],
) -> None:
    session.add(
        RunChangelogEntry(
            run_id=run.id,
            event_type="pipeline_performance_telemetry",
            event_message="Pipeline performance telemetry captured",
            event_metadata={"performance_telemetry": telemetry},
        )
    )


def _resolve_pipeline_chunk_max_chars(run_config: dict[str, Any], *, default: int = _PIPELINE_DEFAULT_CHUNK_MAX_CHARS) -> int:
    return _coerce_positive_int(
        run_config.get(_PIPELINE_CHUNK_MAX_CHARS_KEY),
        default=default,
    )


def _build_chapter_chunks(
    chapters: list[Chapter],
    max_chunk_chars: int,
) -> list[list[Chapter]]:
    if max_chunk_chars <= 0:
        max_chunk_chars = _PIPELINE_DEFAULT_CHUNK_MAX_CHARS

    ordered_chapters = sorted(chapters, key=lambda chapter: chapter.chapter_index)
    chunks: list[list[Chapter]] = []
    current_chunk: list[Chapter] = []
    current_chunk_chars = 0

    for chapter in ordered_chapters:
        chapter_chars = len(str(chapter.normalized_text or ""))
        if current_chunk and current_chunk_chars + chapter_chars > max_chunk_chars:
            chunks.append(current_chunk)
            current_chunk = []
            current_chunk_chars = 0

        current_chunk.append(chapter)
        current_chunk_chars += chapter_chars

    if current_chunk:
        chunks.append(current_chunk)

    return chunks or [ordered_chapters]


def _coerce_chunk_offset_map(value: object) -> list[dict[str, int]]:
    if not isinstance(value, list):
        return []

    coalesced: list[dict[str, int]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        coalesced.append(dict(item))
    return coalesced


def _build_chunk_work_items(chapters: list[Chapter]) -> list[_PipelineChunkWorkItem]:
    return [
        _PipelineChunkWorkItem(
            chapter_id=int(getattr(chapter, "id", getattr(chapter, "chapter_id", chapter.chapter_index))),
            chapter_index=int(chapter.chapter_index),
            chapter_internal_id=str(chapter.chapter_internal_id or ""),
            normalized_text=str(chapter.normalized_text or ""),
            original_to_normalized_offset_map=_coerce_chunk_offset_map(chapter.original_to_normalized_offset_map),
        )
        for chapter in chapters
    ]


def _build_chunk_jobs(chapter_work_items: list[_PipelineChunkWorkItem], max_chunk_chars: int) -> list[list[_PipelineChunkWorkItem]]:
    if not chapter_work_items:
        return []
    return _build_chapter_chunks(chapters=chapter_work_items, max_chunk_chars=max_chunk_chars)


def _build_chunk_segment_payloads(
    *,
    chunk_index: int,
    chunk_count: int,
    chapter_batch: list[_PipelineChunkWorkItem],
    max_chars: int,
    name_to_verbalized: dict[str, str],
    character_lookup: dict[str, dict[str, object] | object],
    character_pronunciations: dict[str, dict[str, str]],
    voice_config: dict[str, object],
    llm_confidence_threshold: float,
    deep_semantic_refinement: bool,
) -> dict[str, object]:
    segment_payloads: list[dict[str, object]] = []
    sub_segment_payloads: list[list[dict[str, object]]] = []
    llm_probe_text: str | None = None

    for chapter in chapter_batch:
        pieces = segment_text_with_parent_paragraph(chapter.normalized_text, max_chars=max_chars)
        chapter_search_cursor = 0

        for segment_index, piece in enumerate(pieces, start=1):
            original_text = str(piece.get("text", ""))
            parent_paragraph_index = int(piece.get("paragraph_index", 1))
            parent_sentence_start_index = int(piece.get("sentence_start_index", parent_paragraph_index))
            parent_sentence_end_index = int(piece.get("sentence_end_index", parent_sentence_start_index))
            if parent_sentence_end_index < parent_sentence_start_index:
                parent_sentence_end_index = parent_sentence_start_index

            tags = tag_segment(original_text)
            speaker = str(tags["speaker"])
            speaker_entry = _resolve_speaker_entry(speaker=speaker, character_lookup=character_lookup)
            normalized_speaker = speaker.strip().lower()
            pronunciation_map = {**name_to_verbalized}
            if normalized_speaker and normalized_speaker != "unknown":
                pronunciation_map.update(character_pronunciations.get(normalized_speaker, {}))
            phonetic_text = replace_pronunciations(original_text, pronunciation_map)

            segment_start = chapter.normalized_text.find(original_text, chapter_search_cursor)
            if segment_start < 0:
                segment_start = max(chapter_search_cursor, 0)
                segment_offset_map: list[dict[str, int]] = []
            else:
                segment_offset_map = build_segment_level_offset_map(
                    chapter.original_to_normalized_offset_map,
                    segment_start,
                    original_text,
                )

            segment_offset_candidates = [
                (entry["original_start"], entry["original_end"])
                for entry in segment_offset_map
                if entry.get("original_start") != -1 and entry.get("original_end") != -1
            ]
            if segment_offset_candidates:
                original_span_start = min(start for start, _ in segment_offset_candidates)
                original_span_end = max(end for _, end in segment_offset_candidates)
            else:
                original_span_start = -1
                original_span_end = -1
            chapter_search_cursor = segment_start + len(original_text)

            speaker = str(tags["speaker"])
            resolved_voice_id, resolved_gender = resolve_voice(
                segment_type=str(tags["type"]),
                speaker=speaker,
                character_lookup=character_lookup,
                voice_config=voice_config,
            )

            canonical_entry = speaker_entry
            gender = resolved_gender
            if canonical_entry is not None:
                gender = str(canonical_entry.get("gender", resolved_gender))

            speaker_id: int | None = None
            if canonical_entry is not None and canonical_entry.get("id") is not None:
                speaker_id = int(canonical_entry["id"])

            segment_payload = {
                "chapter_id": chapter.chapter_index,
                "chapter_internal_id": chapter.chapter_internal_id,
                "segment_id": f"{chapter.chapter_index}-{segment_index:03d}",
                "segment_index": segment_index,
                "original_text": original_text,
                "normalized_text": original_text,
                "phonetic_text": phonetic_text,
                "parent_paragraph_reference": {
                    "paragraph_index": parent_paragraph_index,
                    "paragraph_id": f"{chapter.chapter_index:03d}-p{parent_paragraph_index:03d}",
                },
                "parent_sentence_reference": {
                    "sentence_start_index": parent_sentence_start_index,
                    "sentence_end_index": parent_sentence_end_index,
                    "sentence_id": (
                        f"{chapter.chapter_index:03d}-p{parent_paragraph_index:03d}"
                        f"-s{parent_sentence_start_index:03d}"
                    ),
                },
                "type": tags["type"],
                "type_evidence": _normalize_evidence_offsets(tags.get("type_evidence", {}), segment_offset_map),
                "speaker": speaker,
                "speaker_evidence": _normalize_evidence_offsets(tags.get("speaker_evidence", {}), segment_offset_map),
                "speaker_id": speaker_id,
                "gender": gender,
                "type_confidence": tags["type_confidence"],
                "speaker_state": tags.get("speaker_state", "uncertain"),
                "emotion_state": tags.get("emotion_state", "uncertain"),
                "summary_tag": _normalize_evidence_offsets(tags.get("summary_tag", {}), segment_offset_map),
                "ambiguity_flags": tags.get("ambiguity_flags", []),
                "emotion_evidence": _normalize_evidence_offsets(tags.get("emotion_evidence", {}), segment_offset_map),
                "tag_states": {
                    "type": tags.get("type_state", "uncertain"),
                    "speaker": tags.get("speaker_state", "uncertain"),
                    "emotion": tags.get("emotion_state", "uncertain"),
                    "tension": tags.get("tension_contribution", {}).get("state", "uncertain"),
                    "dominance": tags.get("dominance_contribution", {}).get("state", "uncertain"),
                    "summary": tags.get("summary_tag", {}).get("state", "uncertain"),
                },
                "voice_id": resolved_voice_id,
                "resolved_voice_id": resolved_voice_id,
                "emotion_valence": tags["emotion_valence"],
                "emotion_intensity": tags["emotion_intensity"],
                "emotion_primary_label": tags["emotion_primary_label"],
                "emotion_secondary_label": tags["emotion_secondary_label"],
                "emotion_shift": _normalize_evidence_offsets(tags["emotion_shift"], segment_offset_map),
                "narration_internal_thought_shift": _normalize_evidence_offsets(
                    tags["narration_internal_thought_shift"],
                    segment_offset_map,
                ),
                "internal_external_speech_shift": _normalize_evidence_offsets(
                    tags["internal_external_speech_shift"],
                    segment_offset_map,
                ),
                "tone_reversal": _normalize_evidence_offsets(tags["tone_reversal"], segment_offset_map),
                "sub_segment_boundaries": [
                    _normalize_evidence_offsets(boundary, segment_offset_map)
                    for boundary in tags.get("sub_segment_boundaries", [])
                ],
                "tension_contribution": {
                    "value": tags["tension_contribution"]["value"],
                    "level": tags["tension_contribution"]["level"],
                    "confidence": tags["tension_contribution"]["confidence"],
                    "state": tags["tension_contribution"]["state"],
                    "evidence": _normalize_evidence_offsets(
                        tags["tension_contribution"].get("evidence", {}),
                        segment_offset_map,
                    ),
                },
                "dominance_contribution": {
                    "value": tags["dominance_contribution"]["value"],
                    "level": tags["dominance_contribution"]["level"],
                    "dominant_agent": tags["dominance_contribution"]["dominant_agent"],
                    "evidence": _normalize_evidence_offsets(
                        tags["dominance_contribution"].get("evidence", {}),
                        segment_offset_map,
                    ),
                    "confidence": tags["dominance_contribution"]["confidence"],
                    "state": tags["dominance_contribution"]["state"],
                },
                "confidence": {
                    "speaker": tags["speaker_confidence"],
                    "emotion": tags["emotion_confidence"],
                    "gender": _resolve_gender_confidence(speaker=speaker, character_lookup=character_lookup),
                    "type": tags["type_confidence"],
                    "tension": tags["tension_contribution"]["confidence"],
                    "dominance": tags["dominance_contribution"]["confidence"],
                },
                "original_span_pointer": {
                    "original_start_char": original_span_start,
                    "original_end_char": original_span_end,
                    "normalized_start_char": segment_start,
                    "normalized_end_char": segment_start + len(original_text),
                },
                "original_to_normalized_offset_map": segment_offset_map,
                "chunk_index": chunk_index,
                "chunk_count": chunk_count,
            }

            segment_payloads.append(segment_payload)
            llm_refinement_needed = _should_escalate_to_llm(
                segment_payload,
                confidence_threshold=llm_confidence_threshold,
                deep_semantic_refinement=deep_semantic_refinement,
            )
            segment_payload["llm_refinement_needed"] = bool(llm_refinement_needed)

            if llm_probe_text is None and llm_refinement_needed:
                llm_probe_text = original_text

            boundary_payloads: list[dict[str, object]] = []
            for boundary_index, boundary in enumerate(tags.get("sub_segment_boundaries", []), start=1):
                if not isinstance(boundary, dict):
                    continue
                evidence = boundary.get("evidence", {})
                shift_type = boundary.get("shift_type")
                boundary_payloads.append(
                    {
                        "boundary_index": boundary_index,
                        "segment_id": segment_payload["segment_id"],
                        "shift_type": str(shift_type),
                        "boundary_start_char": int(boundary.get("boundary_start_char", 0)),
                        "boundary_end_char": int(boundary.get("boundary_end_char", 0)),
                        "from_label": (None if boundary.get("from_label") is None else str(boundary.get("from_label"))),
                        "to_label": (None if boundary.get("to_label") is None else str(boundary.get("to_label"))),
                        "from_text": (None if boundary.get("from_text") is None else str(boundary.get("from_text"))),
                        "to_text": (None if boundary.get("to_text") is None else str(boundary.get("to_text"))),
                        "confidence": float(boundary.get("confidence", 0.0)),
                        "tags": {"shift_type": shift_type, "payload": dict(boundary)},
                        "evidence": evidence,
                    }
                )

            sub_segment_payloads.append(boundary_payloads)

    return {
        "chunk_index": chunk_index,
        "chunk_count": chunk_count,
        "segment_payloads": segment_payloads,
        "sub_segment_payloads": sub_segment_payloads,
        "llm_probe_text": llm_probe_text,
    }


def _extract_model_version(model_identifier: object) -> str | None:
    normalized = str(model_identifier).strip() if isinstance(model_identifier, str) else ""
    if not normalized:
        return None

    if ":" in normalized:
        candidate = normalized.rsplit(":", 1)[-1].strip()
        if candidate:
            return candidate

    if "@" in normalized:
        candidate = normalized.rsplit("@", 1)[-1].strip()
        if candidate:
            return candidate

    return None


def _map_local_char_to_original(
    local_offset: int,
    segment_offset_map: list[dict[str, int]],
) -> int:
    if not segment_offset_map or local_offset < 0:
        return -1

    candidates: list[dict[str, int]] = []
    for entry in segment_offset_map:
        try:
            original_start = int(entry["original_start"])
            original_end = int(entry["original_end"])
            normalized_start = int(entry["normalized_start"])
            normalized_end = int(entry["normalized_end"])
        except (KeyError, TypeError, ValueError):
            continue

        if original_start == -1 or original_end == -1:
            continue
        if normalized_start <= local_offset <= normalized_end:
            candidates.append(entry)

    if not candidates:
        return -1

    selected = max(
        candidates,
        key=lambda candidate: (
            int(candidate["normalized_start"]),
            int(candidate["normalized_end"]) - int(candidate["normalized_start"]),
        ),
    )

    try:
        normalized_start = int(selected["normalized_start"])
        normalized_end = int(selected["normalized_end"])
        original_start = int(selected["original_start"])
        original_end = int(selected["original_end"])
    except (KeyError, TypeError, ValueError):
        return -1

    normalized_length = max(normalized_end - normalized_start, 1)
    original_length = max(original_end - original_start, 1)
    mapped = original_start + int((local_offset - normalized_start) * original_length / normalized_length)
    return max(-1, min(mapped, original_end))


def _normalize_evidence_offsets(
    payload: object,
    segment_offset_map: list[dict[str, int]],
) -> object:
    if isinstance(payload, list):
        return [_normalize_evidence_offsets(item, segment_offset_map) for item in payload]

    if not isinstance(payload, dict):
        return payload

    normalized_payload: dict[str, object] = {}
    for key, value in payload.items():
        normalized_payload[key] = _normalize_evidence_offsets(value, segment_offset_map)

    if "start_char" in normalized_payload and "end_char" in normalized_payload:
        start_char = normalized_payload.get("start_char")
        end_char = normalized_payload.get("end_char")
        if isinstance(start_char, int) and isinstance(end_char, int):
            normalized_payload["original_start_char"] = _map_local_char_to_original(start_char, segment_offset_map)
            normalized_payload["original_end_char"] = _map_local_char_to_original(end_char, segment_offset_map)

    return normalized_payload


def _persist_run_llm_model_metadata(run: Run, *, provider: str, model_identifier: str | None) -> None:
    normalized_provider = provider.strip().lower() if isinstance(provider, str) else ""
    normalized_provider = normalized_provider or None
    normalized_model = str(model_identifier).strip() if isinstance(model_identifier, str) and str(model_identifier).strip() else None

    run.llm_provider_name = normalized_provider
    run.llm_model_identifier = normalized_model
    run.llm_model_version = _extract_model_version(normalized_model)


def _build_run_scoped_llm_settings(settings: object, run_config: dict[str, Any]) -> object:
    if not isinstance(run_config, dict):
        return settings

    provider_overrides: dict[str, object] = {}

    raw_provider_config = run_config.get("provider_config")
    if isinstance(raw_provider_config, dict):
        for provider_name, provider_config in raw_provider_config.items():
            normalized_provider = str(provider_name).strip().lower()
            if not normalized_provider or not isinstance(provider_config, dict):
                continue

            base_url = _coerce_provider_config_string(provider_config.get("base_url"))
            if base_url is not None:
                provider_overrides[f"{normalized_provider}_base_url"] = base_url

            model = _coerce_provider_config_string(provider_config.get("model"))
            if model is not None:
                provider_overrides[f"{normalized_provider}_model"] = model

            api_key = _coerce_provider_config_string(provider_config.get("api_key"))
            if api_key is not None:
                provider_overrides[f"{normalized_provider}_api_key"] = api_key

            api_keys = provider_config.get("api_keys")
            normalized_api_keys = _coerce_provider_config_api_keys(api_keys)
            if normalized_api_keys:
                provider_overrides[f"{normalized_provider}_api_keys"] = normalized_api_keys

    raw_provider_api_keys = run_config.get("provider_api_keys")
    if not isinstance(raw_provider_api_keys, dict):
        return _RunScopedLLMSettings(base_settings=settings, provider_api_key_overrides=provider_overrides)

    for provider_name, provider_api_keys in raw_provider_api_keys.items():
        normalized_provider = str(provider_name).strip().lower()
        if not normalized_provider:
            continue
        provider_overrides[f"{normalized_provider}_api_keys"] = provider_api_keys

    if not provider_overrides:
        return settings

    return _RunScopedLLMSettings(
        base_settings=settings,
        provider_api_key_overrides=provider_overrides,
    )


def _coerce_confidence(value: object) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return _LOW_GENDER_CONFIDENCE
    if confidence < 0.0:
        return 0.0
    if confidence > 1.0:
        return 1.0
    return round(confidence, 4)


def _coerce_confidence_threshold(value: object) -> float:
    try:
        threshold = float(value)
    except (TypeError, ValueError):
        return _LLM_CONFIDENCE_THRESHOLD_DEFAULT
    if threshold < 0.0:
        return 0.0
    if threshold > 1.0:
        return 1.0
    return round(threshold, 4)


def _persist_normalized_corpus_blob(session: Session, *, run_id: int, normalized_corpus: str) -> None:
    normalized_payload = normalized_corpus.encode("utf-8")
    session.add(
        RunNormalizedCorpusBlob(
            run_id=run_id,
            source="pipeline",
            source_filename=None,
            corpus_sha256=sha256(normalized_payload).hexdigest(),
            normalized_corpus_blob=normalized_payload,
        )
    )


def _build_llm_cache_key(input_text: str) -> str:
    return sha256(str(input_text).encode("utf-8")).hexdigest()


def _build_incremental_recompute_config_signature(run_config: dict[str, Any]) -> dict[str, Any]:
    return {
        key: run_config[key]
        for key in _INCREMENTAL_RECOMPUTE_CONFIG_KEYS
        if key in run_config
    }


def _get_latest_completed_run_before(
    session: Session,
    project_id: int,
    current_run_id: int,
) -> Run | None:
    return (
        session.query(Run)
        .filter(Run.project_id == project_id, Run.id < current_run_id, Run.status == "completed")
        .order_by(Run.id.desc())
        .first()
    )


def _get_processed_chapter_indexes_for_run(session: Session, run_id: int) -> list[int]:
    rows = (
        session.query(Chapter.chapter_index)
        .join(Segment, Segment.chapter_id == Chapter.id)
        .filter(Segment.run_id == run_id)
        .group_by(Chapter.chapter_index)
        .order_by(Chapter.chapter_index.asc())
        .all()
    )
    return [int(row[0]) for row in rows]


def _resolve_incremental_recompute_scope(
    session: Session,
    project_id: int,
    current_run_id: int,
    run_config: dict[str, Any],
    chapters: list[Chapter],
) -> int:
    if not bool(run_config.get("incremental_recompute", False)):
        return 0

    prior_run = _get_latest_completed_run_before(
        session=session,
        project_id=project_id,
        current_run_id=current_run_id,
    )
    if prior_run is None:
        return 0

    prior_signature = _build_incremental_recompute_config_signature(prior_run.config_json or {})
    current_signature = _build_incremental_recompute_config_signature(run_config)
    if prior_signature != current_signature:
        return 0

    prior_indexes = _get_processed_chapter_indexes_for_run(session=session, run_id=prior_run.id)
    if not prior_indexes:
        return 0

    latest_index = prior_indexes[-1]
    expected_prefix = list(range(1, latest_index + 1))
    if prior_indexes != expected_prefix:
        return 0

    chapter_indexes = [int(chapter.chapter_index) for chapter in chapters]
    if len(chapter_indexes) <= latest_index:
        return 0

    if chapter_indexes[:latest_index] != expected_prefix:
        return 0

    return latest_index


def _copy_incremental_run_payloads(
    session: Session,
    source_run_id: int,
    target_run_id: int,
    chapter_scope: int,
) -> list[dict[str, object]]:
    prior_segments = (
        session.query(Segment)
        .join(Chapter, Segment.chapter_id == Chapter.id)
        .filter(
            Segment.run_id == source_run_id,
            Chapter.chapter_index <= int(chapter_scope),
        )
        .order_by(Chapter.chapter_index.asc(), Segment.segment_index.asc(), Segment.id.asc())
        .all()
    )
    if not prior_segments:
        return []

    source_to_target_segment_id: dict[int, int] = {}
    reused_segment_payloads: list[dict[str, object]] = []
    for prior_segment in prior_segments:
        copied_segment = Segment(
            run_id=target_run_id,
            chapter_id=int(prior_segment.chapter_id),
            segment_index=int(prior_segment.segment_index),
            segment_json=dict(prior_segment.segment_json),
        )
        session.add(copied_segment)
        session.flush()
        source_to_target_segment_id[int(prior_segment.id)] = int(copied_segment.id)
        reused_segment_payloads.append(dict(prior_segment.segment_json))

    prior_segment_ids = list(source_to_target_segment_id.keys())
    if prior_segment_ids:
        prior_tags = (
            session.query(SubSegmentTag)
            .filter(SubSegmentTag.run_id == source_run_id, SubSegmentTag.segment_id.in_(prior_segment_ids))
            .order_by(SubSegmentTag.segment_id.asc(), SubSegmentTag.sub_segment_index.asc())
            .all()
        )
        for prior_tag in prior_tags:
            copied_segment_id = source_to_target_segment_id.get(int(prior_tag.segment_id))
            if copied_segment_id is None:
                continue

            session.add(
                SubSegmentTag(
                    run_id=target_run_id,
                    chapter_id=int(prior_tag.chapter_id),
                    segment_id=copied_segment_id,
                    sub_segment_id=str(prior_tag.sub_segment_id),
                    sub_segment_index=int(prior_tag.sub_segment_index),
                    shift_type=str(prior_tag.shift_type),
                    boundary_start_char=int(prior_tag.boundary_start_char),
                    boundary_end_char=int(prior_tag.boundary_end_char),
                    from_label=(None if prior_tag.from_label is None else str(prior_tag.from_label)),
                    to_label=(None if prior_tag.to_label is None else str(prior_tag.to_label)),
                    from_text=(None if prior_tag.from_text is None else str(prior_tag.from_text)),
                    to_text=(None if prior_tag.to_text is None else str(prior_tag.to_text)),
                    confidence=float(prior_tag.confidence),
                    tags=dict(prior_tag.tags),
                    evidence=(dict(prior_tag.evidence) if isinstance(prior_tag.evidence, dict) else {}),
                )
            )

    return reused_segment_payloads


def _get_cached_llm_response(
    session: Session,
    *,
    input_text: str,
    task_type: str,
    configuration_snapshot_id: str,
    model_identifier: str | None,
) -> LLMCache | None:
    model_id = (str(model_identifier or "").strip()) or None
    if model_id is None:
        return None

    input_text_hash = _build_llm_cache_key(input_text)
    return (
        session.query(LLMCache)
        .filter(
            LLMCache.input_text_hash == input_text_hash,
            LLMCache.task_type == task_type,
            LLMCache.configuration_snapshot_id == configuration_snapshot_id,
            LLMCache.model_identifier == model_id,
        )
        .one_or_none()
    )


def _coerce_call_timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)

    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _build_provider_api_key_audit_mask(api_key: str | None) -> str | None:
    if not api_key:
        return None

    clean_key = str(api_key).strip()
    if not clean_key:
        return None

    if len(clean_key) <= 4:
        return "*" * len(clean_key)

    return f"••••{clean_key[-4:]}"


def _build_provider_api_key_fingerprint(api_key: str | None) -> str | None:
    if not api_key:
        return None

    clean_key = str(api_key).strip()
    if not clean_key:
        return None

    return sha256(clean_key.encode("utf-8")).hexdigest()


def _append_deterministic_replay_warning(run: Run, requested_provider: str, actual_provider: str, reason: str) -> None:
    config_snapshot = dict(run.config_json or {})
    warnings = config_snapshot.get("deterministic_warnings")
    if not isinstance(warnings, list):
        warnings = []

    warnings.append(
        {
            "type": "deterministic_replay_warning",
            "level": "warning",
            "source": "llm_provider_fallback",
            "message": (
                f"Deterministic mode requested provider '{requested_provider}', but run used '{actual_provider}' "
                "after provider-level retries. Exact replay across runs may diverge."
            ),
            "requested_provider": requested_provider,
            "actual_provider": actual_provider,
            "reason": reason,
        }
    )

    config_snapshot["deterministic_warnings"] = warnings
    run.config_json = config_snapshot


def _append_llm_rule_only_state(
    run: Run,
    reason: str,
    last_provider: str | None = None,
) -> None:
    config_snapshot = dict(run.config_json or {})
    config_snapshot["llm_execution_mode"] = {
        "mode": "rule_only",
        "reason": reason,
        "provider": last_provider,
    }
    run.config_json = config_snapshot


def _build_probe_provider_order(
    session: Session,
    requested_provider: str,
    settings: object,
    max_calls_per_day: int,
) -> tuple[str, ...]:
    provider_order = llm_router.select_probe_provider_candidates(
        session=session,
        settings=settings,
        requested_provider=requested_provider,
        max_calls_per_day=max_calls_per_day,
    )
    if requested_provider not in provider_order:
        return (requested_provider, *provider_order)
    return provider_order


def get_provider_priority_order(
    session: Session,
    requested_provider: str,
    settings: object,
    max_calls_per_day: int,
) -> tuple[str, ...]:
    return _build_probe_provider_order(
        session=session,
        requested_provider=requested_provider,
        settings=settings,
        max_calls_per_day=max_calls_per_day,
    )


def _normalize_provider_name_for_llm(value: object) -> str:
    return str(value).strip().lower()


def _resolve_gender_confidence(
    speaker: str,
    character_lookup: dict[str, dict[str, object] | object],
) -> float:
    if not speaker:
        return _LOW_GENDER_CONFIDENCE

    entry = _character_lookup_entry_for_speaker(speaker=speaker, character_lookup=character_lookup)
    if entry is None:
        return _LOW_GENDER_CONFIDENCE

    gender = str(entry.get("gender", "unknown")).strip().lower() or "unknown"
    if gender in _LOW_CONFIDENCE_GENDERS:
        return _LOW_GENDER_CONFIDENCE

    return _coerce_confidence(entry.get("confidence"))


def _character_lookup_entry_for_speaker(
    speaker: str,
    character_lookup: dict[str, dict[str, object] | object],
) -> dict[str, object] | None:
    normalized_speaker = normalize_candidate_key(speaker)
    if not normalized_speaker:
        return None

    entry = character_lookup.get(normalized_speaker)
    if not isinstance(entry, dict):
        return None
    return entry


def _build_character_lookup(rows: list[Character]) -> dict[str, dict[str, object] | object]:
    lookup: dict[str, dict[str, object] | object] = {}

    def add_lookup_key(normalized_key: str, entry: dict[str, object]) -> None:
        if not normalized_key:
            return
        existing = lookup.get(normalized_key)
        if existing is None:
            lookup[normalized_key] = entry
            return
        if existing is entry:
            return
        if isinstance(existing, dict) and existing.get("id") == entry.get("id"):
            return
        lookup[normalized_key] = _AMBIGUOUS_CHARACTER_REFERENCE

    def _character_voice_id(character_row: Character) -> str | None:
        assigned_voice = getattr(character_row, "voice_map", None)
        if assigned_voice is not None and assigned_voice.voice_id:
            return str(assigned_voice.voice_id)
        if character_row.voice_id:
            return str(character_row.voice_id)
        return None

    for character in rows:
        voice_id = _character_voice_id(character)
        speaker_entry: dict[str, object] = {
            "id": character.id,
            "gender": character.gender,
            "voice_id": voice_id,
            "confidence": character.confidence,
        }
        add_lookup_key(normalize_candidate_key(character.name), speaker_entry)
        for alias in character.aliases or []:
            add_lookup_key(normalize_candidate_key(alias), speaker_entry)

    return lookup


def _resolve_speaker_entry(
    speaker: str,
    character_lookup: dict[str, dict[str, object] | object],
) -> dict[str, object] | None:
    if not speaker:
        return None
    if normalize_candidate_key(speaker) == "unknown":
        return None
    return _character_lookup_entry_for_speaker(speaker=speaker, character_lookup=character_lookup)


def _should_escalate_to_llm(
    tags: dict[str, object], *, confidence_threshold: float = _LLM_CONFIDENCE_THRESHOLD_DEFAULT, deep_semantic_refinement: bool = False
) -> bool:
    if bool(deep_semantic_refinement):
        return True

    threshold = _coerce_confidence_threshold(confidence_threshold)
    ambiguity_flags = tags.get("ambiguity_flags")
    if isinstance(ambiguity_flags, str):
        if ambiguity_flags.strip():
            return True
    elif isinstance(ambiguity_flags, (list, tuple, set)):
        for flag in ambiguity_flags:
            if str(flag).strip():
                return True
    elif isinstance(ambiguity_flags, dict):
        if any(bool(value) for value in ambiguity_flags.values()):
            return True

    check_states = {
        str(tags.get("type_state", "unknown")).lower(),
        str(tags.get("speaker_state", "unknown")).lower(),
        str(tags.get("emotion_state", "unknown")).lower(),
        str(tags.get("summary_tag", {}).get("state", "unknown")).lower()
        if isinstance(tags.get("summary_tag"), dict)
        else "unknown",
        str(tags.get("tension_contribution", {}).get("state", "unknown")).lower()
        if isinstance(tags.get("tension_contribution"), dict)
        else "unknown",
        str(tags.get("dominance_contribution", {}).get("state", "unknown")).lower()
        if isinstance(tags.get("dominance_contribution"), dict)
        else "unknown",
    }
    if any(state in {"uncertain", "unknown"} for state in check_states):
        return True

    confidence_fields = [
        ("type_confidence", tags.get("type_confidence")),
        ("speaker_confidence", tags.get("speaker_confidence")),
        ("emotion_confidence", tags.get("emotion_confidence")),
        ("summary_confidence", tags.get("summary_tag", {}).get("confidence") if isinstance(tags.get("summary_tag"), dict) else None),
        ("tension_confidence", tags.get("tension_contribution", {}).get("confidence") if isinstance(tags.get("tension_contribution"), dict) else None),
        ("dominance_confidence", tags.get("dominance_contribution", {}).get("confidence") if isinstance(tags.get("dominance_contribution"), dict) else None),
    ]
    for _, value in confidence_fields:
        if _coerce_confidence(value) < threshold:
            return True
    return False


def execute_pipeline(
    session: Session,
    project: Project,
    run: Run,
    run_config: dict,
    *,
    project_id: int | str | None = None,
    principal_type: str | None = None,
    principal_id: str | None = None,
) -> dict:
    step_records: list[dict[str, object]] = []
    completed_stages: list[str] = []
    pipeline_started_at = time.perf_counter()

    with _record_pipeline_stage(
        step_records=step_records,
        stage_name="load_and_validate_source_data",
        completed_stages=completed_stages,
    ):
        chapters = (
            session.query(Chapter)
            .filter(Chapter.project_id == project.id)
            .order_by(Chapter.chapter_index.asc())
            .all()
        )

        if not chapters:
            raise PipelineError("No chapters available. Upload and ingest a TXT file first.")

    with _record_pipeline_stage(
        step_records=step_records,
        stage_name="persist_normalized_corpus_blob",
        completed_stages=completed_stages,
    ):
        _persist_normalized_corpus_blob(
            session=session,
            run_id=run.id,
            normalized_corpus="\n\n".join(chapter.normalized_text for chapter in chapters),
        )

    with _record_pipeline_stage(
        step_records=step_records,
        stage_name="load_project_artifacts",
        completed_stages=completed_stages,
    ):
        characters = (
            session.query(Character)
            .filter(Character.project_id == project.id)
            .order_by(Character.name.asc(), Character.id.asc())
            .all()
        )

        global_pronunciations = {
            entry.term.strip(): entry.verbalized_form.strip()
            for entry in session.query(PronunciationDictionary)
            .filter(
                PronunciationDictionary.project_id == project.id,
                PronunciationDictionary.scope == "global",
                PronunciationDictionary.character_name == "",
            )
            .order_by(PronunciationDictionary.term.asc(), PronunciationDictionary.id.asc())
            .all()
        }
        place_pronunciations = {
            entry.term.strip(): entry.verbalized_form.strip()
            for entry in session.query(PronunciationDictionary)
            .filter(
                PronunciationDictionary.project_id == project.id,
                PronunciationDictionary.scope == "place",
                PronunciationDictionary.character_name == "",
            )
            .order_by(PronunciationDictionary.term.asc(), PronunciationDictionary.id.asc())
            .all()
        }
        invented_pronunciations = {
            entry.term.strip(): entry.verbalized_form.strip()
            for entry in session.query(PronunciationDictionary)
            .filter(
                PronunciationDictionary.project_id == project.id,
                PronunciationDictionary.scope == "invented",
                PronunciationDictionary.character_name == "",
            )
            .order_by(PronunciationDictionary.term.asc(), PronunciationDictionary.id.asc())
            .all()
        }
        artifact_pronunciations = {
            entry.term.strip(): entry.verbalized_form.strip()
            for entry in session.query(PronunciationDictionary)
            .filter(
                PronunciationDictionary.project_id == project.id,
                PronunciationDictionary.scope == "artifact",
                PronunciationDictionary.character_name == "",
            )
            .order_by(PronunciationDictionary.term.asc(), PronunciationDictionary.id.asc())
            .all()
        }
        character_scope_entries = (
            session.query(PronunciationDictionary)
            .filter(
                PronunciationDictionary.project_id == project.id,
                PronunciationDictionary.scope == "character",
            )
            .order_by(
                PronunciationDictionary.character_name.asc(),
                PronunciationDictionary.term.asc(),
                PronunciationDictionary.id.asc(),
            )
            .all()
        )
    character_pronunciations = {}
    for entry in character_scope_entries:
        normalized_name = entry.character_name.strip().lower()
        if not normalized_name:
            continue
        character_map = character_pronunciations.setdefault(normalized_name, {})
        character_map[entry.term.strip()] = entry.verbalized_form.strip()

    name_to_verbalized = {
        **global_pronunciations,
        **place_pronunciations,
        **artifact_pronunciations,
        **invented_pronunciations,
    }
    for character in characters:
        name_to_verbalized[character.name.strip()] = character.verbalized_form.strip()
    character_lookup = _build_character_lookup(rows=characters)
    voice_config = build_effective_voice_config(
        project.voice_config_json,
        default_narrator_voice=project.default_narrator_voice,
        default_male_voice=project.default_male_voice,
        default_female_voice=project.default_female_voice,
        default_neutral_voice=project.default_neutral_voice,
        default_unknown_voice=project.default_unknown_voice,
    )
    voice_config["internal_thought_voice_policy"] = _normalize_internal_thought_voice_policy(
        run_config.get("internal_thought_voice_policy")
    )
    if run_config.get("internal_thought_voice"):
        voice_config["thought_voice"] = str(run_config["internal_thought_voice"]).strip()

    with _record_pipeline_stage(
        step_records=step_records,
        stage_name="clear_previous_run_artifacts",
        completed_stages=completed_stages,
    ):
        session.query(Segment).filter(Segment.run_id == run.id).delete()
        session.query(LLMCall).filter(LLMCall.run_id == run.id).delete()
        session.query(SubSegmentTag).filter(SubSegmentTag.run_id == run.id).delete()

    with _record_pipeline_stage(
        step_records=step_records,
        stage_name="resolve_incremental_recompute_scope",
        completed_stages=completed_stages,
    ):
        incremental_scope = _resolve_incremental_recompute_scope(
            session=session,
            project_id=project.id,
            current_run_id=run.id,
            run_config=run_config,
            chapters=chapters,
        )
        if incremental_scope > 0:
            run.config_json = {
                **(run.config_json or {}),
                "incremental_recompute": {
                    "enabled": True,
                    "reused_chapter_count": incremental_scope,
                },
            }

    with _record_pipeline_stage(
        step_records=step_records,
        stage_name="build_chunking_plan",
        completed_stages=completed_stages,
    ):
        max_chars = int(run_config.get("max_segment_chars", 255))
        llm_confidence_threshold = _coerce_confidence_threshold(
            run_config.get("llm_confidence_threshold", _LLM_CONFIDENCE_THRESHOLD_DEFAULT)
        )
        deep_semantic_refinement = bool(run_config.get("deep_semantic_refinement", False))
        max_chunk_chars = _resolve_pipeline_chunk_max_chars(run_config)
        chapter_work_items = _build_chunk_work_items(chapters=chapters[incremental_scope:])
        chunk_jobs = _build_chunk_jobs(chapter_work_items=chapter_work_items, max_chunk_chars=max_chunk_chars)
        chunk_count = len(chunk_jobs)
        run.config_json = {
            **(run.config_json or {}),
            "pipeline_chunking": {
                "enabled": chunk_count > 1,
                "chunk_max_chars": max_chunk_chars,
                "chunk_count": chunk_count,
            },
        }

    llm_probe_text: str | None = None
    total_segments = 0
    segment_payloads: list[dict[str, object]] = []
    if incremental_scope > 0:
        with _record_pipeline_stage(
            step_records=step_records,
            stage_name="copy_incremental_segments",
            completed_stages=completed_stages,
        ):
            prior_run = _get_latest_completed_run_before(
                session=session,
                project_id=project.id,
                current_run_id=run.id,
            )
            if prior_run is not None:
                segment_payloads.extend(
                    _copy_incremental_run_payloads(
                        session=session,
                        source_run_id=prior_run.id,
                        target_run_id=run.id,
                        chapter_scope=incremental_scope,
                    )
                )
                total_segments = len(segment_payloads)

    chunk_payloads: list[dict[str, object]] = []
    with _record_pipeline_stage(
        step_records=step_records,
        stage_name="build_chunk_payloads",
        completed_stages=completed_stages,
    ):
        if chunk_jobs:
            with ThreadPoolExecutor(max_workers=min(8, len(chunk_jobs))) as executor:
                futures = {
                    executor.submit(
                        _build_chunk_segment_payloads,
                        chunk_index=chunk_index,
                        chunk_count=chunk_count,
                        chapter_batch=chapter_batch,
                        max_chars=max_chars,
                        name_to_verbalized=name_to_verbalized,
                        character_lookup=character_lookup,
                        character_pronunciations=character_pronunciations,
                        voice_config=voice_config,
                        llm_confidence_threshold=llm_confidence_threshold,
                        deep_semantic_refinement=deep_semantic_refinement,
                    ): chunk_index
                    for chunk_index, chapter_batch in enumerate(chunk_jobs, start=1)
                }
                ordered_payloads: dict[int, dict[str, object]] = {}
                for future in as_completed(futures):
                    chunk_payload = future.result()
                    ordered_payloads[int(chunk_payload.get("chunk_index", 0))] = chunk_payload

                for chunk_index in sorted(ordered_payloads):
                    chunk_payloads.append(ordered_payloads[chunk_index])

    with _record_pipeline_stage(
        step_records=step_records,
        stage_name="merge_segment_payloads",
        completed_stages=completed_stages,
    ):
        new_segment_payloads: list[dict[str, object]] = []
        new_sub_segment_payloads: list[list[dict[str, object]]] = []
        persisted_segment_records: list[tuple[Segment, dict[str, object]]] = []
        for chunk_payload in chunk_payloads:
            new_segment_payloads.extend(chunk_payload.get("segment_payloads", []))
            new_sub_segment_payloads.extend(chunk_payload.get("sub_segment_payloads", []))
            if llm_probe_text is None:
                candidate_probe_text = chunk_payload.get("llm_probe_text")
                if isinstance(candidate_probe_text, str) and candidate_probe_text:
                    llm_probe_text = candidate_probe_text

        segment_payloads.extend(new_segment_payloads)
        total_segments = len(segment_payloads)

        chapter_id_by_index = {int(item.chapter_index): item.id for item in chapters}

        for segment_payload, boundary_payloads in zip(new_segment_payloads, new_sub_segment_payloads):
            chapter_index = int(segment_payload.get("chapter_id", 0))
            segment = Segment(
                run_id=run.id,
                chapter_id=chapter_id_by_index[chapter_index],
                segment_index=int(segment_payload["segment_index"]),
                segment_json=segment_payload,
            )
            session.add(segment)
            session.flush()

            segment_payload_id = str(segment_payload["segment_id"])
            for boundary_payload in boundary_payloads:
                if not isinstance(boundary_payload, dict):
                    continue
                session.add(
                    SubSegmentTag(
                        run_id=run.id,
                        chapter_id=chapter_id_by_index[chapter_index],
                        segment_id=segment.id,
                        sub_segment_id=f"{segment_payload_id}-{int(boundary_payload.get('boundary_index', 0)):02d}",
                        sub_segment_index=int(boundary_payload.get("boundary_index", 0)),
                        shift_type=str(boundary_payload.get("shift_type")),
                        boundary_start_char=int(boundary_payload.get("boundary_start_char", 0)),
                        boundary_end_char=int(boundary_payload.get("boundary_end_char", 0)),
                        from_label=(None if boundary_payload.get("from_label") is None else str(boundary_payload.get("from_label"))),
                        to_label=(None if boundary_payload.get("to_label") is None else str(boundary_payload.get("to_label"))),
                        from_text=(None if boundary_payload.get("from_text") is None else str(boundary_payload.get("from_text"))),
                        to_text=(None if boundary_payload.get("to_text") is None else str(boundary_payload.get("to_text"))),
                        confidence=float(boundary_payload.get("confidence", 0.0)),
                        tags=boundary_payload.get("tags", {}),
                        evidence=boundary_payload.get("evidence", {}),
                    )
            )

            total_segments += 1
            persisted_segment_records.append((segment, segment_payload))

        chapter_content_integrity = _build_chapter_content_integrity_report(
            chapters=chapters,
            segment_payloads=segment_payloads,
        )
        run_config_with_integrity = dict(run.config_json or {})
        run_config_with_integrity["chapter_content_integrity"] = chapter_content_integrity
        run.config_json = run_config_with_integrity

        if not bool(chapter_content_integrity.get("is_content_preserved")):
            raise PipelineError(
                "chapter-content integrity check failed during chapter reconstruction",
                metadata={"chapter_content_integrity": chapter_content_integrity},
            )

    llm_enabled = bool(run_config.get("llm_enabled", False))
    resolved_project_id = project_id if project_id is not None else project.id
    llm_probe_success = False
    with _record_pipeline_stage(
        step_records=step_records,
        stage_name="run_llm_probe",
        completed_stages=completed_stages,
    ):
        if llm_enabled and llm_probe_text:
            llm_probe_success = _run_llm_probe(
                session=session,
                project=project,
                run=run,
                run_config=run_config,
                input_text=llm_probe_text,
                project_id=resolved_project_id,
                principal_type=principal_type,
                principal_id=principal_id,
            )

        for persisted_segment, segment_payload in persisted_segment_records:
            needs_llm_refinement = bool(segment_payload.get("llm_refinement_needed"))
            segment_payload["refinement_source"] = (
                "llm" if (needs_llm_refinement and llm_probe_success) else "rule_only"
            )
            persisted_segment.segment_json = dict(segment_payload)
            flag_modified(persisted_segment, "segment_json")

    with _record_pipeline_stage(
        step_records=step_records,
        stage_name="derive_character_analytics",
        completed_stages=completed_stages,
    ):
        character_occurrence_analytics = build_character_occurrence_analytics(
            chapters=chapters,
            characters=characters,
            segment_payloads=segment_payloads,
        )
        run.config_json = {
            **(run.config_json or {}),
            **character_occurrence_analytics,
        }

    with _record_pipeline_stage(
        step_records=step_records,
        stage_name="finalize_run_and_build_export",
        completed_stages=completed_stages,
    ):
        run.status = "completed"
        run.finished_at = datetime.now(timezone.utc)
        session.flush()
        export_payload = build_run_export(session, project, run)

    pipeline_completed_at = time.perf_counter()
    performance_telemetry = _build_performance_telemetry_payload(
        step_records=step_records,
        total_duration_ms=int((pipeline_completed_at - pipeline_started_at) * 1000),
        status="completed",
    )
    run_config_with_telemetry = dict(run.config_json or {})
    run_config_with_telemetry["performance_telemetry"] = performance_telemetry
    run.config_json = run_config_with_telemetry
    _append_pipeline_performance_changelog_entry(
        session=session,
        run=run,
        telemetry=performance_telemetry,
    )
    session.flush()

    return {
        "segment_count": total_segments,
        "export": export_payload,
    }


def _run_llm_probe(
    session: Session,
    project: Project,
    run: Run,
    run_config: dict,
    input_text: str,
    *,
    project_id: int | str | None = None,
    principal_type: str | None = None,
    principal_id: str | None = None,
) -> bool:
    provider = _normalize_provider_name_for_llm(run_config.get("provider_name", "openrouter"))
    requested_provider = provider
    pinned_model_identifier = str(run_config.get("deterministic_model_identifier") or "").strip()
    pinned_model = pinned_model_identifier if run_config.get("deterministic_mode") else None

    if not is_supported_provider(provider):
        _persist_run_llm_model_metadata(
            run=run,
            provider=provider,
            model_identifier=None,
        )
        session.add(
            LLMCall(
                run_id=run.id,
                provider=provider,
                task_type=LLMTaskType.SENTIMENT_PROBE.value,
                success=False,
                request_count=0,
                token_usage_estimate=None,
                detail="unsupported_provider",
                is_cache_hit=False,
                model_identifier=None,
                called_at=datetime.now(timezone.utc),
            )
        )
        session.flush()
        return False

    if not is_provider_enabled(session=session, provider=provider):
        _persist_run_llm_model_metadata(
            run=run,
            provider=provider,
            model_identifier=None,
        )
        session.add(
            LLMCall(
                run_id=run.id,
                provider=provider,
                task_type=LLMTaskType.SENTIMENT_PROBE.value,
                success=False,
                request_count=0,
                token_usage_estimate=None,
                detail="provider_disabled",
                is_cache_hit=False,
                model_identifier=None,
                called_at=datetime.now(timezone.utc),
            )
        )
        session.flush()
        return False

    max_calls_per_day = int(run_config.get("max_calls_per_day", 25))
    settings = get_settings()
    run_scoped_settings = _build_run_scoped_llm_settings(
        settings=settings,
        run_config=run_config,
    )
    provider_candidates = get_provider_priority_order(
        session=session,
        requested_provider=provider,
        settings=run_scoped_settings,
        max_calls_per_day=max_calls_per_day,
    )
    if provider not in provider_candidates:
        provider_candidates = (provider, *provider_candidates)
    configuration_snapshot_id = _resolve_configuration_snapshot_id(
        project=project,
        run=run,
        run_config=run_config,
    )

    request = LLMRequest(
        request_id=str(uuid4()),
        project_id=project.id,
        task_type=LLMTaskType.SENTIMENT_PROBE.value,
        input_text=input_text,
        expected_schema={"sentiment": "string", "confidence": "number"},
        configuration_snapshot_id=configuration_snapshot_id,
    )

    final_provider = provider
    final_request_count = 0
    final_token_usage = None
    final_detail = None
    final_model_identifier = None
    final_called_at = None
    success = False
    all_providers_exhausted = False
    request_attempt_index = 0

    for active_provider in provider_candidates:
        if not is_supported_provider(active_provider):
            continue

        provider_requestable, provider_request_reason = llm_router.is_provider_requestable(
            session=session,
            settings=run_scoped_settings,
            provider_name=active_provider,
            max_calls_per_day=max_calls_per_day,
            project_id=project_id,
            principal_type=principal_type,
            principal_id=principal_id,
        )
        if not provider_requestable:
            final_provider = active_provider
            final_detail = provider_request_reason
            if active_provider != provider_candidates[-1]:
                continue
            break

        runtime_base_url, runtime_model_identifier, runtime_api_key = get_provider_runtime_settings(
            settings=run_scoped_settings,
            provider_name=active_provider,
        )
        if pinned_model and active_provider == provider:
            runtime_model_identifier = pinned_model
        cached_response = _get_cached_llm_response(
            session=session,
            input_text=input_text,
            task_type=LLMTaskType.SENTIMENT_PROBE.value,
            configuration_snapshot_id=configuration_snapshot_id,
            model_identifier=runtime_model_identifier,
        )
        if cached_response is not None:
            cached_payload = cached_response.response_payload
            final_provider = active_provider
            final_success = bool(cached_payload.get("success", False))
            final_token_usage = cached_payload.get("token_usage_estimate")
            final_detail = cached_payload.get("detail")
            final_model_identifier = str(runtime_model_identifier)
            final_called_at = _coerce_call_timestamp(cached_payload.get("called_at"))
            success = final_success
            final_request_count = 0
            _persist_run_llm_model_metadata(
                run=run,
                provider=final_provider,
                model_identifier=final_model_identifier,
            )
            session.add(
                LLMCall(
                    run_id=run.id,
                    provider=final_provider,
                    task_type=LLMTaskType.SENTIMENT_PROBE.value,
                    success=final_success,
                    request_count=final_request_count,
                    token_usage_estimate=final_token_usage,
                    detail=(None if final_success else str(final_detail) if final_detail is not None else "cache_hit"),
                    is_cache_hit=True,
                    model_identifier=final_model_identifier,
                    called_at=final_called_at,
                )
            )
            session.flush()
            return success

        runtime_api_keys = get_provider_api_keys(
            settings=run_scoped_settings,
            provider_name=active_provider,
        )
        if not runtime_api_keys and runtime_api_key:
            runtime_api_keys = [runtime_api_key]

        if not runtime_api_keys:
            runtime_api_keys = [None]

        router = LLMRouter(openrouter_base_url=runtime_base_url)
        provider_failure_detail: str | None = None

        for index, api_key in enumerate(runtime_api_keys):
            if api_key is not None:
                key_allowed, _ = consume_api_key_quota(
                    session=session,
                    provider=active_provider,
                    provider_api_key=api_key,
                    max_calls_per_day=max_calls_per_day,
                    project_id=project_id,
                    principal_type=principal_type,
                    principal_id=principal_id,
                )
                if not key_allowed:
                    provider_failure_detail = "quota_reached"
                    continue
            else:
                pass

            allowed, request_count = consume_quota(
                session=session,
                provider=active_provider,
                max_calls_per_day=max_calls_per_day,
                project_id=project_id,
                principal_type=principal_type,
                principal_id=principal_id,
            )
            if not allowed:
                provider_failure_detail = "quota_reached"
                final_request_count = request_count
                break

            final_request_count = request_count
            response = router.call(
                request=request,
                provider_name=active_provider,
                model_identifier=runtime_model_identifier,
                api_key=api_key,
            )
            request_attempt_index += 1
            session.add(
                ProviderApiKeyUsageAudit(
                    run_id=run.id,
                    provider=active_provider,
                    task_type=LLMTaskType.SENTIMENT_PROBE.value,
                    request_id=request.request_id,
                    attempt_index=request_attempt_index,
                    provider_api_key_masked=_build_provider_api_key_audit_mask(api_key),
                    provider_api_key_fingerprint=_build_provider_api_key_fingerprint(api_key),
                    model_identifier=response.model_identifier,
                    success=response.success_flag,
                    error_code=None if response.success_flag else response.error_code,
                    token_usage_estimate=response.token_usage_estimate,
                    called_at=_coerce_call_timestamp(response.timestamp),
                )
            )

            if response.success_flag:
                mark_provider_available(
                    session=session,
                    provider=active_provider,
                    project_id=project_id,
                    principal_type=principal_type,
                    principal_id=principal_id,
                )
                mark_provider_successful_call(
                    session=session,
                    provider=active_provider,
                    project_id=project_id,
                    principal_type=principal_type,
                    principal_id=principal_id,
                )
                if api_key is not None:
                    mark_api_key_successful_call(
                        session=session,
                        provider=active_provider,
                        provider_api_key=api_key,
                        project_id=project_id,
                        principal_type=principal_type,
                        principal_id=principal_id,
                    )
                final_provider = active_provider
                final_token_usage = response.token_usage_estimate
                final_detail = response.raw_output
                final_model_identifier = response.model_identifier
                final_called_at = _coerce_call_timestamp(response.timestamp)
                payload = {
                    "success": response.success_flag,
                    "detail": response.raw_output,
                    "token_usage_estimate": response.token_usage_estimate,
                    "called_at": _coerce_call_timestamp(response.timestamp).isoformat(),
                }
                session.add(
                    LLMCache(
                        input_text_hash=_build_llm_cache_key(input_text),
                        task_type=LLMTaskType.SENTIMENT_PROBE.value,
                        configuration_snapshot_id=configuration_snapshot_id,
                        model_identifier=(str(response.model_identifier) if response.model_identifier else runtime_model_identifier),
                        response_payload=payload,
                    )
                )
                success = True
                break

            provider_failure_detail = response.error_code or "provider_error"
            final_detail = provider_failure_detail
            final_token_usage = response.token_usage_estimate
            final_model_identifier = response.model_identifier
            final_called_at = _coerce_call_timestamp(response.timestamp)

            if response.error_code in {"rate_limit", "quota"}:
                if api_key is not None:
                    mark_api_key_rate_limited(
                        session=session,
                        provider=active_provider,
                        provider_api_key=api_key,
                        project_id=project_id,
                        principal_type=principal_type,
                        principal_id=principal_id,
                    )
                    if response.error_code == "rate_limit":
                        mark_api_key_reset_at(
                            session=session,
                            provider=active_provider,
                            provider_api_key=api_key,
                            reset_at=response.rate_limit_reset_at,
                            project_id=project_id,
                            principal_type=principal_type,
                            principal_id=principal_id,
                        )
                is_last_key = index + 1 >= len(runtime_api_keys)
                if not is_last_key:
                    continue

                mark_provider_rate_limited(
                    session=session,
                    provider=active_provider,
                    project_id=project_id,
                    principal_type=principal_type,
                    principal_id=principal_id,
                )
                if response.error_code == "rate_limit":
                    mark_provider_reset_at(
                        session=session,
                        provider=active_provider,
                        reset_at=response.rate_limit_reset_at,
                        project_id=project_id,
                        principal_type=principal_type,
                        principal_id=principal_id,
                    )

            else:
                break
        if success:
            break

        if final_detail is None:
            final_detail = provider_failure_detail

        final_provider = active_provider
        if provider_failure_detail in {"rate_limit", "quota", "quota_reached"}:
            if active_provider != provider_candidates[-1]:
                continue
            all_providers_exhausted = True
            break

        if provider_failure_detail is not None:
            break

    if all_providers_exhausted or (not success and final_detail in {"rate_limit", "quota", "quota_reached"} and provider_candidates):
        _append_llm_rule_only_state(
            run=run,
            reason=(str(final_detail) if final_detail is not None else "all_providers_unavailable"),
            last_provider=final_provider,
        )

    session.add(
        LLMCall(
            run_id=run.id,
            provider=final_provider,
            task_type=LLMTaskType.SENTIMENT_PROBE.value,
            success=success,
            request_count=final_request_count,
            token_usage_estimate=final_token_usage,
            detail=(None if success else final_detail),
            is_cache_hit=False,
            model_identifier=final_model_identifier,
            called_at=(
                _coerce_call_timestamp(None)
                if final_called_at is None
                else final_called_at
            ),
            )
        )

    _persist_run_llm_model_metadata(
        run=run,
        provider=final_provider,
        model_identifier=final_model_identifier,
    )
    session.flush()

    if bool(run_config.get("deterministic_mode")) and final_provider != requested_provider:
        fallback_reason = final_detail or "provider_fallback"
        _append_deterministic_replay_warning(
            run=run,
            requested_provider=requested_provider,
            actual_provider=final_provider,
            reason=fallback_reason,
        )
        session.flush()

    return success


def _assert_pipeline_stage_order(
    completed_stages: list[str],
    stage_name: str,
) -> None:
    allowed_previous_stages = _PIPELINE_STAGE_PREDECESSORS.get(stage_name)
    if allowed_previous_stages is None:
        raise PipelineError(f"Unknown pipeline stage '{stage_name}'.")

    if stage_name in completed_stages:
        raise PipelineError(f"Pipeline stage '{stage_name}' was already completed.")

    if not allowed_previous_stages:
        if completed_stages:
            raise PipelineError(f"Pipeline stage '{stage_name}' must be the first stage.")
        return

    if not completed_stages:
        raise PipelineError(
            f"Pipeline stage '{stage_name}' cannot run before {' or '.join(allowed_previous_stages)}."
        )

    last_stage = completed_stages[-1]
    if last_stage not in allowed_previous_stages:
        raise PipelineError(
            "Pipeline ordering guard violated. "
            f"Expected one of {', '.join(allowed_previous_stages)} before '{stage_name}', "
            f"but last completed stage was '{last_stage}'."
        )


@contextmanager
def _record_pipeline_stage(
    step_records: list[dict[str, object]],
    stage_name: str,
    completed_stages: list[str],
) -> Iterator[None]:
    _assert_pipeline_stage_order(
        completed_stages=completed_stages,
        stage_name=stage_name,
    )
    with _record_pipeline_step(step_records=step_records, step_name=stage_name):
        yield
    completed_stages.append(stage_name)
