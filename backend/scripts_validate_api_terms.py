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


def main() -> int:
    terms_path = ROOT / "docs" / "api_domain_terms.md"
    parsed = load_and_parse_api_terms(terms_path)

    if parsed["Novel"]["definition"] != GLOSSARY_BY_NAME["Novel"]:
        print("API terms validation failed: Novel definition differs from glossary.")
        return 1
    if parsed["Corpus"]["definition"] != GLOSSARY_BY_NAME["Corpus"]:
        print("API terms validation failed: Corpus definition differs from glossary.")
        return 1
    if not _validate_novel_example(parsed["Novel"]["example"]):
        print("API terms validation failed: Novel JSON example is missing required fields.")
        return 1
    if not _validate_corpus_example(parsed["Corpus"]["example"]):
        print("API terms validation failed: Corpus JSON example is missing required fields.")
        return 1

    print("API terms validation succeeded for Novel/Corpus definitions and examples.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
