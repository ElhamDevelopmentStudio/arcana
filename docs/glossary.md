# NIPE Glossary

Reference source: [SRS.md](/Users/elhamdev/work/nipe/SRS.md) section `## 0. Glossary`.

## 0. Glossary

- **Novel**: A long-form narrative text (web novel, book, serialized fiction).
- **Corpus**: Full text of a novel (all chapters).
- **Chapter Unit**: A single chapter (index + title + content).
- **Segment**: A short, digestible chunk of text intended for analysis and TTS feeding (target: ≤ 255 characters for audiobook mode).
- **Sub-segment**: A smaller unit inside a segment representing a detected shift (emotion shift, narration/dialogue shift, thought shift).
- **Character Map**: User-editable table mapping `name -> verbalized form -> gender`, plus aliases and metadata.
- **Verbalized Form**: Pronunciation-oriented representation for TTS (e.g., “Aegis” → “EE-jis”).
- **Voice Map**: Mapping from character (or gender/default) to TTS voice profile identifiers.
- **Tagging**: Assigning labels and scores to segments/sub-segments (emotion, speaker, type, tension contribution).
- **Confidence**: A numeric score representing reliability of a label (0.0–1.0).
- **Evidence Trace**: Stored pointers to text spans and feature signals that justified a label.
- **Mode**: One of the product workflows (Audiobook / Academic / Author / Other).
