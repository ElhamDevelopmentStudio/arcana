from app.services.tagging import (
    detect_dialogue_blocks,
    detect_emotion_shift,
    detect_narration_internal_thought_shift,
    detect_narration_blocks,
    detect_structure,
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


def test_tag_segment_includes_dialogue_blocks_for_traceability() -> None:
    tags = tag_segment('"Wait," she asked.')
    assert tags["type"] == "dialogue"
    assert tags["dialogue_blocks"] == [{"type": "dialogue", "text": '"Wait," she asked.'}]
    assert tags["narration_blocks"] == []


def test_tag_segment_includes_tension_contribution_tag() -> None:
    tags = tag_segment("He bolted to the door as she shouted, \"Help!\" then the alarm rang.")
    tension = tags["tension_contribution"]
    assert isinstance(tension, dict)
    assert set(tension.keys()) == {"value", "level"}
    assert isinstance(tension["value"], float)
    assert 0.0 <= tension["value"] <= 1.0
    assert tension["level"] in {"high", "moderate", "low", "calm"}
    assert tension["value"] > 0.0


def test_tag_segment_tension_contribution_remains_low_for_stable_description() -> None:
    tags = tag_segment("The moonlight painted the room in silver lines.")
    tension = tags["tension_contribution"]
    assert isinstance(tension, dict)
    assert tension["level"] in {"calm", "low"}
    assert tension["value"] < 0.35


def test_tag_segment_includes_dominance_contribution_tag() -> None:
    tags = tag_segment('"Wait," Alice said.')
    dominance = tags["dominance_contribution"]
    assert isinstance(dominance, dict)
    assert set(dominance.keys()) == {"value", "level", "dominant_agent", "evidence"}
    assert isinstance(dominance["value"], float)
    assert 0.0 <= dominance["value"] <= 1.0
    assert dominance["level"] in {"dominant", "strong", "moderate", "low"}
    assert dominance["dominant_agent"] == "alice"
    assert isinstance(dominance["evidence"], dict)
    assert "speaker_resolved" in dominance["evidence"]
    assert "pronoun_reference_count" in dominance["evidence"]
    assert "proper_noun_hits" in dominance["evidence"]


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


def test_detect_emotion_shift_identifies_positive_to_negative_transition() -> None:
    shift = detect_emotion_shift("He was happy, but fear and despair arrived.")
    assert shift["has_shift"] is True
    assert isinstance(shift["confidence"], float)
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
    assert shift["evidence"]["shift_count"] == 0


def test_tag_segment_includes_emotion_shift_field() -> None:
    tags = tag_segment("He smiled as dawn broke, but then the grave threat arrived.")
    assert isinstance(tags["emotion_shift"], dict)
    assert set(tags["emotion_shift"].keys()) >= {"has_shift", "from", "to", "confidence", "evidence"}


def test_detect_narration_internal_thought_shift_identifies_transition() -> None:
    shift = detect_narration_internal_thought_shift("She thought the sun would rise, but the room stayed cold and silent.")
    assert shift["has_shift"] is True
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
    assert shift["evidence"]["shift_count"] == 0


def test_tag_segment_includes_narration_internal_thought_shift_field() -> None:
    tags = tag_segment("She thought he would return, but the wind grew loud.")
    assert isinstance(tags["narration_internal_thought_shift"], dict)
    assert set(tags["narration_internal_thought_shift"].keys()) >= {"has_shift", "from", "to", "confidence", "evidence"}


def test_detect_narration_blocks_identifies_outside_dialogue_ranges() -> None:
    text = '"She spoke," said Alex.\nThen silence returned.\n- Another reply.'
    blocks = detect_narration_blocks(text)
    assert blocks == [
        {"type": "narration", "text": "Then silence returned."},
    ]
