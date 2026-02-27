import type { PropsWithChildren } from 'react';

import { SWRConfig } from 'swr';
import { Toaster } from 'sonner';

import { GlobalHealthDependencyGate } from './global-health-dependency-gate';

export function AppProviders({ children }: PropsWithChildren) {
  return (
    <SWRConfig
      value={{
        revalidateOnFocus: false,
        shouldRetryOnError: false,
      }}
    >
      <GlobalHealthDependencyGate>{children}</GlobalHealthDependencyGate>
      <Toaster richColors position="top-right" closeButton />
    </SWRConfig>
  );
}
