import { formatCurrency, formatPercent } from "@/lib/format";
import type { BtcPrice } from "@/lib/types";
import { Card, CardTitle } from "@/components/ui/Card";
import { StatusBadge } from "@/components/ui/StatusBadge";

export function BtcPriceCard({ btc }: { btc: BtcPrice }) {
  return (
    <Card>
      <div className="flex items-center justify-between">
        <CardTitle>BTC Preis</CardTitle>
        <StatusBadge status={btc.usd.status} />
      </div>
      {btc.usd.status === "ok" && btc.usd.value !== null ? (
        <>
          <p className="mt-1 text-2xl font-semibold">{formatCurrency(btc.usd.value, "USD")}</p>
          {btc.eur.status === "ok" && btc.eur.value !== null && (
            <p className="text-sm text-slate-500">{formatCurrency(btc.eur.value, "EUR")}</p>
          )}
          <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
            <ChangeStat label="24h" value={btc.change_24h.value} status={btc.change_24h.status} />
            <ChangeStat label="7d" value={btc.change_7d.value} status={btc.change_7d.status} />
            <ChangeStat label="30d" value={btc.change_30d.value} status={btc.change_30d.status} />
          </div>
        </>
      ) : (
        <p className="mt-2 text-sm text-slate-500">BTC-Preis derzeit nicht verfügbar.</p>
      )}
    </Card>
  );
}

function ChangeStat({ label, value, status }: { label: string; value: number | null; status: string }) {
  const positive = value !== null && value >= 0;
  return (
    <div>
      <span className="block text-slate-400">{label}</span>
      {status === "ok" && value !== null ? (
        <span className={positive ? "text-emerald-600" : "text-red-600"}>{formatPercent(value)}</span>
      ) : (
        <span className="text-slate-400">—</span>
      )}
    </div>
  );
}
