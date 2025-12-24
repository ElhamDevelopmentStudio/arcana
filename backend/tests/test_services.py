from app.services.ingestion import detect_chapters
from app.services.phonetics import replace_pronunciations, replace_pronunciations_with_counts
from app.services.segmentation import (
    segment_text,
    segment_text_with_parent_paragraph,
    split_paragraphs,
    split_paragraphs_into_sentences,
    split_sentences,
)
from app.services.segment_reconstruction import reconstruct_chapter_text_from_segments


def test_detect_chapters_fallback_when_no_header() -> None:
    content = "This is a novel without explicit chapter heading."
    chapters = detect_chapters(content)
    assert len(chapters) == 1
    assert chapters[0][0] == "Chapter 1"


def test_replace_pronunciation_whole_word_only() -> None:
    text = "Sunny met Nephis. Sunlight stayed bright."
    replaced = replace_pronunciations(text, {"Sunny": "Sunny", "Nephis": "Ne-fis"})
    assert "Ne-fis" in replaced
    assert "Sunlight" in replaced


def test_replace_pronunciation_can_match_substrings_when_disabled() -> None:
    text = "CaptainAegis glimmered near the aegis."
    replaced = replace_pronunciations(text, {"Aegis": "EE-jis"}, match_whole_words=False)
    assert replaced == "CaptainEE-jis glimmered near the aegis."


def test_replace_pronunciation_avoids_false_positive_substring_matches() -> None:
    text = "The CaptainAegis and Aegis were present."
    replaced = replace_pronunciations(text, {"Aegis": "EE-jis"})
    assert replaced == "The CaptainAegis and EE-jis were present."


def test_replace_pronunciation_can_ignore_case_when_disabled() -> None:
    text = "Aegis sailed with aegis and AEGIS in the hold."
    replaced = replace_pronunciations(text, {"Aegis": "EE-jis"}, match_whole_words=True, case_sensitive=False)
    assert replaced == "EE-jis sailed with EE-jis and EE-jis in the hold."


def test_replace_pronunciation_reports_replacement_counts() -> None:
    text = "Sunny, Sunny met Nephis. Nephis smiled after Sunny said hello."
    replaced, counts = replace_pronunciations_with_counts(
        text,
        {
            "Sunny": "Sŏo-nee",
            "Nephis": "Ne-fis",
        },
    )
    assert replaced == "Sŏo-nee, Sŏo-nee met Ne-fis. Ne-fis smiled after Sŏo-nee said hello."
    assert counts["Sunny"] == 3
    assert counts["Nephis"] == 2


def test_segmentation_never_exceeds_limit() -> None:
    text = (
        "One sentence that is rather long and should probably be chunked carefully. "
        "Another sentence follows immediately and keeps extending the line to force chunking."
    )
    segments = segment_text(text, max_chars=60)
    assert segments
    assert all(len(segment) <= 60 for segment in segments)


def test_split_paragraphs_collapses_multiple_breaks_and_removes_empty_blocks() -> None:
    text = "First paragraph.\n\n\n\nSecond paragraph.\n\n\nThird."
    assert split_paragraphs(text) == ["First paragraph.", "Second paragraph.", "Third."]


def test_segment_text_resets_across_paragraph_boundaries() -> None:
    text = '"Hi there." She waved.\n\nNow a different paragraph starts with a new thought.'
    segments = segment_text(text, max_chars=100)
    assert segments == ['"Hi there." She waved.', "Now a different paragraph starts with a new thought."]


def test_split_paragraphs_into_sentences_preserves_paragraph_grouping() -> None:
    text = "First paragraph. Ends here.\n\nSecond paragraph asks a question?\nWith follow-up."
    assert split_paragraphs_into_sentences(text) == [
        ["First paragraph.", "Ends here."],
        ["Second paragraph asks a question?", "With follow-up."],
    ]


def test_segment_text_with_parent_paragraph_exposes_sentence_reference() -> None:
    text = "First sentence. Second sentence. Third sentence.\n\nFourth sentence."
    segments = segment_text_with_parent_paragraph(text, max_chars=120)

    assert len(segments) == 2
    assert segments[0]["paragraph_index"] == 1
    assert segments[0]["sentence_start_index"] == 1
    assert segments[0]["sentence_end_index"] == 3
    assert segments[1]["paragraph_index"] == 2
    assert segments[1]["sentence_start_index"] == 1
    assert segments[1]["sentence_end_index"] == 1


