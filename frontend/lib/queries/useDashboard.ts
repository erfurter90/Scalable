import { useQuery } from "@tanstack/react-query";

import { apiClient } from "../api-client";
import type { Dashboard } from "../types";

export function useDashboard() {
  return useQuery({
    queryKey: ["dashboard"],
    queryFn: () => apiClient.get<Dashboard>("/api/dashboard"),
  });
}
