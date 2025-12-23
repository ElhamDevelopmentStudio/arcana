from app.services.tagging import detect_dialogue_blocks, detect_structure, tag_segment


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


def test_tag_segment_includes_dialogue_blocks_for_traceability() -> None:
    tags = tag_segment('"Wait," she asked.')
    assert tags["type"] == "dialogue"
    assert tags["dialogue_blocks"] == [{"type": "dialogue", "text": '"Wait," she asked.'}]
