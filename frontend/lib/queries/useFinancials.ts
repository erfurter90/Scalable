import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "../api-client";
import type {
  CostBasisSet,
  FinancialEntry,
  FinancialEntryCreate,
  FinancialEntryUpdate,
  NetWorthSnapshot,
  PurchaseCreate,
} from "../types";

export function useFinancialEntries() {
  return useQuery({
    queryKey: ["financials", "entries"],
    queryFn: () => apiClient.get<FinancialEntry[]>("/api/financials/entries"),
  });
}

export function useNetWorthHistory() {
  return useQuery({
    queryKey: ["financials", "net-worth-history"],
    queryFn: () => apiClient.get<NetWorthSnapshot[]>("/api/financials/net-worth-history"),
  });
}

function useInvalidateFinancials() {
  const queryClient = useQueryClient();
  return () => {
    // A single entry write can affect entries, both net-worth views, portfolio, and the
    // combined dashboard aggregate — invalidate everything derived from financial data.
    queryClient.invalidateQueries({ queryKey: ["financials"] });
    queryClient.invalidateQueries({ queryKey: ["portfolio"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  };
}

export function useCreateFinancialEntry() {
  const invalidate = useInvalidateFinancials();
  return useMutation({
    mutationFn: (data: FinancialEntryCreate) => apiClient.post<FinancialEntry>("/api/financials/entries", data),
    onSuccess: invalidate,
  });
}

export function useUpdateFinancialEntry() {
  const invalidate = useInvalidateFinancials();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: FinancialEntryUpdate }) =>
      apiClient.put<FinancialEntry>(`/api/financials/entries/${id}`, data),
    onSuccess: invalidate,
  });
}

export function useDeleteFinancialEntry() {
  const invalidate = useInvalidateFinancials();
  return useMutation({
    mutationFn: (id: number) => apiClient.delete<void>(`/api/financials/entries/${id}`),
    onSuccess: invalidate,
  });
}

export function useRefreshEntryValue() {
  const invalidate = useInvalidateFinancials();
  return useMutation({
    mutationFn: (id: number) => apiClient.post<FinancialEntry>(`/api/financials/entries/${id}/refresh-value`),
    onSuccess: invalidate,
  });
}

export function useAddPurchase() {
  const invalidate = useInvalidateFinancials();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: PurchaseCreate }) =>
      apiClient.post<FinancialEntry>(`/api/financials/entries/${id}/add-purchase`, data),
    onSuccess: invalidate,
  });
}

export function useSetCostBasis() {
  const invalidate = useInvalidateFinancials();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: CostBasisSet }) =>
      apiClient.post<FinancialEntry>(`/api/financials/entries/${id}/set-cost-basis`, data),
    onSuccess: invalidate,
  });
}
