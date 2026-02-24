# NIPE Implementation Scope Baseline

Reference source:
- [SRS.md](/Users/elhamdev/work/nipe/SRS.md) section `### 1.2 Scope`

This file intentionally copies SRS `NIPE SHALL` and `NIPE SHALL NOT` statements into an implementation-scoped document so engineering work can validate scope consistently.

## NIPE SHALL

- ingest large novels (3,500+ chapters)
- normalize text and structure
- extract characters and build a character map
- support user review and overrides
- produce segmented text suitable for TTS (audiobook mode)
- generate multi-layer tags (speaker, type, emotion, tension, dominance contribution)
- output structured exports (JSON/CSV/time series)
- provide dashboards/visualizations (where enabled)

## NIPE SHALL NOT

- rewrite or generate new story text
- produce final audio output directly (optional integration later, but not required in v1)
- claim emotional labels are ground-truth
- require manual per-chapter labeling
