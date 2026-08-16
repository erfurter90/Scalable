"use client";

import { useMemo, useState } from "react";

import { ApiError } from "@/lib/api-client";
import { coinTicker } from "@/lib/coins";
import { formatCurrency, formatDate, formatPercent } from "@/lib/format";
import { useDeleteFinancialEntry, useRefreshEntryValue } from "@/lib/queries/useFinancials";
import type { FinancialEntry } from "@/lib/types";
import { Button } from "@/components/ui/Button";

const TYPE_LABELS: Record<string, string> = {
  income: "Einnahme",
  expense: "Ausgabe",
  asset: "Vermögenswert",
  liability: "Verbindlichkeit",
};

type SortKey = "date" | "type" | "category" | "label" | "amount";
type SortDirection = "asc" | "desc";

const COLUMNS: { key: SortKey; label: string; align?: "right" }[] = [
  { key: "date", label: "Datum" },
  { key: "type", label: "Typ" },
  { key: "category", label: "Kategorie" },
  { key: "label", label: "Bezeichnung" },
  { key: "amount", label: "Betrag", align: "right" },
];

function sortValue(entry: FinancialEntry, key: SortKey): string | number {
  switch (key) {
    case "date":
      return entry.snapshot_date;
    case "type":
      return TYPE_LABELS[entry.entry_type] ?? entry.entry_type;
    case "category":
      return entry.category.toLowerCase();
    case "label":
      return entry.label.toLowerCase();
    case "amount":
      return Number(entry.amount);
  }
}

function formatQuantity(quantity: string, priceAssetId: string | null): string {
  // Trim trailing zeros from the Numeric(30,10) string the backend returns (e.g.
  // "0.2000000000" -> "0.2") for a readable display.
  const trimmed = parseFloat(quantity).toString();
  const unit = priceAssetId ? coinTicker(priceAssetId) : "";
  return `${trimmed} ${unit}`.trim();
}

function gainLoss(entry: FinancialEntry): { abs: number; pct: number } | null {
  // average_cost_basis is always EUR (see backend); only compare directly against `amount`
  // when the entry's own current-value currency is EUR too, to avoid mixing units.
  if (!entry.average_cost_basis || !entry.quantity || entry.currency.toUpperCase() !== "EUR") {
    return null;
  }
  const costBasisTotal = parseFloat(entry.quantity) * parseFloat(entry.average_cost_basis);
  if (costBasisTotal === 0) return null;
  const abs = Number(entry.amount) - costBasisTotal;
  return { abs, pct: (abs / costBasisTotal) * 100 };
}

