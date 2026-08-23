import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "../api-client";
import type { CoinbaseStatus, CoinbaseSyncResult } from "../types";

export function useCoinbaseStatus() {
  return useQuery({
    queryKey: ["coinbase", "status"],
    queryFn: () => apiClient.get<CoinbaseStatus>("/api/integrations/coinbase/status"),
  });
}

export function useCoinbaseSync() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.post<CoinbaseSyncResult>("/api/integrations/coinbase/sync"),
    onSuccess: () => {
      // A sync can create, replace, or remove FinancialEntry rows -- same fan-out as any
      // other financial-data write (see useFinancials.ts's useInvalidateFinancials).
      queryClient.invalidateQueries({ queryKey: ["financials"] });
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
  });
}
