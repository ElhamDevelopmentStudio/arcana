import type { PropsWithChildren } from 'react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { useHealthQuery } from '@/features/workflow/api/workflow-hooks';

function isHealthyStatus(status: string | null | undefined) {
  return typeof status === 'string' && status.trim().toLowerCase() === 'ok';
}

export function GlobalHealthDependencyGate({ children }: PropsWithChildren) {
  const healthQuery = useHealthQuery(true);
  const healthy = isHealthyStatus(healthQuery.data?.status);
  const hasHealthError = Boolean(healthQuery.error);
  const isBlocked = hasHealthError || (healthQuery.data !== undefined && !healthy);

  if (!isBlocked) {
    return <>{children}</>;
  }

  const detail = hasHealthError
    ? healthQuery.error instanceof Error
      ? healthQuery.error.message
      : 'Unable to reach backend health endpoint.'
    : `Backend health status is "${healthQuery.data?.status ?? 'unknown'}".`;

  return (
    <div className="relative min-h-screen">
      <div
        aria-hidden="true"
        className="pointer-events-none select-none opacity-45"
        data-testid="global-health-gate-content"
      >
        {children}
      </div>
      <div className="fixed inset-x-0 top-0 z-[120] p-3">
        <Alert className="mx-auto max-w-4xl border-destructive/45 bg-destructive/12 text-destructive" data-testid="global-health-gate-alert" variant="destructive">
          <AlertTitle>Backend dependency unavailable</AlertTitle>
          <AlertDescription className="space-y-2">
            <p data-testid="global-health-gate-detail">
              Health checks must pass before workspace actions are reliable. {detail}
            </p>
            <Button
              className="border-destructive/45 bg-transparent text-destructive hover:bg-destructive/14"
              data-testid="global-health-gate-retry"
              size="sm"
              variant="outline"
              onClick={() => {
                void healthQuery.mutate();
              }}
            >
              Retry health check
            </Button>
          </AlertDescription>
        </Alert>
      </div>
    </div>
  );
}
