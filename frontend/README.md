# NIPE Frontend

Frontend app for NIPE backend-backed workflow (project setup, ingestion, mode selection, run execution, and export inspection).

## Stack

- React + Vite
- Tailwind CSS v4 (`@tailwindcss/vite`)
- shadcn/ui baseline components (`src/components/ui/*`, `components.json`)
- Axios (API client)
- SWR (async data)
- Zustand (UI state)
- Zod (runtime schema validation)
- date-fns (time formatting)
- Vitest + Testing Library (unit/integration/e2e-style component tests)
- Playwright (browser e2e + visual regression)

## Folder Structure

- `src/main.tsx`: root bootstrap (`RouterProvider`, global styles)
- `src/router/main-routes.tsx`: main app routes
- `src/router/auth-routes.tsx`: auth route tree placeholder
- `src/router/index.tsx`: combined route objects
- `src/styles/globals.css`: global design system + Tailwind utility layers
- `src/components/ui/*`: shadcn/ui primitive components
- `src/shared/*`: reusable API/UI/lib primitives
- `src/features/*`: feature modules
- `src/app/*`: app-level schemas, config, and store
- `tests/unit/*`: unit tests
- `tests/integration/*`: integration tests
- `tests/regression/*`: regression tests
- `tests/e2e/*`: Playwright visual/e2e tests

## Run

```bash
cd frontend
npm install
npm run dev
```

Default API target is `http://localhost:8000`. Override with:

```bash
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

## Build

```bash
cd frontend
npm run build
```

## Tests

Vitest:

```bash
cd frontend
npm run test:run
```

Playwright e2e + visual:

```bash
cd frontend
npx playwright install chromium
npm run test:playwright
```

Update visual snapshots intentionally:

```bash
cd frontend
npm run test:playwright:update
```
