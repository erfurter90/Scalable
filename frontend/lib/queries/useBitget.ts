import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "../api-client";
import type { BitgetStatus, BitgetSyncResult } from "../types";

export function useBitgetStatus() {
  return useQuery({
    queryKey: ["bitget", "status"],
    queryFn: () => apiClient.get<BitgetStatus>("/api/integrations/bitget/status"),
  });
}

export function useBitgetSync() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.post<BitgetSyncResult>("/api/integrations/bitget/sync"),
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
