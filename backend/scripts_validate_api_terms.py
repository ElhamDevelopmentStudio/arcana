from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.api_terms_validation import load_and_parse_api_terms  # noqa: E402
from app.glossary_terms import GLOSSARY_BY_NAME  # noqa: E402


def _is_unit_interval(value: object) -> bool:
    return isinstance(value, (int, float)) and 0.0 <= float(value) <= 1.0


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


def _validate_character_map_example(example: dict) -> bool:
    character_map = example.get("character_map")
    if not isinstance(character_map, dict):
        return False

    minimum = character_map.get("minimum")
    expanded = character_map.get("expanded")
    if not isinstance(minimum, dict) or not isinstance(expanded, dict):
        return False

    minimum_required = ("name", "verbalized_form", "gender")
    if not all(key in minimum for key in minimum_required):
        return False

    expanded_required = (
        "name",
        "verbalized_form",
        "gender",
        "aliases",
        "notes",
        "source",
        "confidence",
    )
    if not all(key in expanded for key in expanded_required):
        return False
    if not isinstance(expanded.get("aliases"), list):
        return False
    confidence = expanded.get("confidence")
    return isinstance(confidence, (int, float))


def _validate_voice_map_example(example: dict) -> bool:
    voice_map = example.get("voice_map")
    if not isinstance(voice_map, dict):
        return False

    narrator_voice = voice_map.get("narrator_voice")
    if not isinstance(narrator_voice, str) or not narrator_voice.strip():
        return False

    defaults = voice_map.get("defaults")
    if not isinstance(defaults, dict):
        return False
    required_defaults = ("male", "female", "neutral", "unknown")
    if not all(key in defaults for key in required_defaults):
        return False
    if not all(isinstance(defaults[key], str) and defaults[key].strip() for key in required_defaults):
        return False

    character_overrides = voice_map.get("character_overrides")
    if not isinstance(character_overrides, dict):
        return False

    fallback_behavior = voice_map.get("fallback_behavior")
    if not isinstance(fallback_behavior, dict):
        return False
    resolution_order = fallback_behavior.get("resolution_order")
    if not isinstance(resolution_order, list):
        return False
    required_steps = [
        "character_override",
        "narrator_if_narration",
        "gender_default",
        "unknown_default",
    ]
    return all(step in resolution_order for step in required_steps)


def _validate_confidence_example(example: dict) -> bool:
    confidence = example.get("confidence")
    if not isinstance(confidence, dict):
        return False
    if not isinstance(confidence.get("semantic"), str):
        return False
    range_obj = confidence.get("range")
    if not isinstance(range_obj, dict):
        return False
    min_value = range_obj.get("min")
    max_value = range_obj.get("max")
    if not (_is_unit_interval(min_value) and _is_unit_interval(max_value)):
        return False
    if float(min_value) > float(max_value):
        return False
    if range_obj.get("inclusive") is not True:
        return False
    unknown_policy = confidence.get("unknown_policy")
    if not isinstance(unknown_policy, dict):
        return False
    if not isinstance(unknown_policy.get("label"), str):
        return False
    if not _is_unit_interval(unknown_policy.get("default_value")):
        return False
    examples = confidence.get("examples")
    if not isinstance(examples, dict):
        return False
    for key in ("speaker", "emotion"):
        if key not in examples or not _is_unit_interval(examples[key]):
            return False
    return True


def _validate_evidence_trace_example(example: dict) -> bool:
    evidence_trace = example.get("evidence_trace")
    if not isinstance(evidence_trace, dict):
        return False
    required = ("trace_id", "target", "target_ref", "signals", "span_pointers", "confidence")
    if not all(key in evidence_trace for key in required):
        return False
    if not isinstance(evidence_trace.get("trace_id"), str):
        return False
    if not isinstance(evidence_trace.get("target"), str):
        return False
    if not _is_unit_interval(evidence_trace.get("confidence")):
        return False

    target_ref = evidence_trace.get("target_ref")
    if not isinstance(target_ref, dict):
        return False
    target_ref_required = ("project_id", "chapter_id", "segment_id", "sub_segment_id")
    if not all(key in target_ref for key in target_ref_required):
        return False

    signals = evidence_trace.get("signals")
    if not isinstance(signals, list) or not signals:
        return False
    for signal in signals:
        if not isinstance(signal, dict):
            return False
        if not all(key in signal for key in ("type", "value", "weight")):
            return False
        if not isinstance(signal["type"], str) or not isinstance(signal["value"], str):
            return False
        if not _is_unit_interval(signal["weight"]):
            return False

    span_pointers = evidence_trace.get("span_pointers")
    if not isinstance(span_pointers, list) or not span_pointers:
        return False
    for pointer in span_pointers:
        if not isinstance(pointer, dict):
            return False
        if not all(key in pointer for key in ("source", "start_char", "end_char")):
            return False
        if not isinstance(pointer["source"], str):
            return False
        if not isinstance(pointer["start_char"], int) or not isinstance(pointer["end_char"], int):
            return False
        if pointer["start_char"] < 0 or pointer["end_char"] < pointer["start_char"]:
            return False

    return True


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
    if parsed["Character Map"]["definition"] != GLOSSARY_BY_NAME["Character Map"]:
        print("API terms validation failed: Character Map definition differs from glossary.")
        return 1
    if parsed["Voice Map"]["definition"] != GLOSSARY_BY_NAME["Voice Map"]:
        print("API terms validation failed: Voice Map definition differs from glossary.")
        return 1
    if parsed["Confidence"]["definition"] != GLOSSARY_BY_NAME["Confidence"]:
        print("API terms validation failed: Confidence definition differs from glossary.")
        return 1
    if parsed["Evidence Trace"]["definition"] != GLOSSARY_BY_NAME["Evidence Trace"]:
        print("API terms validation failed: Evidence Trace definition differs from glossary.")
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
    if not _validate_character_map_example(parsed["Character Map"]["example"]):
        print("API terms validation failed: Character Map JSON example is missing minimum/expanded schema fields.")
        return 1
    if not _validate_voice_map_example(parsed["Voice Map"]["example"]):
        print("API terms validation failed: Voice Map JSON example is missing schema/fallback behavior fields.")
        return 1
    if not _validate_confidence_example(parsed["Confidence"]["example"]):
        print("API terms validation failed: Confidence JSON example is missing semantics/range-check fields.")
        return 1
    if not _validate_evidence_trace_example(parsed["Evidence Trace"]["example"]):
        print("API terms validation failed: Evidence Trace JSON example is missing semantics/range-check fields.")
        return 1

    print(
        "API terms validation succeeded for Novel/Corpus/Chapter Unit/Segment/Sub-segment/Character Map/Voice Map/Confidence/Evidence Trace definitions and examples."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
