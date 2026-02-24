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

## Sub-segment

Definition: A smaller unit inside a segment representing a detected shift (emotion shift, narration/dialogue shift, thought shift).

Example (storage representation with parent pointers):

```json
{
  "sub_segment": {
    "sub_segment_id": "12-004-01",
    "sub_segment_index": 1,
    "parent_project_id": 1,
    "parent_run_id": 7,
    "parent_chapter_id": 12,
    "parent_segment_id": "12-004",
    "parent_pointers": {
      "project": "projects.id=1",
      "chapter": "chapters.id=12",
      "segment": "segments.segment_id=12-004"
    },
    "span_start_char": 0,
    "span_end_char": 24,
    "text": "\"Ah! So bitter!\"",
    "shift_type": "emotion_shift",
    "tags": {
      "type": "dialogue",
      "speaker": "unknown",
      "emotion_primary": "frustration"
    },
    "confidence": {
      "speaker": 0.2,
      "emotion": 0.6
    }
  }
}
```

## Character Map

Definition: User-editable table mapping `name -> verbalized form -> gender`, plus aliases and metadata.

Example (minimum + expanded schema):

```json
{
  "character_map": {
    "minimum": {
      "name": "Sunny",
      "verbalized_form": "SUN-nee",
      "gender": "male"
    },
    "expanded": {
      "name": "Nephis",
      "verbalized_form": "NEH-fiss",
      "gender": "female",
      "aliases": ["Changing Star", "Lady Nephis"],
      "notes": "Main cast character",
      "source": "user_import_csv",
      "confidence": 0.98,
      "voice_id": "voice_female_main_01"
    }
  }
}
```

## Voice Map

Definition: Mapping from character (or gender/default) to TTS voice profile identifiers.

Example (schema + fallback behavior):

```json
{
  "voice_map": {
    "narrator_voice": "voice_narrator_default",
    "defaults": {
      "male": "voice_male_default",
      "female": "voice_female_default",
      "neutral": "voice_neutral_default",
      "unknown": "voice_unknown_default"
    },
    "character_overrides": {
      "Sunny": "voice_male_main_01",
      "Nephis": "voice_female_main_01"
    },
    "fallback_behavior": {
      "resolution_order": [
        "character_override",
        "narrator_if_narration",
        "gender_default",
        "unknown_default"
      ],
      "notes": "If speaker is unresolved or gender is unavailable, use unknown default."
    }
  }
}
```

## Confidence

Definition: A numeric score representing reliability of a label (0.0–1.0).

Example (semantics + range checks):

```json
{
  "confidence": {
    "semantic": "Reliability score for inferred or assigned labels.",
    "range": {
      "min": 0.0,
      "max": 1.0,
      "inclusive": true
    },
    "unknown_policy": {
      "label": "unknown/uncertain",
      "default_value": 0.0
    },
    "examples": {
      "speaker": 0.2,
      "emotion": 0.6
    }
  }
}
```

## Evidence Trace

Definition: Stored pointers to text spans and feature signals that justified a label.

Example (semantics + range checks):

```json
{
  "evidence_trace": {
    "trace_id": "12-004-speaker",
    "target": "speaker",
    "target_ref": {
      "project_id": 1,
      "chapter_id": 12,
      "segment_id": "12-004",
      "sub_segment_id": "12-004-01"
    },
    "signals": [
      {
        "type": "alias_match",
        "value": "Sunny",
        "weight": 0.55
      },
      {
        "type": "attribution_verb",
        "value": "said",
        "weight": 0.35
      }
    ],
    "span_pointers": [
      {
        "source": "normalized_text",
        "start_char": 102,
        "end_char": 117
      }
    ],
    "confidence": 0.9
  }
}
```

## Mode

Definition: One of the product workflows (Audiobook / Academic / Author / Other).

Example (enum + persistence):

```json
{
  "mode": {
    "enum": ["audiobook", "academic", "author", "custom"],
    "default": "audiobook",
    "persisted_in": [
      "runs.config_json.mode"
    ],
    "notes": "Current PoC stores selected mode at run level; project-level mode persistence is deferred."
  }
}
```