def test_reconstruct_chapter_text_from_segments_is_order_invariant() -> None:
    chapter_text = (
        "The tower opened at dawn. Birds called from the rooftops.\n\n"
        "A messenger arrived in silver boots, breathless and late."
    )
    pieces = segment_text_with_parent_paragraph(chapter_text, max_chars=40)
    segment_payloads = []
    cursor = 0

    for index, piece in enumerate(pieces, start=1):
        segment_text_value = str(piece["text"])
        start = chapter_text.find(segment_text_value, cursor)
        if start < 0:
            continue
        end = start + len(segment_text_value)
        cursor = end
        segment_payloads.append(
            {
                "segment_index": index,
                "normalized_text": segment_text_value,
                "original_text": segment_text_value,
                "original_span_pointer": {
                    "normalized_start_char": start,
                    "normalized_end_char": end,
                },
            }
        )

    reconstructed_text = reconstruct_chapter_text_from_segments(chapter_text, list(reversed(segment_payloads)))
    assert reconstructed_text == chapter_text


def test_reconstruct_chapter_text_from_segments_falls_back_to_normalized_text_order() -> None:
    segment_payloads = [
        {
            "segment_index": 2,
            "normalized_text": "second",
            "original_text": "second",
            "original_span_pointer": {"normalized_start_char": -1, "normalized_end_char": -1},
        },
        {
            "segment_index": 1,
            "normalized_text": "first",
            "original_text": "first",
            "original_span_pointer": {"normalized_start_char": -1, "normalized_end_char": -1},
        },
    ]

    reconstructed_text = reconstruct_chapter_text_from_segments("first second", segment_payloads)
    assert reconstructed_text == "firstsecond"


def test_segment_text_is_built_from_paragraph_sentence_layer() -> None:
    text = "A short line. Another line.\n\nNext paragraph starts cleanly."
    segments = segment_text(text, max_chars=120)
    assert segments == ["A short line. Another line.", "Next paragraph starts cleanly."]


def test_segment_text_hard_caps_overlarge_max_chars() -> None:
    text = "One very long sentence " * 40
    segments = segment_text(text, max_chars=999)
    assert segments
    assert all(len(segment) <= 255 for segment in segments)
    assert len(segments) > 1


def test_segment_text_avoids_clause_connector_starts() -> None:
    long_alpha_prefix = " ".join(["alpha"] * 20)
    text = f"{long_alpha_prefix} because the investigation revealed a hidden trail after midnight."
    segments = segment_text(text, max_chars=60)

    assert segments
    assert all(len(segment) <= 60 for segment in segments)
    for segment in segments[1:]:
        assert not segment.strip().lower().startswith(
            ("and ", "but ", "or ", "so ", "then ", "because ", "if ", "when ", "while ", "as ", "although ")
        )


def test_segment_text_prefers_punctuation_boundaries() -> None:
    text = (
        "alpha one, alpha two, alpha three, alpha four, alpha five, alpha six, alpha seven, "
        "alpha eight, alpha nine, alpha ten, alpha eleven, alpha twelve."
    )
    segments = segment_text(text, max_chars=100)
    assert len(segments) > 1
    assert segments[0].endswith(",") or segments[0].endswith(".")


def test_segment_text_prefers_quote_boundaries_when_possible() -> None:
    quote_payload = (
        "inside the quote, with repeated clauses, including commas, and details, "
        * 6
    )
    text = (
        'He said, "'
        + quote_payload
        + 'it keeps going" afterward, the group reacted with relief and kept discussing the plan '
        + "for a long while until dawn."
    )
    opening_quote_index = text.index('"')
    segments = segment_text(text, max_chars=120)
    assert len(segments) > 1
    assert '"' not in segments[0]
    assert len(segments[0]) < opening_quote_index
    assert segments[1].lstrip().startswith('"')


def test_split_sentences_keeps_abbreviations_and_initials() -> None:
    text = (
        "Dr. A. B. arrived at dawn and then said the team should wait, "
        "while Colonel A. reviewed his notes. They then departed."
    )
    sentences = split_sentences(text)
    assert sentences == [
        "Dr. A. B. arrived at dawn and then said the team should wait, while Colonel A. reviewed his notes.",
        "They then departed.",
    ]


def test_segment_text_avoids_splitting_on_abbreviation_periods() -> None:
    text = (
        "The witness cited Dr. A. B. Carlton, who arrived before dawn, and then discussed "
        "the mission details at length."
    )
    segments = segment_text(text, max_chars=28)
    assert segments[0] == "The witness cited"
    assert segments[1].startswith("Dr.")
