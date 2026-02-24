from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class GlossaryTermKey(StrEnum):
    NOVEL = "Novel"
    CORPUS = "Corpus"
    CHAPTER_UNIT = "Chapter Unit"
    SEGMENT = "Segment"
    SUB_SEGMENT = "Sub-segment"
    CHARACTER_MAP = "Character Map"
    VERBALIZED_FORM = "Verbalized Form"
    VOICE_MAP = "Voice Map"
    TAGGING = "Tagging"
    CONFIDENCE = "Confidence"
    EVIDENCE_TRACE = "Evidence Trace"
    MODE = "Mode"


@dataclass(frozen=True)
class GlossaryTerm:
    key: GlossaryTermKey
    definition: str


GLOSSARY_TERMS: tuple[GlossaryTerm, ...] = (
    GlossaryTerm(
        key=GlossaryTermKey.NOVEL,
        definition="A long-form narrative text (web novel, book, serialized fiction).",
    ),
    GlossaryTerm(
        key=GlossaryTermKey.CORPUS,
        definition="Full text of a novel (all chapters).",
    ),
    GlossaryTerm(
        key=GlossaryTermKey.CHAPTER_UNIT,
        definition="A single chapter (index + title + content).",
    ),
    GlossaryTerm(
        key=GlossaryTermKey.SEGMENT,
        definition="A short, digestible chunk of text intended for analysis and TTS feeding (target: ≤ 255 characters for audiobook mode).",
    ),
    GlossaryTerm(
        key=GlossaryTermKey.SUB_SEGMENT,
        definition="A smaller unit inside a segment representing a detected shift (emotion shift, narration/dialogue shift, thought shift).",
    ),
    GlossaryTerm(
        key=GlossaryTermKey.CHARACTER_MAP,
        definition="User-editable table mapping `name -> verbalized form -> gender`, plus aliases and metadata.",
    ),
    GlossaryTerm(
        key=GlossaryTermKey.VERBALIZED_FORM,
        definition="Pronunciation-oriented representation for TTS (e.g., “Aegis” → “EE-jis”).",
    ),
    GlossaryTerm(
        key=GlossaryTermKey.VOICE_MAP,
        definition="Mapping from character (or gender/default) to TTS voice profile identifiers.",
    ),
    GlossaryTerm(
        key=GlossaryTermKey.TAGGING,
        definition="Assigning labels and scores to segments/sub-segments (emotion, speaker, type, tension contribution).",
    ),
    GlossaryTerm(
        key=GlossaryTermKey.CONFIDENCE,
        definition="A numeric score representing reliability of a label (0.0–1.0).",
    ),
    GlossaryTerm(
        key=GlossaryTermKey.EVIDENCE_TRACE,
        definition="Stored pointers to text spans and feature signals that justified a label.",
    ),
    GlossaryTerm(
        key=GlossaryTermKey.MODE,
        definition="One of the product workflows (Audiobook / Academic / Author / Other).",
    ),
)


GLOSSARY_BY_NAME: dict[str, str] = {entry.key.value: entry.definition for entry in GLOSSARY_TERMS}


def glossary_term_pairs() -> list[tuple[str, str]]:
    return [(entry.key.value, entry.definition) for entry in GLOSSARY_TERMS]
