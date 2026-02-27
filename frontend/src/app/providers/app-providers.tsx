import type { PropsWithChildren } from 'react';

import { SWRConfig } from 'swr';
import { Toaster } from 'sonner';

import { GlobalHealthDependencyGate } from './global-health-dependency-gate';
import { MutationEventBusBridge } from './mutation-event-bus-bridge';

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
      <Toaster richColors position="top-right" closeButton />
    </SWRConfig>
  );
}
