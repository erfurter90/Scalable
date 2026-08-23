import { useQuery } from "@tanstack/react-query";

import { apiClient } from "../api-client";
import type { RecentTransaction } from "../types";

export function useRecentTransactions() {
  return useQuery({
    queryKey: ["transactions", "recent"],
    queryFn: () => apiClient.get<RecentTransaction[]>("/api/transactions/recent"),
  });
}
