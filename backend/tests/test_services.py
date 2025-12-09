from app.services.ingestion import detect_chapters
from app.services.phonetics import replace_pronunciations, replace_pronunciations_with_counts
from app.services.segmentation import segment_text


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
