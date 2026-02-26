from app.services.tagging import (
    detect_dialogue_blocks,
    detect_emotion_shift,
    detect_shift_markers,
    detect_internal_external_speech_shift,
    detect_narration_internal_thought_shift,
    detect_narration_blocks,
    detect_structure,
    detect_tone_reversal,
    tag_segment,
)


def test_detect_dialogue_blocks_recognizes_quotes_and_dash_lines() -> None:
    text = '"Hello," said Alex.\n- This is his reply.\nThen the narrator resumed the thought.'
    blocks = detect_dialogue_blocks(text)

    assert blocks == [
        {"type": "dialogue", "text": '"Hello," said Alex.'},
        {"type": "dialogue", "text": "- This is his reply."},
        {"type": "narration", "text": "Then the narrator resumed the thought."},
    ]


def test_detect_structure_returns_dialogue_for_dialogue_blocks() -> None:
    assert detect_structure('"Wait," she asked.') == "dialogue"
    assert detect_structure("He shrugged.") == "narration"


def test_detect_structure_detects_internal_thought_blocks() -> None:
    assert detect_structure("She thought he might never return.") == "internal thought"


def test_detect_structure_detects_action_blocks() -> None:
    assert detect_structure("Mira dashed across the hall and slammed the door.") == "action"


def test_detect_structure_detects_description_blocks() -> None:
    assert detect_structure("The moonlight poured through the cracked window and painted silver bars.") == "description"


def test_detect_structure_returns_mixed_when_dialogue_and_narration_mix() -> None:
    assert (
        detect_structure('"We should leave now," she said. The corridor stayed silent afterward.')
        == "mixed"
    )


def test_tag_segment_includes_type_confidence() -> None:
    tags = tag_segment('"Wait," she asked.')
    assert isinstance(tags["type_confidence"], float)
    assert 0.0 <= tags["type_confidence"] <= 1.0
    assert tags["type_confidence"] > 0.6
    assert tags["type_state"] == "certain"
    assert isinstance(tags["type_evidence"], dict)
    assert set(tags["type_evidence"].keys()) >= {"method", "signals"}
    assert isinstance(tags["type_evidence"]["signals"], list)
    assert len(tags["type_evidence"]["signals"]) >= 1


def test_tag_segment_includes_dialogue_blocks_for_traceability() -> None:
    tags = tag_segment('"Wait," she asked.')
    assert tags["type"] == "dialogue"
    assert tags["dialogue_blocks"] == [{"type": "dialogue", "text": '"Wait," she asked.'}]
    assert tags["narration_blocks"] == []


def test_tag_segment_includes_speaker_evidence() -> None:
    tags = tag_segment('"Wait," she said.')
    assert isinstance(tags["speaker_evidence"], dict)
    assert tags["speaker_evidence"]["status"] == "found"
    assert tags["speaker_evidence"]["method"] == "speaker_pattern_lookup"
    assert tags["speaker_state"] == "certain"
    speaker_span = tags["speaker_evidence"]["speaker_span"]
    assert isinstance(speaker_span, dict)
    assert speaker_span["text"] == "she"
    assert speaker_span["start_char"] < speaker_span["end_char"]


def test_tag_segment_marks_unknown_state_for_unattributed_narrative_speaker() -> None:
    tags = tag_segment("The fire burned low in the corner.")
    assert tags["speaker_confidence"] == 0.2
    assert tags["speaker_state"] == "unknown"


def test_tag_segment_flags_ambiguous_speaker_without_attribution() -> None:
    tags = tag_segment('"Hold on."')
    assert tags["speaker"] == "unknown"
    assert tags["speaker_state"] in {"uncertain", "unknown"}
    assert "ambiguity_flags" in tags
    assert "ambiguous_speaker_attribution" in tags["ambiguity_flags"]
    assert "low_speaker_confidence" not in tags["ambiguity_flags"]


def test_tag_segment_includes_tension_contribution_tag() -> None:
    tags = tag_segment("He bolted to the door as she shouted, \"Help!\" then the alarm rang.")
    tension = tags["tension_contribution"]
    assert isinstance(tension, dict)
    assert set(tension.keys()) == {"value", "level", "confidence", "state", "evidence"}
    assert isinstance(tension["value"], float)
    assert 0.0 <= tension["value"] <= 1.0
    assert tension["level"] in {"high", "moderate", "low", "calm"}
    assert tension["value"] > 0.0
    assert isinstance(tension["confidence"], float)
    assert 0.0 <= tension["confidence"] <= 1.0
    assert isinstance(tension["evidence"], dict)
    assert tension["evidence"]["signal_count"] >= 0
    assert tension["evidence"]["intensifier_count"] >= 0
    assert tension["state"] in {"certain", "uncertain", "unknown"}


