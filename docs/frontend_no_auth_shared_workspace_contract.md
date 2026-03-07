# Frontend No-Auth Shared Workspace Contract

This document defines the current frontend runtime contract when authentication is not enabled.

## Scope

- Applies to the current frontend routes and API usage in this repository.
- Defines expected behavior for local/dev/shared deployments where all users operate in one workspace context.
- Prevents accidental introduction of user-session branching before auth tasks are approved.

## Contract Rules

1. Identity/session model
- There is no authenticated user session in active frontend flows.
- Frontend must not branch UI or data behavior by user identity.
- `/auth` is a placeholder-only route and does not gate workflow access.

2. Workspace context model
- Frontend uses a single persisted workspace state in Zustand (`frontend/src/app/state/workspace-store.ts`).
- Persisted key is `nipe-workspace`.
- Shared state fields are:
  - `projectId`
  - `projectTitle`
  - `selectedMode`
  - `chapterCount`
  - `runId`
- Project-level routes resolve context as:
  - route `:project_id` first
  - fallback to workspace store project id if route param is absent

3. API request model
- API base URL is environment-driven (`import.meta.env`) and never user-entered.
- Frontend calls backend endpoints directly through `NipeApiClient` and SWR hooks.
- Frontend does not collect or attach auth credentials/tokens.
- Frontend does not expose UI for project access-control headers (`X-Principal-Type`, `X-Principal-Id`) in no-auth mode.

4. Entry and navigation flow
- Primary entry route is landing (`/`).
- Primary CTA path is `/` -> `/dashboard`.
- Draft project creation CTA uses `POST /api/projects/drafts` and routes to `/projects/new`.
- Workflow route sequence remains:
  - `/projects/new`
  - `/projects/:project_id/mode`
  - `/projects/:project_id/characters`
  - `/projects/:project_id/pipeline-setup`

5. Multi-user behavior assumption
- Current frontend behavior is shared-workspace, not user-isolated workspace.
- Data shown in dashboard/project lists is assumed to be global for the environment.
- Any user-role or tenant isolation UX is out of scope until auth + scoped access tasks are implemented.

## Guardrails for Future Changes

- Any new frontend feature must remain no-auth by default unless an explicit auth task is approved.
- Do not introduce `currentUser`-based filtering, ownership chips, or session redirects in workflow routes.
- If backend enforces access headers in a deployment, that integration must be introduced as a separate scoped task with matching frontend UX and tests.
