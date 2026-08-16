"use client";

import { useState } from "react";

import { useCreateFinancialEntry, useUpdateFinancialEntry } from "@/lib/queries/useFinancials";
import type {
  AssetSubcategory,
  EntryType,
  FinancialEntry,
  FinancialEntryCreate,
  FinancialEntryUpdate,
  PurchaseCurrency,
} from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Input, Label, Select } from "@/components/ui/Input";
import { ApiError } from "@/lib/api-client";

const ENTRY_TYPES: { value: EntryType; label: string }[] = [
  { value: "income", label: "Einnahme" },
  { value: "expense", label: "Ausgabe" },
  { value: "asset", label: "Vermögenswert" },
  { value: "liability", label: "Verbindlichkeit" },
];

const ASSET_SUBCATEGORIES: { value: AssetSubcategory; label: string }[] = [
  { value: "cash", label: "Cash" },
  { value: "btc", label: "BTC" },
  { value: "crypto", label: "Andere Krypto" },
  { value: "stocks", label: "Aktien" },
  { value: "etf", label: "ETF" },
  { value: "other", label: "Sonstiges" },
];

// Subcategories where a live-priced quantity ("0.2 BTC") makes sense instead of a manually
// typed, immediately-stale EUR figure.
const QUANTITY_SUBCATEGORIES: AssetSubcategory[] = ["btc", "crypto"];

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

type ValuationMode = "amount" | "quantity";

