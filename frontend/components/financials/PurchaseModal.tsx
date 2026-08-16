"use client";

import { useState } from "react";

import { ApiError } from "@/lib/api-client";
import { coinTicker } from "@/lib/coins";
import { useAddPurchase, useSetCostBasis } from "@/lib/queries/useFinancials";
import type { FinancialEntry, PurchaseCurrency } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Input, Label, Select } from "@/components/ui/Input";

export function PurchaseModal({ entry, onClose }: { entry: FinancialEntry; onClose: () => void }) {
  const addPurchase = useAddPurchase();
  const setCostBasis = useSetCostBasis();
  // No cost basis recorded yet -> this is establishing the initial acquisition price for the
  // *existing* quantity (no quantity change). Once one exists, further purchases blend in.
  const isInitialCostBasis = entry.average_cost_basis === null;

  const [additionalQuantity, setAdditionalQuantity] = useState("");
  const [purchasePrice, setPurchasePrice] = useState("");
  const [purchasePriceCurrency, setPurchasePriceCurrency] = useState<PurchaseCurrency>("EUR");
  const [error, setError] = useState<string | null>(null);

  const ticker = entry.price_asset_id ? coinTicker(entry.price_asset_id) : "";
  const isPending = addPurchase.isPending || setCostBasis.isPending;

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    try {
      if (isInitialCostBasis) {
        await setCostBasis.mutateAsync({
          id: entry.id,
          data: { purchase_price: purchasePrice, purchase_price_currency: purchasePriceCurrency },
        });
      } else {
        await addPurchase.mutateAsync({
          id: entry.id,
          data: {
            additional_quantity: additionalQuantity,
            purchase_price: purchasePrice,
            purchase_price_currency: purchasePriceCurrency,
          },
        });
      }
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Speichern fehlgeschlagen.");
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <form onSubmit={handleSubmit} className="w-full max-w-md rounded-xl bg-white p-6 shadow-lg">
        <h2 className="mb-1 text-base font-semibold">
          {isInitialCostBasis ? "Anschaffungspreis erfassen" : "Nachkauf"}: {entry.label}
        </h2>
        <p className="mb-4 text-xs text-slate-500">
          {isInitialCostBasis
            ? `Für deine bestehende Menge von ${parseFloat(entry.quantity ?? "0")} ${ticker} — die Menge selbst ändert sich dabei nicht.`
            : `Bisherige Menge: ${parseFloat(entry.quantity ?? "0")} ${ticker} · Ø-Einstand bisher: ${parseFloat(entry.average_cost_basis ?? "0").toLocaleString("de-DE")} €`}
        </p>

        {!isInitialCostBasis && (
          <div className="mb-3">
            <Label htmlFor="additional_quantity">Zusätzliche Menge</Label>
            <Input
              id="additional_quantity"
              type="number"
              step="any"
              min="0.00000001"
              value={additionalQuantity}
              onChange={(e) => setAdditionalQuantity(e.target.value)}
              required
            />
          </div>
        )}

        <div className="mb-4">
          <Label htmlFor="new_purchase_price">
            {isInitialCostBasis ? "Durchschnittlicher Kaufpreis pro Einheit" : "Kaufpreis pro Einheit"}
          </Label>
          <div className="grid grid-cols-2 gap-3">
            <Input
              id="new_purchase_price"
              type="number"
              step="any"
              min="0.00000001"
              value={purchasePrice}
              onChange={(e) => setPurchasePrice(e.target.value)}
              required
            />
            <Select
              value={purchasePriceCurrency}
              onChange={(e) => setPurchasePriceCurrency(e.target.value as PurchaseCurrency)}
            >
              <option value="EUR">EUR</option>
              <option value="USD">USD</option>
            </Select>
          </div>
        </div>

        {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Abbrechen
          </Button>
          <Button type="submit" disabled={isPending}>
            {isPending ? "Speichern…" : "Speichern"}
          </Button>
        </div>
      </form>
    </div>
  );
}