def test_tag_segment_includes_emotion_evidence() -> None:
    tags = tag_segment("He was happy, calm, and hopeful.")
    emotion_evidence = tags["emotion_evidence"]
    assert isinstance(emotion_evidence, dict)
    assert set(emotion_evidence.keys()) >= {
        "method",
        "positive_signals",
        "negative_signals",
        "positive_signal_count",
        "negative_signal_count",
        "total_signal_count",
    }
    assert emotion_evidence["positive_signal_count"] >= 1
    assert isinstance(emotion_evidence["positive_signals"], list)
    assert isinstance(emotion_evidence["negative_signals"], list)


def test_tag_segment_tension_contribution_remains_low_for_stable_description() -> None:
    tags = tag_segment("The moonlight painted the room in silver lines.")
    tension = tags["tension_contribution"]
    assert isinstance(tension, dict)
    assert tension["level"] in {"calm", "low"}
    assert tension["value"] < 0.35
    assert isinstance(tension["confidence"], float)
    assert 0.0 <= tension["confidence"] <= 1.0


def test_tag_segment_includes_dominance_contribution_tag() -> None:
    tags = tag_segment('"Wait," Alice said.')
    dominance = tags["dominance_contribution"]
    assert isinstance(dominance, dict)
    assert set(dominance.keys()) == {"value", "level", "dominant_agent", "evidence", "confidence", "state"}
    assert isinstance(dominance["value"], float)
    assert 0.0 <= dominance["value"] <= 1.0
    assert dominance["level"] in {"dominant", "strong", "moderate", "low"}
    assert dominance["dominant_agent"] == "alice"
    assert isinstance(dominance["evidence"], dict)
    assert "speaker_resolved" in dominance["evidence"]
    assert "pronoun_reference_count" in dominance["evidence"]
    assert "proper_noun_hits" in dominance["evidence"]
    assert "proper_noun_spans" in dominance["evidence"]
    assert isinstance(dominance["confidence"], float)
    assert 0.0 <= dominance["confidence"] <= 1.0
    assert dominance["state"] in {"certain", "uncertain", "unknown"}


def test_tag_segment_dominance_contribution_defaults_to_narrative_guide_when_no_speaker() -> None:
    tags = tag_segment("The moonlight painted the room in silver lines.")
    dominance = tags["dominance_contribution"]
    assert isinstance(dominance, dict)
    assert dominance["dominant_agent"] == "narrative_guide"
    assert dominance["value"] >= 0.0


def test_tag_segment_emotion_outputs_include_valence_intensity_and_labels() -> None:
    tags = tag_segment("The night was calm and good, and hope was rising.")
    assert tags["emotion_valence"] > 0
    assert tags["emotion_intensity"] == abs(tags["emotion_valence"])
    assert tags["emotion_primary_label"] == "positive"
    assert tags["emotion_secondary_label"] in {"joyful", "hopeful", "gratitude", "calm"}
    assert tags["emotion_confidence"] == 0.6


def test_tag_segment_emotion_outputs_default_to_neutral_for_no_signal_words() -> None:
    tags = tag_segment("A branch crossed the floor.")
    assert tags["emotion_valence"] == 0.0
    assert tags["emotion_intensity"] == 0.0
    assert tags["emotion_primary_label"] == "neutral"
    assert tags["emotion_secondary_label"] == "neutral"
    assert tags["emotion_confidence"] == 0.4


def test_tag_segment_supports_expanded_emotion_taxonomy() -> None:
    basic_tags = tag_segment("Cold dark threat," " and danger", emotion_taxonomy="basic")
    expanded_tags = tag_segment("Cold dark threat," " and danger", emotion_taxonomy="expanded")

    assert basic_tags["emotion_primary_label"] == "negative"
    assert basic_tags["emotion_secondary_label"] == "angry"
    assert expanded_tags["emotion_primary_label"] == "fearful"
    assert expanded_tags["emotion_primary_label"] != basic_tags["emotion_primary_label"]
    assert expanded_tags["emotion_secondary_label"] == "fearful"


