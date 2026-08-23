import { formatCurrencyOrMask, formatPercent } from "@/lib/format";
import { usePrivacyMode } from "@/lib/privacy-context";
import type { NetWorthChange, NetWorthSnapshot } from "@/lib/types";
import { Card, CardTitle } from "@/components/ui/Card";

export function NetWorthCard({
  netWorth,
  change,
}: {
  netWorth: NetWorthSnapshot | null;
  change: NetWorthChange | null;
}) {
  const { hidden } = usePrivacyMode();

  if (!netWorth) {
    return (
      <Card>
        <CardTitle>Nettovermögen</CardTitle>
        <p className="mt-2 text-sm text-slate-500">Noch keine Finanzdaten erfasst.</p>
      </Card>
    );
  }

  return (
    <Card>
      <CardTitle>Nettovermögen</CardTitle>
      <p className="mt-1 text-2xl font-semibold">{formatCurrencyOrMask(netWorth.net_worth, hidden)}</p>
      {change && change.change_pct !== null && (
        <p className={`mt-1 text-sm ${change.change_abs >= 0 ? "text-emerald-600" : "text-red-600"}`}>
          {formatPercent(change.change_pct)} ggü. vor 30 Tagen
        </p>
      )}
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-500">
        <div>
          <span className="block text-slate-400">Cash</span>
          {formatCurrencyOrMask(netWorth.cash_total, hidden)}
        </div>
        <div>
          <span className="block text-slate-400">Investments</span>
          {formatCurrencyOrMask(netWorth.investments_total, hidden)}
        </div>
      </div>
    </Card>
  );
}
