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
