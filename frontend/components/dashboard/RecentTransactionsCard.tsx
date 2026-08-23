"use client";

import { formatCurrencyOrMask, formatDateTime } from "@/lib/format";
import { usePrivacyMode } from "@/lib/privacy-context";
import { useRecentTransactions } from "@/lib/queries/useTransactions";
import { Card, CardTitle } from "@/components/ui/Card";

export function RecentTransactionsCard() {
  const transactions = useRecentTransactions();
  const { hidden } = usePrivacyMode();

  if (transactions.isLoading || (transactions.data && transactions.data.length === 0)) {
    return null;
  }

  if (transactions.isError) {
    return (
      <Card>
        <CardTitle>Letzte Transaktionen</CardTitle>
        <p className="mt-3 text-sm text-red-600">Transaktionen konnten nicht geladen werden.</p>
      </Card>
    );
  }

  return (
    <Card>
      <CardTitle>Letzte Transaktionen</CardTitle>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 text-left text-xs text-slate-400">
              <th className="pb-2 pr-4 font-medium">Börse</th>
              <th className="pb-2 pr-4 font-medium">Asset</th>
              <th className="pb-2 pr-4 font-medium">Anschaffungskosten</th>
              <th className="pb-2 pr-4 font-medium">Preis/Coin</th>
              <th className="pb-2 font-medium">Zeitpunkt</th>
            </tr>
          </thead>
          <tbody>
            {transactions.data!.map((txn, index) => (
              <tr key={index} className="border-b border-slate-50 last:border-0">
                <td className="py-2 pr-4 text-slate-600">{txn.source}</td>
                <td className="py-2 pr-4 font-medium">{txn.asset}</td>
                <td className="py-2 pr-4 text-slate-600">
                  {txn.total_cost ? formatCurrencyOrMask(txn.total_cost, hidden) : "–"}
                </td>
                <td className="py-2 pr-4 text-slate-600">
                  {txn.price ? formatCurrencyOrMask(txn.price, hidden) : "–"}
                </td>
                <td className="py-2 text-slate-500">{txn.occurred_at ? formatDateTime(txn.occurred_at) : "–"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
