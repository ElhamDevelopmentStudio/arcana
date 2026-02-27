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
9. Frontend quality baseline is mandatory: a polished, aesthetically intentional UI is required, not bare utility screens.
10. Use reusable components and avoid feature-level duplicated UI primitives.
11. Maintain a clear frontend folder structure with feature/module boundaries and code splitting for major screens/sections.
12. A global design system stylesheet is mandatory at `frontend/src/styles/globals.css` using shared tokens (color, typography, spacing, radius, shadow, motion).
13. The following frontend libraries are mandatory for implementation: `axios`, `swr`, `date-fns`, `zustand`, `zod`.
14. Tailwind CSS is the primary frontend styling system; keep bespoke CSS minimal and design-token driven from `globals.css`.
15. Frontend interfaces must avoid unnecessary visual clutter: use the minimum number of cards, borders, and decorative blocks needed for clarity.
16. Every page should contain only information and actions that directly improve the current step UX; remove vanity/status content that does not help completion.

## Frontend Design Authority — CODEX_REDESIGN_PROMPT.md (Mandatory)

`CODEX_REDESIGN_PROMPT.md` is the **sole authority** for all frontend visual design, layout, and UX decisions in this project.

1. Any task that touches frontend UI — including colors, typography, spacing, layout, components, pages, navigation, animations, icons, copy, or design tokens — **must** be implemented in full compliance with `CODEX_REDESIGN_PROMPT.md`.
2. Read `CODEX_REDESIGN_PROMPT.md` in full before starting any frontend design work, even if you believe you already know the design.
3. If the current codebase contradicts `CODEX_REDESIGN_PROMPT.md`, the prompt wins — update the code, not the prompt.
4. Do not treat `CODEX_REDESIGN_PROMPT.md` as a style guide or suggestion. It is a binding design specification. Deviations are defects.
5. Do not carry forward any pattern, color, class name, font, or layout structure from the pre-redesign codebase unless it is explicitly approved or described in `CODEX_REDESIGN_PROMPT.md`.
6. When generating images for the frontend (landing page, feature sections, etc.), use the `imagegen` skill at `/Users/elhamdev/.cursor/skills/imagegen/SKILL.md` and the prompts defined in `CODEX_REDESIGN_PROMPT.md` Section 2.3.
7. The redesign checklist tasks (`RD-*`) in `SRS_Expanded_Implementation_Checklist.md` Section 14 are the granular delivery units for the full redesign. Follow them in order.

## Frontend Architecture Rules (Mandatory)

1. The frontend must be multi-page and route-driven. Do not collapse core workflows into a single control page.
2. Each page must have one primary responsibility and one primary user goal.
3. A page should show only the information and actions needed for that step; avoid unrelated controls.
4. Use modular feature boundaries: each route gets its own page module, local view components, and tests.
5. Shared UI primitives belong in reusable component folders; business logic stays in feature/domain modules.
6. API base URL must come from environment config (`.env` / `import.meta.env`) and never from user-entered form fields.
7. Route sequence must follow the product workflow, including at minimum:
- `/projects/new` for project creation.
- `/projects/:project_id/mode` for mode selection.
- `/projects/:project_id/characters` for character map operations.
- `/projects/:project_id/pipeline-setup` for pipeline configuration.
8. If backend support for a sub-feature is not implemented yet, keep the page structure and show a clear placeholder/disabled state instead of mixing it into another page.
9. Navigation between workflow pages must be explicit, predictable, and persistent (step nav or equivalent).
10. Every new route must include corresponding unit/integration/e2e coverage as applicable.

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
