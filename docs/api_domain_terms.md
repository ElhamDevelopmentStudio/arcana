# NIPE API Domain Terms

Reference sources:
- [SRS.md](/Users/elhamdev/work/nipe/SRS.md) section `## 0. Glossary`
- [backend/README.md](/Users/elhamdev/work/nipe/backend/README.md) API summary

## Novel

Definition: A long-form narrative text (web novel, book, serialized fiction).

Example (API-facing metadata):

```json
{
  "novel": {
    "project_id": 1,
    "title": "Shadow Slave",
    "source_format": "txt",
    "language": "en"
  }
}
```

## Corpus

Definition: Full text of a novel (all chapters).

Example (API-facing representation):

```json
{
  "corpus": {
    "project_id": 1,
    "chapter_count": 95,
    "chapters": [
      {
        "chapter_index": 1,
        "chapter_title": "Chapter 1",
        "char_count": 7812
      },
      {
        "chapter_index": 2,
        "chapter_title": "Chapter 2",
        "char_count": 7540
      }
    ]
  }
}
```

## Chapter Unit

Definition: A single chapter (index + title + content).

Example (API-facing representation):

```json
{
  "chapter_unit": {
    "project_id": 1,
    "chapter_id": 12,
    "chapter_index": 12,
    "chapter_title": "Chapter 12",
    "raw_text": "Original chapter text...",
    "normalized_text": "Normalized chapter text..."
  }
}
```

## Segment

Definition: A short, digestible chunk of text intended for analysis and TTS feeding (target: ≤ 255 characters for audiobook mode).

Example (API-facing representation):

```json
{
  "segment": {
    "chapter_id": 12,
    "segment_id": "12-004",
    "original_text": "\"I should have bought a piece of real meat instead.\"",
    "phonetic_text": "\"I should have bought a piece of real meat instead.\"",
    "type": "dialogue",
    "speaker": "unknown",
    "gender": "unknown",
    "voice_id": "narrator_default",
    "emotion_valence": 0.0,
    "emotion_intensity": 0.0,
    "confidence": {
      "speaker": 0.2,
      "emotion": 0.4
    }
  }
}
```
