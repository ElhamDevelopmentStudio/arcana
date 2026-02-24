from app.services.ingestion import detect_chapters
from app.services.phonetics import replace_pronunciations
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


def test_segmentation_never_exceeds_limit() -> None:
    text = (
        "One sentence that is rather long and should probably be chunked carefully. "
        "Another sentence follows immediately and keeps extending the line to force chunking."
    )
    segments = segment_text(text, max_chars=60)
    assert segments
    assert all(len(segment) <= 60 for segment in segments)
