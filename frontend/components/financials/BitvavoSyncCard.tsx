"use client";

import { ApiError } from "@/lib/api-client";
import { coinTicker } from "@/lib/coins";
import { formatCurrency } from "@/lib/format";
import { useBitvavoStatus, useBitvavoSync } from "@/lib/queries/useBitvavo";
import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";

export function BitvavoSyncCard() {
  const status = useBitvavoStatus();
  const sync = useBitvavoSync();

  if (status.isLoading || !status.data?.configured) {
    // Silent when not configured -- this is an opt-in integration (needs BITVAVO_API_KEY/
    // SECRET in backend/.env), not something every install should be nagged about.
    return null;
  }

  return (
    <Card>
      <div className="flex items-center justify-between">
        <div>
          <CardTitle>Bitvavo-Synchronisierung</CardTitle>
          <p className="mt-1 text-sm text-slate-500">
            Holt deine vollständige Transaktionshistorie von Bitvavo und ersetzt die entsprechenden Krypto-Einträge
            unten automatisch mit Menge und Ø-Anschaffungspreis.
          </p>
        </div>
        <Button onClick={() => sync.mutate()} disabled={sync.isPending}>
          {sync.isPending ? "Synchronisiere…" : "Jetzt synchronisieren"}
        </Button>
      </div>

      {sync.isError && (
        <p className="mt-3 text-sm text-red-600">
          {sync.error instanceof ApiError ? sync.error.message : "Synchronisierung fehlgeschlagen."}
        </p>
      )}

      {sync.data && (
        <div className="mt-4 space-y-2 border-t border-slate-100 pt-3">
          {sync.data.error && <p className="text-sm text-red-600">{sync.data.error}</p>}
          {sync.data.assets.length === 0 && !sync.data.error && (
            <p className="text-sm text-slate-500">Keine Guthaben auf Bitvavo gefunden.</p>
          )}
          {sync.data.assets.map((asset) => (
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
        </div>
      )}
    </Card>
  );
}
