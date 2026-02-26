from app.services.tagging import (
    build_high_ambiguity_dialogue_block_warnings,
    build_low_confidence_speaker_attribution_warnings,
)


def test_build_low_confidence_speaker_attribution_warnings_includes_dialogue_without_attribution() -> None:
    payloads = [
        {
            "segment_id": "seg-001",
            "segment_index": 1,
            "chapter_id": 1,
            "type": "dialogue",
            "speaker": "unknown",
            "speaker_confidence": 0.2,
            "speaker_state": "uncertain",
            "ambiguity_flags": ["ambiguous_speaker_attribution"],
        },
        {
            "segment_id": "seg-002",
            "segment_index": 2,
            "chapter_id": 1,
            "type": "narration",
            "speaker": "narrative_guide",
            "speaker_confidence": 0.2,
            "speaker_state": "uncertain",
            "ambiguity_flags": [],
        },
    ]

    warnings = build_low_confidence_speaker_attribution_warnings(payloads)

    assert len(warnings) == 1
    warning = warnings[0]
    assert warning["type"] == "low_confidence_speaker_attribution"
    assert warning["level"] == "warning"
    assert warning["source"] == "tagging"
    assert warning["segment_id"] == "seg-001"
    assert warning["speaker"] == "unknown"
    assert warning["speaker_confidence"] == 0.2


def test_build_low_confidence_speaker_attribution_warnings_ignores_confident_or_non_dialogue_segments() -> None:
    payloads = [
        {
            "segment_id": "seg-003",
            "segment_index": 3,
            "chapter_id": 1,
            "type": "dialogue",
            "speaker": "alice",
            "speaker_confidence": 0.95,
            "speaker_state": "certain",
            "ambiguity_flags": [],
        },
        {
            "segment_id": "seg-004",
            "segment_index": 4,
            "chapter_id": 1,
            "type": "narration",
            "speaker": "narrative_guide",
            "speaker_confidence": 0.2,
            "speaker_state": "uncertain",
            "ambiguity_flags": [],
        },
    ]

    warnings = build_low_confidence_speaker_attribution_warnings(payloads)
    assert not warnings


def test_build_high_ambiguity_dialogue_block_warnings_includes_mixed_dialogue_blocks() -> None:
    payloads = [
        {
            "segment_id": "seg-005",
            "segment_index": 5,
            "chapter_id": 1,
            "type": "mixed",
            "speaker": "unknown",
            "speaker_confidence": 0.2,
            "speaker_state": "uncertain",
            "ambiguity_flags": [
                "ambiguous_speaker_attribution",
                "mixed_structure",
                "mixed_dialogue_and_narration",
            ],
        },
        {
            "segment_id": "seg-006",
            "segment_index": 6,
            "chapter_id": 1,
            "type": "dialogue",
            "speaker": "alice",
            "speaker_confidence": 0.84,
            "speaker_state": "uncertain",
            "ambiguity_flags": ["ambiguous_speaker_attribution", "low_speaker_confidence"],
        },
    ]

    warnings = build_high_ambiguity_dialogue_block_warnings(payloads, ambiguity_flag_threshold=2)

    assert len(warnings) == 2
    assert any(warning["type"] == "high_ambiguity_dialogue_block" for warning in warnings)
    warning = warnings[0]
    assert warning["level"] == "warning"
    assert warning["source"] == "tagging"
    assert warning["segment_id"] == "seg-005"
    assert warning["speaker"] == "unknown"
    assert warning["ambiguity_flags"] == [
        "ambiguous_speaker_attribution",
        "mixed_dialogue_and_narration",
        "mixed_structure",
    ]


def test_build_high_ambiguity_dialogue_block_warnings_ignores_insufficient_ambiguity() -> None:
    payloads = [
        {
            "segment_id": "seg-007",
            "segment_index": 7,
            "chapter_id": 1,
            "type": "mixed",
            "speaker": "alice",
            "speaker_confidence": 0.9,
            "speaker_state": "certain",
            "ambiguity_flags": ["ambiguous_speaker_attribution"],
        },
        {
            "segment_id": "seg-008",
            "segment_index": 8,
            "chapter_id": 1,
            "type": "narration",
            "speaker": "narrative_guide",
            "speaker_confidence": 0.3,
            "speaker_state": "uncertain",
            "ambiguity_flags": [
                "ambiguous_speaker_attribution",
                "mixed_structure",
                "mixed_dialogue_and_narration",
            ],
        },
    ]

    warnings = build_high_ambiguity_dialogue_block_warnings(payloads, ambiguity_flag_threshold=2)
    assert not warnings
