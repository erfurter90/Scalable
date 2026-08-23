"use client";

import type { UseMutationResult } from "@tanstack/react-query";

import { ApiError } from "@/lib/api-client";
import { coinTicker } from "@/lib/coins";
import { formatCurrency } from "@/lib/format";
import { useBitgetStatus, useBitgetSync } from "@/lib/queries/useBitget";
import { useBitvavoStatus, useBitvavoSync } from "@/lib/queries/useBitvavo";
import { useCoinbaseStatus, useCoinbaseSync } from "@/lib/queries/useCoinbase";
import type { BitgetSyncResult, BitvavoSyncResult, CoinbaseSyncResult } from "@/lib/types";
import { Card } from "@/components/ui/Card";

type SyncResult = BitvavoSyncResult | BitgetSyncResult | CoinbaseSyncResult;

interface ExchangeConfig {
  key: string;
  label: string;
  configured: boolean | undefined;
  // Readable, muted colors (not garish) that still contrast well with white text.
  colorClass: string;
  sync: UseMutationResult<SyncResult, unknown, void, unknown>;
}

export function ExchangeSyncPanel() {
  const bitvavoStatus = useBitvavoStatus();
  const bitvavoSync = useBitvavoSync();
  const bitgetStatus = useBitgetStatus();
  const bitgetSync = useBitgetSync();
  const coinbaseStatus = useCoinbaseStatus();
  const coinbaseSync = useCoinbaseSync();

  const exchanges: ExchangeConfig[] = [
    {
      key: "bitvavo",
      label: "Bitvavo",
      configured: bitvavoStatus.data?.configured,
      colorClass: "bg-blue-600 hover:bg-blue-700",
      sync: bitvavoSync,
    },
    {
      key: "bitget",
      label: "Bitget",
      configured: bitgetStatus.data?.configured,
      colorClass: "bg-emerald-600 hover:bg-emerald-700",
      sync: bitgetSync,
    },
    {
      key: "coinbase",
      label: "Coinbase",
      configured: coinbaseStatus.data?.configured,
      colorClass: "bg-indigo-600 hover:bg-indigo-700",
      sync: coinbaseSync,
    },
  ].filter((exchange) => exchange.configured);

  if (exchanges.length === 0) {
    // Silent when nothing is configured -- these are opt-in integrations (need API keys in
    // backend/.env), not something every install should be nagged about.
    return null;
  }

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-3">
        <span className="shrink-0 text-sm font-medium text-slate-500">Synchronisierung</span>
        <div className="grid grow grid-cols-5 justify-items-start gap-2">
          {exchanges.map((exchange) => (
            <button
              key={exchange.key}
              onClick={() => exchange.sync.mutate()}
              disabled={exchange.sync.isPending}
              className={`rounded-lg px-4 py-2 text-sm font-medium text-white transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${exchange.colorClass}`}
            >
              {exchange.sync.isPending ? "Synchronisiere…" : exchange.label}
            </button>
          ))}
        </div>
      </div>

      {exchanges.map((exchange) => {
        if (!exchange.sync.isError && !exchange.sync.data) return null;
        return (
          <div key={exchange.key} className="mt-4 space-y-2 border-t border-slate-100 pt-3">
            <p className="text-xs font-medium text-slate-500">{exchange.label}</p>

            {exchange.sync.isError && (
              <p className="text-sm text-red-600">
                {exchange.sync.error instanceof ApiError ? exchange.sync.error.message : "Synchronisierung fehlgeschlagen."}
              </p>
            )}

            {exchange.sync.data && (
              <>
                {exchange.sync.data.error && <p className="text-sm text-red-600">{exchange.sync.data.error}</p>}
                {exchange.sync.data.assets.length === 0 && !exchange.sync.data.error && (
                  <p className="text-sm text-slate-500">Keine Guthaben auf {exchange.label} gefunden.</p>
                )}
                {exchange.sync.data.assets.map((asset) => (
                  <div key={asset.symbol} className="text-sm">
                    <span className="font-medium">{coinTicker(asset.coingecko_id ?? asset.symbol)}</span>{" "}
                    {asset.error ? (
                      <span className="text-red-600">{asset.error}</span>
                    ) : (
                      <span className="text-slate-600">
                        {parseFloat(asset.quantity).toString()} Stück
                        {asset.current_value_eur && ` · ${formatCurrency(asset.current_value_eur)}`}
                        {asset.average_cost_basis && ` · Ø ${formatCurrency(asset.average_cost_basis)}`}
                        {asset.cost_basis_incomplete && (
                          <span className="text-amber-600"> · Ø unvollständig (Einzahlung ohne bekannten Kaufpreis)</span>
                        )}
                        {asset.replaced_entry_labels.length > 0 &&
                          ` · ersetzt: ${asset.replaced_entry_labels.join(", ")}`}
                      </span>
                    )}
                    {asset.note && <span className="block text-xs text-amber-600">{asset.note}</span>}
                  </div>
                ))}
              </>
            )}
          </div>
        );
      })}
    </Card>
  );
}
