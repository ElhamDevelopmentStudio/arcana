from app.services.tagging import detect_dialogue_blocks, detect_narration_blocks, detect_structure, tag_segment


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


def test_detect_narration_blocks_identifies_outside_dialogue_ranges() -> None:
    text = '"She spoke," said Alex.\nThen silence returned.\n- Another reply.'
    blocks = detect_narration_blocks(text)
    assert blocks == [
        {"type": "narration", "text": "Then silence returned."},
    ]
