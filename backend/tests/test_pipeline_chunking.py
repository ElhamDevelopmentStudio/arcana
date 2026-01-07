from app.services.pipeline import (
    _build_chapter_chunks,
    _build_chunk_jobs,
    _build_chunk_segment_payloads,
    _build_chunk_work_items,
    _resolve_pipeline_chunk_max_chars,
)


class _ChapterFixture:
    def __init__(self, chapter_index: int, normalized_text: str) -> None:
        self.chapter_index = chapter_index
        self.normalized_text = normalized_text


def test_resolve_pipeline_chunk_max_chars_default_and_override() -> None:
    default = 120_000
    assert _resolve_pipeline_chunk_max_chars({}, default=default) == default
    assert _resolve_pipeline_chunk_max_chars({"pipeline_chunk_max_chars": "64000"}, default=default) == 64000
    assert _resolve_pipeline_chunk_max_chars({"pipeline_chunk_max_chars": 0}, default=default) == default
    assert _resolve_pipeline_chunk_max_chars({"pipeline_chunk_max_chars": "bad"}, default=default) == default


def test_build_chapter_chunks_prefers_input_character_order() -> None:
    chapters = [
        _ChapterFixture(chapter_index=3, normalized_text="c" * 700),
        _ChapterFixture(chapter_index=1, normalized_text="a" * 700),
        _ChapterFixture(chapter_index=2, normalized_text="b" * 700),
    ]
    chunks = _build_chapter_chunks(chapters, max_chunk_chars=1200)
    chunk_indexes = [[chapter.chapter_index for chapter in chunk] for chunk in chunks]
    assert chunk_indexes == [[1], [2], [3]]


def test_build_chapter_chunks_isolation_for_large_chapter() -> None:
    chapters = [
        _ChapterFixture(chapter_index=1, normalized_text="a" * 1200),
        _ChapterFixture(chapter_index=2, normalized_text="b" * 200),
        _ChapterFixture(chapter_index=3, normalized_text="c" * 200),
    ]
    chunks = _build_chapter_chunks(chapters, max_chunk_chars=500)
    chunk_indexes = [[chapter.chapter_index for chapter in chunk] for chunk in chunks]
    assert chunk_indexes == [[1], [2, 3]]


class _ChunkWorkItemFixture:
    def __init__(
        self,
        chapter_id: int,
        chapter_index: int,
        chapter_internal_id: str,
        normalized_text: str,
        offset_map: list[dict[str, int]],
    ) -> None:
        self.chapter_id = chapter_id
        self.chapter_index = chapter_index
        self.chapter_internal_id = chapter_internal_id
        self.normalized_text = normalized_text
        self.original_to_normalized_offset_map = offset_map


def test_build_chunk_jobs_is_stable() -> None:
    chapters = [
        _ChunkWorkItemFixture(
            chapter_id=2,
            chapter_index=2,
            chapter_internal_id="ch2",
            normalized_text="b" * 2,
            offset_map=[],
        ),
        _ChunkWorkItemFixture(
            chapter_id=1,
            chapter_index=1,
            chapter_internal_id="ch1",
            normalized_text="a" * 2,
            offset_map=[],
        ),
        _ChunkWorkItemFixture(
            chapter_id=3,
            chapter_index=3,
            chapter_internal_id="ch3",
            normalized_text="c" * 2,
            offset_map=[],
        ),
    ]
    chunks = _build_chunk_jobs(chapters, max_chunk_chars=3)
    chunk_indexes = [[chapter.chapter_index for chapter in chunk] for chunk in chunks]
    assert chunk_indexes == [[1], [2], [3]]


def test_build_chunk_segment_payloads_uses_stable_chunk_metadata() -> None:
    chapter_work_items = _build_chunk_work_items(
        [
            _ChunkWorkItemFixture(
                chapter_id=1,
                chapter_index=2,
                chapter_internal_id="ch2",
                normalized_text="Alice speaks.",
                offset_map=[],
            ),
            _ChunkWorkItemFixture(
                chapter_id=2,
                chapter_index=1,
                chapter_internal_id="ch1",
                normalized_text="Bob whispers.",
                offset_map=[],
            ),
        ]
    )
    payload = _build_chunk_segment_payloads(
        chunk_index=1,
        chunk_count=1,
        chapter_batch=chapter_work_items,
        max_chars=255,
        name_to_verbalized={},
        character_lookup={},
        character_pronunciations={},
        voice_config={},
        llm_confidence_threshold=0.6,
        deep_semantic_refinement=False,
    )

    assert payload["chunk_index"] == 1
    assert payload["chunk_count"] == 1
    assert payload["segment_payloads"]
    assert [segment["chapter_internal_id"] for segment in payload["segment_payloads"]] == ["ch2", "ch1"]
