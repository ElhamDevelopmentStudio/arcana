from app.services.tagging import (
    build_high_ambiguity_dialogue_block_warnings,
    build_low_confidence_speaker_attribution_warnings,
    build_unstable_rapid_emotion_shift_warnings,
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


def test_build_unstable_rapid_emotion_shift_warnings() -> None:
    payloads = [
        {
            "segment_id": "seg-009",
            "segment_index": 9,
            "chapter_id": 1,
            "type": "narration",
            "emotion_shift": {
                "has_shift": True,
                "confidence": 0.93,
                "evidence": {
                    "transition_count": 5,
                    "unit_count": 10,
                },
            },
        },
        {
            "segment_id": "seg-010",
            "segment_index": 10,
            "chapter_id": 1,
            "type": "narration",
            "emotion_shift": {
                "has_shift": True,
                "confidence": 0.95,
                "evidence": {
                    "transition_count": 2,
                    "unit_count": 10,
                },
            },
        },
    ]

    warnings = build_unstable_rapid_emotion_shift_warnings(payloads)

    assert len(warnings) == 1
    warning = warnings[0]
    assert warning["type"] == "unstable_rapid_emotion_shift"
    assert warning["level"] == "warning"
    assert warning["source"] == "tagging"
    assert warning["segment_id"] == "seg-009"
    assert warning["transition_count"] == 5
    assert warning["unit_count"] == 10
    assert isinstance(warning["emotion_shift_density"], float)
    assert warning["emotion_shift_density"] > 0


def test_build_unstable_rapid_emotion_shift_warnings_ignores_sparse_shifts() -> None:
    payloads = [
        {
            "segment_id": "seg-011",
            "segment_index": 11,
            "chapter_id": 1,
            "type": "narration",
            "emotion_shift": {
                "has_shift": True,
                "confidence": 0.83,
                "evidence": {
                    "transition_count": 2,
                    "unit_count": 12,
                },
            },
        },
    ]

    warnings = build_unstable_rapid_emotion_shift_warnings(
        payloads,
        transition_threshold=4,
        density_threshold=0.5,
    )
    assert not warnings