def test_detect_emotion_shift_respects_expanded_emotion_taxonomy() -> None:
    text = "Cold and dark winds rose, but hope returned with the dawn."
    basic_shift = detect_emotion_shift(text, emotion_taxonomy="basic")
    expanded_shift = detect_emotion_shift(text, emotion_taxonomy="expanded")

    assert basic_shift["has_shift"] is True
    assert expanded_shift["has_shift"] is True
    assert isinstance(basic_shift["from"], dict)
    assert isinstance(expanded_shift["from"], dict)
    assert basic_shift["from"]["label"] == "negative"
    assert expanded_shift["from"]["label"] == "fearful"
    assert basic_shift["to"]["label"] == "positive"
    assert expanded_shift["to"]["label"] in {"hopeful", "joyful", "gratitude", "calm"}


def test_detect_emotion_shift_identifies_positive_to_negative_transition() -> None:
    shift = detect_emotion_shift("He was happy, but fear and despair arrived.")
    assert shift["has_shift"] is True
    assert isinstance(shift["confidence"], float)
    assert shift["state"] in {"certain", "uncertain", "unknown"}
    assert shift["confidence"] > 0
    assert shift["from"] is not None
    assert shift["to"] is not None
    assert shift["from"]["label"] == "positive"
    assert shift["to"]["label"] == "negative"
    assert shift["from"]["secondary_label"] in {"joyful", "hopeful", "gratitude", "calm", "neutral", "positive"}
    assert shift["to"]["secondary_label"] in {"fearful", "angry", "grief", "violent", "negative"}


def test_detect_emotion_shift_stays_false_for_stable_emotion() -> None:
    shift = detect_emotion_shift("The moonlight painted the room in soft silver and gentle winds.")
    assert shift["has_shift"] is False
    assert shift["from"] is None
    assert shift["to"] is None
    assert shift["state"] in {"certain", "uncertain", "unknown"}
    assert shift["evidence"]["shift_count"] == 0


def test_tag_segment_includes_emotion_shift_field() -> None:
    tags = tag_segment("He smiled as dawn broke, but then the grave threat arrived.")
    assert isinstance(tags["emotion_shift"], dict)
    assert set(tags["emotion_shift"].keys()) >= {"has_shift", "from", "to", "confidence", "state", "evidence"}


def test_detect_narration_internal_thought_shift_identifies_transition() -> None:
    shift = detect_narration_internal_thought_shift("She thought the sun would rise, but the room stayed cold and silent.")
    assert shift["has_shift"] is True
    assert shift["state"] in {"certain", "uncertain", "unknown"}
    assert shift["from"] is not None
    assert shift["to"] is not None
    assert shift["confidence"] > 0
    assert shift["from"]["type"] in {"internal thought", "narration"}
    assert shift["to"]["type"] in {"internal thought", "narration"}
    assert shift["from"]["type"] != shift["to"]["type"]


def test_detect_narration_internal_thought_shift_stays_false_without_transition() -> None:
    shift = detect_narration_internal_thought_shift("She thought the moon had moved, while she considered the path and then thought again.")
    assert shift["has_shift"] is False
    assert shift["from"] is None
    assert shift["to"] is None
    assert shift["state"] in {"certain", "uncertain", "unknown"}
    assert shift["evidence"]["shift_count"] == 0


def test_tag_segment_includes_narration_internal_thought_shift_field() -> None:
    tags = tag_segment("She thought he would return, but the wind grew loud.")
    assert isinstance(tags["narration_internal_thought_shift"], dict)
    assert set(tags["narration_internal_thought_shift"].keys()) >= {"has_shift", "from", "to", "confidence", "state", "evidence"}


def test_detect_internal_external_speech_shift_identifies_transition() -> None:
    shift = detect_internal_external_speech_shift('She thought he would answer. "No," he said.')
    assert shift["has_shift"] is True
    assert shift["state"] in {"certain", "uncertain", "unknown"}
    assert shift["from"] is not None
    assert shift["to"] is not None
    assert shift["confidence"] > 0
    assert shift["from"]["type"] in {"internal thought", "dialogue"}
    assert shift["to"]["type"] in {"internal thought", "dialogue"}
    assert shift["from"]["type"] != shift["to"]["type"]


def test_detect_internal_external_speech_shift_stays_false_without_transition() -> None:
    shift = detect_internal_external_speech_shift('"The bridge is clear," said Mara.')
    assert shift["has_shift"] is False
    assert shift["from"] is None
    assert shift["to"] is None
    assert shift["state"] in {"certain", "uncertain", "unknown"}
    assert shift["evidence"]["shift_count"] == 0


def test_tag_segment_includes_internal_external_speech_shift_field() -> None:
    tags = tag_segment('She thought he would answer. "No," he said.')
    assert isinstance(tags["internal_external_speech_shift"], dict)
    assert set(tags["internal_external_speech_shift"].keys()) >= {"has_shift", "from", "to", "confidence", "state", "evidence"}


