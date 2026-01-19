# ADR-103: LLM Router Uses Ordered Provider Failover with Deterministic Replay Controls

Reference sources:
- [SRS.md](/Users/elhamdev/work/nipe/SRS.md) section `### 4.12 LLM Routing & Quota Management System (NEW)`
- [SRS.md](/Users/elhamdev/work/nipe/SRS.md) section `### NFR-7 LLM Reliability`

## Status

accepted

## Context

- LLM providers can rate-limit, fail, or return variable outputs over time.
- NIPE needs controlled failover for reliability while preserving reproducibility requirements.
- Run-level deterministic settings must be captured and auditable.

## Decision

- Route LLM calls through a centralized router with provider priority ordering.
- Support multi-key rotation per provider and failover across providers on quota/rate-limit failures.
- Persist deterministic replay controls (mode flag, seed, model identifier, randomization config) in run config.
- Record provider/key usage audits and deterministic replay warnings when fallback behavior may affect equivalence.

## Consequences

- Pipeline reliability improves under transient provider outages.
- Deterministic replay intent is explicit and testable per run.
- Operational debugging has auditable provider attempt history.

## Backend Impact

- `backend/app/config.py` provider/key + priority parsing
- `backend/app/services/llm.py` routing, usage tracking, failover behavior
- `backend/app/main.py` run config ingestion and persistence

## Frontend Impact

- Pipeline setup can expose deterministic and provider controls as explicit run inputs
- Run details can surface deterministic replay warnings and selected provider metadata
- Contract/e2e tests can verify config roundtrip for deterministic and provider-related fields

