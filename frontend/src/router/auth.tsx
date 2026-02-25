import { lazy, Suspense, type ReactNode } from 'react';
import type { RouteObject } from 'react-router-dom';

const AuthPlaceholderPage = lazy(() =>
  import('@/pages/auth/auth-placeholder-page').then((module) => ({ default: module.AuthPlaceholderPage })),
);

const AUTH_ROUTE_SUSPENSE_FALLBACK = (
  <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">Loading auth...</div>
);

function SuspendedRoute({ children }: { children: ReactNode }) {
  return <Suspense fallback={AUTH_ROUTE_SUSPENSE_FALLBACK}>{children}</Suspense>;
}

export const authRouter: RouteObject[] = [
  {
    index: true,
    element: <SuspendedRoute><AuthPlaceholderPage /></SuspendedRoute>,
  },
];