export function EntryTable({
  entries,
  onEdit,
  onAddPurchase,
}: {
  entries: FinancialEntry[];
  onEdit: (entry: FinancialEntry) => void;
  onAddPurchase: (entry: FinancialEntry) => void;
}) {
  const deleteEntry = useDeleteFinancialEntry();
  const refreshValue = useRefreshEntryValue();
  const [pendingDeleteId, setPendingDeleteId] = useState<number | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  // No sort applied by default -> keeps the backend's own order (newest entry first).
  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");

  const sortedEntries = useMemo(() => {
    if (!sortKey) return entries;
    return [...entries].sort((a, b) => {
      const va = sortValue(a, sortKey);
      const vb = sortValue(b, sortKey);
      const cmp = typeof va === "number" && typeof vb === "number" ? va - vb : String(va).localeCompare(String(vb));
      return sortDirection === "asc" ? cmp : -cmp;
    });
  }, [entries, sortKey, sortDirection]);

  if (entries.length === 0) {
    return <p className="text-sm text-slate-500">Noch keine Einträge erfasst.</p>;
  }

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDirection((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDirection("asc");
    }
  }

  async function handleDelete(id: number) {
    await deleteEntry.mutateAsync(id);
    setPendingDeleteId(null);
  }

  async function handleRefresh(id: number) {
    setRefreshError(null);
    try {
      await refreshValue.mutateAsync(id);
    } catch (err) {
      setRefreshError(err instanceof ApiError ? err.message : "Aktualisierung fehlgeschlagen.");
    }
  }

  return (
    <div className="overflow-x-auto">
      {refreshError && <p className="mb-2 text-sm text-red-600">{refreshError}</p>}
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-xs text-slate-500">
            {COLUMNS.map((column) => (
              <th key={column.key} className={`py-2 pr-3 font-medium ${column.align === "right" ? "text-right" : ""}`}>
                <button
                  type="button"
                  onClick={() => handleSort(column.key)}
                  className={`inline-flex items-center gap-1 hover:text-slate-700 ${
                    column.align === "right" ? "flex-row-reverse" : ""
                  }`}
                >
                  {column.label}
                  <span className="w-3 text-slate-400">
                    {sortKey === column.key ? (sortDirection === "asc" ? "▲" : "▼") : ""}
                  </span>
                </button>
              </th>
            ))}
            <th className="py-2 pr-3 font-medium" />
          </tr>
        </thead>
        <tbody>
          {sortedEntries.map((entry) => {
            const gl = gainLoss(entry);
            return (
            <tr key={entry.id} className="border-b border-slate-100">
              <td className="py-2 pr-3 text-slate-500">{formatDate(entry.snapshot_date)}</td>
              <td className="py-2 pr-3">{TYPE_LABELS[entry.entry_type]}</td>
              <td className="py-2 pr-3 text-slate-500">
                {entry.category}
                {entry.subcategory ? ` · ${entry.subcategory}` : ""}
              </td>
              <td className="py-2 pr-3">
                {entry.label}
                {entry.source === "bitvavo" && (
                  <span
                    className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500"
                    title="Automatisch von Bitvavo synchronisiert — wird beim nächsten Sync überschrieben"
                  >
                    Bitvavo
                  </span>
                )}
              </td>
              <td className="py-2 pr-3 text-right">
                {formatCurrency(entry.amount, entry.currency)}
                {entry.quantity && (
                  <span className="block text-xs text-slate-400">
                    {formatQuantity(entry.quantity, entry.price_asset_id)}
                  </span>
                )}
                {entry.average_cost_basis && (
                  <span className="block text-xs text-slate-400">
                    Ø {formatCurrency(entry.average_cost_basis)}
                  </span>
                )}
                {gl && (
                  <span className={`block text-xs font-medium ${gl.abs >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                    {formatPercent(gl.pct)} ({gl.abs >= 0 ? "+" : ""}
                    {formatCurrency(gl.abs)})
                  </span>
                )}
              </td>
              <td className="py-2 pr-3 text-right">
                {pendingDeleteId === entry.id ? (
                  <span className="flex items-center justify-end gap-1">
                    <Button variant="danger" onClick={() => handleDelete(entry.id)} disabled={deleteEntry.isPending}>
                      Löschen bestätigen
                    </Button>
                    <Button variant="secondary" onClick={() => setPendingDeleteId(null)}>
                      Abbrechen
                    </Button>
                  </span>
                ) : (
                  <span className="flex items-center justify-end gap-1">
                    {entry.quantity && (
                      <Button
                        variant="secondary"
                        onClick={() => handleRefresh(entry.id)}
                        disabled={refreshValue.isPending}
                        title="Betrag mit aktuellem Kurs neu berechnen"
                      >
                        Wert aktualisieren
                      </Button>
                    )}
                    {entry.quantity && entry.source !== "bitvavo" && (
                      <Button
                        variant="secondary"
                        onClick={() => onAddPurchase(entry)}
                        title={
                          entry.average_cost_basis
                            ? "Weitere Menge zu einem Kaufpreis hinzufügen"
                            : "Anschaffungspreis für die bestehende Menge festlegen"
                        }
                      >
                        {entry.average_cost_basis ? "Nachkauf" : "Anschaffungspreis"}
                      </Button>
                    )}
                    <Button variant="secondary" onClick={() => onEdit(entry)}>
                      Bearbeiten
                    </Button>
                    <Button variant="danger" onClick={() => setPendingDeleteId(entry.id)}>
                      Löschen
                    </Button>
                  </span>
                )}
              </td>
            </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
