import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "../api-client";
import type { BitvavoStatus, BitvavoSyncResult } from "../types";

export function useBitvavoStatus() {
  return useQuery({
    queryKey: ["bitvavo", "status"],
    queryFn: () => apiClient.get<BitvavoStatus>("/api/integrations/bitvavo/status"),
  });
}

export function useBitvavoSync() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.post<BitvavoSyncResult>("/api/integrations/bitvavo/sync"),
    onSuccess: () => {
      // A sync can create, replace, or remove FinancialEntry rows -- same fan-out as any
      // other financial-data write (see useFinancials.ts's useInvalidateFinancials).
      queryClient.invalidateQueries({ queryKey: ["financials"] });
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}
