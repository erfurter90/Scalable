import { useQuery } from "@tanstack/react-query";

import { apiClient } from "../api-client";
import type { Score } from "../types";

export function useCurrentScore() {
  return useQuery({
    queryKey: ["score", "current"],
    queryFn: () => apiClient.get<Score>("/api/score/current"),
  });
}

export function useScoreHistory() {
  return useQuery({
    queryKey: ["score", "history"],
    queryFn: () => apiClient.get<Score[]>("/api/score/history"),
  });
}