def test_detect_tone_reversal_identifies_dark_irony_transition() -> None:
    reversal = detect_tone_reversal("Great, but the outcome was terrible.")
    assert reversal["has_tone_reversal"] is True
    assert reversal["state"] in {"certain", "uncertain", "unknown"}
    assert reversal["tone"] == "dark_irony"
    assert reversal["from"] is not None
    assert reversal["to"] is not None
    assert reversal["confidence"] > 0
    assert reversal["from"]["label"] in {"positive", "negative"}
    assert reversal["to"]["label"] in {"positive", "negative"}
    assert reversal["from"]["label"] != reversal["to"]["label"]
    assert reversal["evidence"]["has_connector"] is True


def test_detect_tone_reversal_stays_false_for_flat_positive_tone() -> None:
    reversal = detect_tone_reversal("The day was warm and cheerful, and everyone felt good.")
    assert reversal["has_tone_reversal"] is False
    assert reversal["from"] is None
    assert reversal["to"] is None
    assert reversal["state"] in {"certain", "uncertain", "unknown"}
    assert reversal["evidence"]["transition_count"] == 0


def test_detect_shift_markers_runs_registered_shift_detectors() -> None:
    text = "She thought he might be late, but then she heard the gate creak and said, \"Finally.\""
    shift_markers = detect_shift_markers(text)

    assert set(shift_markers.keys()) == {
        "emotion_shift",
        "narration_internal_thought_shift",
        "internal_external_speech_shift",
        "tone_reversal",
    }
    assert shift_markers["emotion_shift"] == detect_emotion_shift(text)
    assert shift_markers["narration_internal_thought_shift"] == detect_narration_internal_thought_shift(text)
    assert shift_markers["internal_external_speech_shift"] == detect_internal_external_speech_shift(text)
    assert shift_markers["tone_reversal"] == detect_tone_reversal(text)


def test_tag_segment_includes_tone_reversal_field() -> None:
    tags = tag_segment("Great, but the outcome was terrible.")
    assert isinstance(tags["tone_reversal"], dict)
    assert set(tags["tone_reversal"].keys()) >= {"has_tone_reversal", "tone", "from", "to", "confidence", "state", "evidence"}


def test_tag_segment_includes_sub_segment_boundaries_for_detected_shifts() -> None:
    tags = tag_segment('She thought he would answer. "No," he said.')
    boundaries = tags["sub_segment_boundaries"]
    assert isinstance(boundaries, list)
    assert any(item.get("shift_type") == "internal_external_speech_shift" for item in boundaries)
    assert all(isinstance(item, dict) for item in boundaries)
    for item in boundaries:
        assert set(item.keys()) >= {
            "shift_type",
            "boundary_start_char",
            "boundary_end_char",
            "from_label",
            "to_label",
            "from_text",
            "to_text",
            "confidence",
        }


def test_tag_segment_has_empty_sub_segment_boundaries_when_no_shift_detected() -> None:
    tags = tag_segment("The sky was calm and peaceful.")
    assert isinstance(tags["sub_segment_boundaries"], list)
    assert tags["sub_segment_boundaries"] == []


def test_tag_segment_includes_parent_segment_summary_tag() -> None:
    tags = tag_segment("Great, but the outcome was terrible.")
    summary = tags["summary_tag"]
    assert isinstance(summary, dict)
    assert set(summary.keys()) >= {
        "tag_type",
        "dominant_tone",
        "dominant_state",
        "dominant_agent",
        "confidence",
        "state",
        "evidence",
    }
    assert summary["tag_type"] == "segment_summary"
    assert summary["dominant_state"] == tags["type"]
    assert summary["dominant_tone"] == "dark_irony"
    assert isinstance(summary["dominant_agent"], str)
    assert isinstance(summary["confidence"], float)
    assert summary["state"] in {"certain", "uncertain", "unknown"}


def test_tag_segment_summary_prefers_tone_reversal_dominant_tone() -> None:
    tags = tag_segment("Great, but the outcome was terrible.")
    assert tags["summary_tag"]["dominant_tone"] == "dark_irony"


def test_detect_narration_blocks_identifies_outside_dialogue_ranges() -> None:
    text = '"She spoke," said Alex.\nThen silence returned.\n- Another reply.'
    blocks = detect_narration_blocks(text)
    assert blocks == [
        {"type": "narration", "text": "Then silence returned."},
    ]
