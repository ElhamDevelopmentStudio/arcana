import type { PropsWithChildren } from 'react';

import { SWRConfig } from 'swr';
import { Toaster } from 'sonner';

export function AppProviders({ children }: PropsWithChildren) {
  return (
    <SWRConfig
      value={{
        revalidateOnFocus: false,
        shouldRetryOnError: false,
      }}
    >
      {children}
      <Toaster richColors position="top-right" closeButton />
    </SWRConfig>
  );
}
