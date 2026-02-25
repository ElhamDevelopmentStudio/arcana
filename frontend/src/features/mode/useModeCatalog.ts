import useSWR from "swr";

import type { ModeCatalog } from "@/app/types";
import type { NipeApiClient } from "@/shared/api/http";

export function useModeCatalog(client: NipeApiClient, enabled: boolean) {
  const swrState = useSWR<ModeCatalog, Error>(
    enabled ? ["mode-catalog", client.baseUrl] : null,
    async () => client.getModeCatalog(),
    {
      revalidateOnFocus: false,
    }
  );

  return {
    ...swrState,
    catalog: swrState.data ?? null,
  };
}
