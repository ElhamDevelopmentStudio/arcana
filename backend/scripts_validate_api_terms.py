from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.api_terms_validation import load_and_parse_api_terms  # noqa: E402
from app.glossary_terms import GLOSSARY_BY_NAME  # noqa: E402


def _validate_novel_example(example: dict) -> bool:
    novel = example.get("novel")
    if not isinstance(novel, dict):
        return False
    required = ("project_id", "title", "source_format", "language")
    return all(key in novel for key in required)


def _validate_corpus_example(example: dict) -> bool:
    corpus = example.get("corpus")
    if not isinstance(corpus, dict):
        return False
    if not all(key in corpus for key in ("project_id", "chapter_count", "chapters")):
        return False
    chapters = corpus.get("chapters")
    if not isinstance(chapters, list) or not chapters:
        return False
    first = chapters[0]
    if not isinstance(first, dict):
        return False
    required = ("chapter_index", "chapter_title", "char_count")
    return all(key in first for key in required)


def _validate_chapter_unit_example(example: dict) -> bool:
    chapter_unit = example.get("chapter_unit")
    if not isinstance(chapter_unit, dict):
        return False
    required = (
        "project_id",
        "chapter_id",
        "chapter_index",
        "chapter_title",
        "raw_text",
        "normalized_text",
    )
    return all(key in chapter_unit for key in required)


def _validate_segment_example(example: dict) -> bool:
    segment = example.get("segment")
    if not isinstance(segment, dict):
        return False
    required = (
        "chapter_id",
        "segment_id",
        "original_text",
        "phonetic_text",
        "type",
        "speaker",
        "gender",
        "voice_id",
        "emotion_valence",
        "emotion_intensity",
        "confidence",
    )
    if not all(key in segment for key in required):
        return False
    confidence = segment.get("confidence")
    if not isinstance(confidence, dict):
        return False
    return all(key in confidence for key in ("speaker", "emotion"))


def _validate_sub_segment_example(example: dict) -> bool:
    sub_segment = example.get("sub_segment")
    if not isinstance(sub_segment, dict):
        return False
    required = (
        "sub_segment_id",
        "sub_segment_index",
        "parent_project_id",
        "parent_run_id",
        "parent_chapter_id",
        "parent_segment_id",
        "parent_pointers",
        "span_start_char",
        "span_end_char",
        "text",
        "shift_type",
        "tags",
        "confidence",
    )
    if not all(key in sub_segment for key in required):
        return False
    parent_pointers = sub_segment.get("parent_pointers")
    if not isinstance(parent_pointers, dict):
        return False
    if not all(key in parent_pointers for key in ("project", "chapter", "segment")):
        return False
    confidence = sub_segment.get("confidence")
    if not isinstance(confidence, dict):
        return False
    return all(key in confidence for key in ("speaker", "emotion"))


def main() -> int:
    terms_path = ROOT / "docs" / "api_domain_terms.md"
    parsed = load_and_parse_api_terms(terms_path)

    if parsed["Novel"]["definition"] != GLOSSARY_BY_NAME["Novel"]:
        print("API terms validation failed: Novel definition differs from glossary.")
        return 1
    if parsed["Corpus"]["definition"] != GLOSSARY_BY_NAME["Corpus"]:
        print("API terms validation failed: Corpus definition differs from glossary.")
        return 1
    if parsed["Chapter Unit"]["definition"] != GLOSSARY_BY_NAME["Chapter Unit"]:
        print("API terms validation failed: Chapter Unit definition differs from glossary.")
        return 1
    if parsed["Segment"]["definition"] != GLOSSARY_BY_NAME["Segment"]:
        print("API terms validation failed: Segment definition differs from glossary.")
        return 1
    if parsed["Sub-segment"]["definition"] != GLOSSARY_BY_NAME["Sub-segment"]:
        print("API terms validation failed: Sub-segment definition differs from glossary.")
        return 1
    if not _validate_novel_example(parsed["Novel"]["example"]):
        print("API terms validation failed: Novel JSON example is missing required fields.")
        return 1
    if not _validate_corpus_example(parsed["Corpus"]["example"]):
        print("API terms validation failed: Corpus JSON example is missing required fields.")
        return 1
    if not _validate_chapter_unit_example(parsed["Chapter Unit"]["example"]):
        print("API terms validation failed: Chapter Unit JSON example is missing required fields.")
        return 1
    if not _validate_segment_example(parsed["Segment"]["example"]):
        print("API terms validation failed: Segment JSON example is missing required fields.")
        return 1
    if not _validate_sub_segment_example(parsed["Sub-segment"]["example"]):
        print("API terms validation failed: Sub-segment JSON example is missing required fields.")
        return 1

    print("API terms validation succeeded for Novel/Corpus/Chapter Unit/Segment/Sub-segment definitions and examples.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
