# NIPE Frontend

React + Vite client for the NIPE workflow.

## Workflow Routes

- `/projects/new` - project creation + ingestion
- `/projects/:project_id/mode` - mode selection
- `/projects/:project_id/characters` - character map operations
- `/projects/:project_id/pipeline-setup` - run configuration and trigger
- `/projects/:project_id/run-monitor` - run lifecycle details
- `/projects/:project_id/export` - export readiness and download
- `/projects/:project_id/dashboards` - analytics visualization

## Stack

- React Router (route-driven workflow)
- Tailwind CSS + global design tokens (`src/styles/globals.css`)
- shadcn/ui component base (customized locally)
- Axios + SWR + Zustand + Zod + date-fns

## Design System

- Core tokens live in `src/styles/globals.css` (`:root`, `.dark`, `@theme inline`).
- App layout uses a narrative shell: left workflow rail + right content canvas.
- Visual style targets: low-noise backgrounds, soft depth, clear hierarchy, and high readability.
- Shared primitives (`button`, `card`, `badge`, `input`, `native-select`) are tuned to the same spacing, radius, and shadow language.

## Scripts

```bash
npm run dev
npm run build
npm run lint
npm run test:unit
npm run test:integration
npm run test:regression
npm run test:vitest
npm run test:e2e
npm run test:visual
npm run test:frontend
```

## Test Layout

- `tests/unit` - isolated utility and pure logic tests
- `tests/integration` - route/component interaction tests
- `tests/regression` - regression guards for previously fixed behavior
- `tests/e2e` - Playwright browser flow and visual tests
- `tests/playwright` - Playwright config
- `tests/vitest` - Vitest setup/util helpers
