# AGENTS.md

This document defines the repository working agreement for any agent or contributor operating in this project.

## Purpose

Keep implementation accurate, incremental, testable, and easy to resume from a new session.

## Core Delivery Rules

1. Execute one small task at a time.
2. Do not batch unrelated features into a single implementation step.
3. Prefer narrowly scoped tasks with explicit completion boundaries.
4. After each completed task, decide whether `README.md` needs an update and apply it when relevant.
5. Follow vertical slices for user-visible work: backend + frontend + relevant integration evidence in the same task slice.
6. Always start from the earliest unresolved checklist item in `SRS_Expanded_Implementation_Checklist.md`.
7. If earlier checklist tasks are still undone, complete those first before advancing to later tasks, unless explicitly marked blocked with reason and follow-up task ID.
8. For API/data-model changes, implement matching frontend behavior in the same slice or log an explicit deferred FE task ID before moving on.

## Task Granularity Standard

A task is “small enough” when:
- It can be implemented and validated in one focused pass.
- It has a single primary objective.
- It does not require cross-cutting refactors unless those are the objective.
- It can be reviewed independently without needing the next task for correctness.

## Testing Standard Per Task

For each implementation task, add or update tests as needed across applicable layers:
- Unit tests
- Integration tests
- End-to-end tests
- Regression tests
- Any additional tests required by risk (performance, security, migration, etc.)

### Test execution policy

Before moving to the next task:
1. Run all relevant tests for the current change set.
2. Ensure all executed tests pass.
3. If any test fails, fix and re-run before continuing.

## Commit Policy

1. Commit only after the task is complete and validated.
2. Use clean, professional commit messages.
3. Use a standard commit prefix (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`).
4. Do not use novelty signatures or filler text in commit messages.

## Documentation and Continuation Policy

1. Keep progress understandable for a brand-new chat/session.
2. If behavior, setup, or scope changes, update relevant docs in the same task.
3. Maintain alignment with:
- `PoC.md` for current PoC scope
- `SRS.md` for full product requirements
- `SRS_Expanded_Implementation_Checklist.md` for granular roadmap execution

## Scope Control

1. Implement only what the current approved task requires.
2. Defer non-requested expansions to checklist items.
3. Avoid silent scope creep.

## External Reference Folder Policy

Path: `for_reference_only_not_for_copying/`

1. This folder is **never** a source of truth for this project.
2. Authoritative order is:
- `SRS.md`
- `SRS_Expanded_Implementation_Checklist.md`
- `PoC.md` (when working in PoC scope)
- Existing code in this repository
3. The reference folder may be consulted **only** for implementation inspiration on features explicitly listed in:
- `docs/reference_feature_overlap.md`
4. Never copy code verbatim from the reference folder into this repository.
5. If reference behavior conflicts with SRS/checklist, follow SRS/checklist and ignore the reference behavior.
6. Any implementation decision inspired by the reference folder must be validated against current project requirements before merge.