export function EntryFormModal({ entry, onClose }: { entry: FinancialEntry | null; onClose: () => void }) {
  const isEditing = entry !== null;
  const create = useCreateFinancialEntry();
  const update = useUpdateFinancialEntry();

  const [entryType, setEntryType] = useState<EntryType>(entry?.entry_type ?? "expense");
  const [category, setCategory] = useState(entry?.category ?? "");
  const [subcategory, setSubcategory] = useState<AssetSubcategory>((entry?.subcategory as AssetSubcategory) ?? "cash");
  const [label, setLabel] = useState(entry?.label ?? "");
  const [amount, setAmount] = useState(entry?.amount ?? "");
  const [valuationMode, setValuationMode] = useState<ValuationMode>(entry?.quantity ? "quantity" : "amount");
  const [quantity, setQuantity] = useState(entry?.quantity ?? "");
  const [priceAssetId, setPriceAssetId] = useState(entry?.price_asset_id ?? "");
  const [purchasePrice, setPurchasePrice] = useState("");
  const [purchasePriceCurrency, setPurchasePriceCurrency] = useState<PurchaseCurrency>("EUR");
  const [currency, setCurrency] = useState(entry?.currency ?? "EUR");
  const [snapshotDate, setSnapshotDate] = useState(entry?.snapshot_date ?? todayIso());
  const [notes, setNotes] = useState(entry?.notes ?? "");
  const [error, setError] = useState<string | null>(null);

  const isPending = create.isPending || update.isPending;
  const supportsQuantity = entryType === "asset" && QUANTITY_SUBCATEGORIES.includes(subcategory);
  const isQuantityMode = supportsQuantity && valuationMode === "quantity";
  // BTC always prices against "bitcoin"; for other coins the user names the CoinGecko id.
  const effectivePriceAssetId = subcategory === "btc" ? "bitcoin" : priceAssetId;

  function handleSubcategoryChange(value: AssetSubcategory) {
    setSubcategory(value);
    if (!QUANTITY_SUBCATEGORIES.includes(value)) {
      setValuationMode("amount");
    }
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    const base = {
      category,
      subcategory: entryType === "asset" ? subcategory : null,
      label,
      currency,
      snapshot_date: snapshotDate,
      notes: notes || null,
    };

    try {
      if (isEditing) {
        const payload: FinancialEntryUpdate = isQuantityMode
          ? { ...base, quantity, price_asset_id: effectivePriceAssetId }
          : { ...base, amount, quantity: null, price_asset_id: null };
        await update.mutateAsync({ id: entry.id, data: payload });
      } else {
        const payload: FinancialEntryCreate = isQuantityMode
          ? {
              ...base,
              entry_type: entryType,
              quantity,
              price_asset_id: effectivePriceAssetId,
              ...(purchasePrice
                ? { purchase_price: purchasePrice, purchase_price_currency: purchasePriceCurrency }
                : {}),
            }
          : { ...base, entry_type: entryType, amount };
        await create.mutateAsync(payload);
      }
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Speichern fehlgeschlagen.");
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <form onSubmit={handleSubmit} className="w-full max-w-md rounded-xl bg-white p-6 shadow-lg">
        <h2 className="mb-4 text-base font-semibold">{isEditing ? "Eintrag bearbeiten" : "Neuer Eintrag"}</h2>

        <div className="mb-3">
          <Label htmlFor="entry_type">Typ</Label>
          <Select id="entry_type" value={entryType} onChange={(e) => setEntryType(e.target.value as EntryType)}>
            {ENTRY_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </Select>
        </div>

        {entryType === "asset" && (
          <div className="mb-3">
            <Label htmlFor="subcategory">Asset-Klasse</Label>
            <Select
              id="subcategory"
              value={subcategory}
              onChange={(e) => handleSubcategoryChange(e.target.value as AssetSubcategory)}
            >
              {ASSET_SUBCATEGORIES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </Select>
          </div>
        )}

        <div className="mb-3">
          <Label htmlFor="category">Kategorie</Label>
          <Input id="category" value={category} onChange={(e) => setCategory(e.target.value)} required />
        </div>

        <div className="mb-3">
          <Label htmlFor="label">Bezeichnung</Label>
          <Input id="label" value={label} onChange={(e) => setLabel(e.target.value)} required />
        </div>

        {supportsQuantity && (
          <div className="mb-3 flex gap-1 rounded-lg bg-slate-100 p-1 text-xs">
            <button
              type="button"
              onClick={() => setValuationMode("amount")}
              className={`flex-1 rounded-md py-1.5 font-medium ${
                valuationMode === "amount" ? "bg-white shadow-sm" : "text-slate-500"
              }`}
            >
              Betrag eingeben
            </button>
            <button
              type="button"
              onClick={() => setValuationMode("quantity")}
              className={`flex-1 rounded-md py-1.5 font-medium ${
                valuationMode === "quantity" ? "bg-white shadow-sm" : "text-slate-500"
              }`}
            >
              Menge eingeben
            </button>
          </div>
        )}

        {isQuantityMode ? (
          <div className="mb-3 grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="quantity">Menge</Label>
              <Input
                id="quantity"
                type="number"
                step="any"
                min="0.00000001"
                placeholder={subcategory === "btc" ? "z. B. 0.2" : "z. B. 3"}
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                required
              />
            </div>
            <div>
              <Label htmlFor="price_asset_id">Coin</Label>
              {subcategory === "btc" ? (
                <Input id="price_asset_id" value="Bitcoin" disabled />
              ) : (
                <Input
                  id="price_asset_id"
                  placeholder="z. B. ethereum, solana"
                  value={priceAssetId}
                  onChange={(e) => setPriceAssetId(e.target.value)}
                  required
                />
              )}
            </div>
          </div>
        ) : (
          <div className="mb-3">
            <Label htmlFor="amount">Betrag</Label>
            <Input
              id="amount"
              type="number"
              step="any"
              min="0.00000001"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              required
            />
            <p className="mt-1 text-xs text-slate-400">
              Beliebige Nachkommastellen möglich — z. B. auch ein präziser Krypto-Betrag mit Währung
              &quot;BTC&quot; statt EUR.
            </p>
          </div>
        )}

        {isQuantityMode && subcategory === "crypto" && (
          <p className="mb-3 -mt-1 text-xs text-slate-400">
            Exakte CoinGecko-ID verwenden (z. B. &quot;ethereum&quot; statt &quot;ETH&quot;), auffindbar auf
            coingecko.com in der URL der jeweiligen Coin-Seite.
          </p>
        )}

        {isQuantityMode && !isEditing && (
          <div className="mb-3">
            <Label htmlFor="purchase_price">Anschaffungspreis pro Einheit (optional)</Label>
            <div className="grid grid-cols-2 gap-3">
              <Input
                id="purchase_price"
                type="number"
                step="any"
                min="0.00000001"
                placeholder="z. B. 50000"
                value={purchasePrice}
                onChange={(e) => setPurchasePrice(e.target.value)}
              />
              <Select
                value={purchasePriceCurrency}
                onChange={(e) => setPurchasePriceCurrency(e.target.value as PurchaseCurrency)}
              >
                <option value="EUR">EUR</option>
                <option value="USD">USD</option>
              </Select>
            </div>
            <p className="mt-1 text-xs text-slate-400">
              Für die Berechnung des durchschnittlichen Einstandspreises. USD wird zum aktuellen Kurs in EUR
              umgerechnet. Für spätere Nachkäufe zu anderen Preisen nutze &quot;Nachkauf&quot; in der Tabelle.
            </p>
          </div>
        )}

        <div className="mb-3">
          <Label htmlFor="currency">Währung</Label>
          <Input id="currency" value={currency} onChange={(e) => setCurrency(e.target.value)} required />
        </div>

        <div className="mb-3">
          <Label htmlFor="snapshot_date">Datum</Label>
          <Input
            id="snapshot_date"
            type="date"
            value={snapshotDate}
            onChange={(e) => setSnapshotDate(e.target.value)}
            required
          />
        </div>

        <div className="mb-4">
          <Label htmlFor="notes">Notizen (optional)</Label>
          <Input id="notes" value={notes} onChange={(e) => setNotes(e.target.value)} />
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
