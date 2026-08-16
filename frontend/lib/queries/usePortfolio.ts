import { useQuery } from "@tanstack/react-query";

import { apiClient, ApiError } from "../api-client";
import type { PortfolioAllocation } from "../types";

export function usePortfolioAllocation() {
  return useQuery({
    queryKey: ["portfolio", "allocation"],
    queryFn: () => apiClient.get<PortfolioAllocation>("/api/portfolio/allocation"),
    retry: (failureCount, error) => error instanceof ApiError && error.status === 404 ? false : failureCount < 1,
  });
}
