import type { PropsWithChildren } from 'react';

import { SWRConfig } from 'swr';
import { Toaster } from 'sonner';

import { GlobalHealthDependencyGate } from './global-health-dependency-gate';
import { MutationEventBusBridge } from './mutation-event-bus-bridge';
import { JobNotificationCenter } from '@/components/notifications/job-notification-center';

export function AppProviders({ children }: PropsWithChildren) {
  return (
    <SWRConfig
      value={{
        revalidateOnFocus: false,
        shouldRetryOnError: false,
      }}
    >
      <GlobalHealthDependencyGate>{children}</GlobalHealthDependencyGate>
      <MutationEventBusBridge />
      <JobNotificationCenter />
      <Toaster richColors position="top-right" closeButton />
    </SWRConfig>
  );
}
