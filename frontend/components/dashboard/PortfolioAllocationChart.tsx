"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import { formatCurrencyOrMask } from "@/lib/format";
import { usePrivacyMode } from "@/lib/privacy-context";
import type { PortfolioAllocation } from "@/lib/types";
import { Card, CardTitle } from "@/components/ui/Card";

const COLORS: Record<string, string> = {
  cash: "#94a3b8",
  btc: "#f59e0b",
  crypto: "#a855f7",
  stocks: "#3b82f6",
  etf: "#10b981",
  other: "#64748b",
};

export function PortfolioAllocationChart({ portfolio }: { portfolio: PortfolioAllocation | null }) {
  const { hidden } = usePrivacyMode();

  if (!portfolio || portfolio.breakdown.length === 0) {
    return (
      <Card>
        <CardTitle>Portfolio-Allokation</CardTitle>
        <p className="mt-2 text-sm text-slate-500">Noch keine Vermögenswerte erfasst.</p>
      </Card>
    );
  }

  const data = portfolio.breakdown.map((item) => ({
    name: item.subcategory,
    value: Number(item.amount),
    percent: item.percent_of_total,
  }));

  return (
    <Card>
      <CardTitle>Portfolio-Allokation</CardTitle>
      <div className="mt-2 flex items-center gap-4">
        <div className="h-40 w-40 shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={data} dataKey="value" nameKey="name" innerRadius={35} outerRadius={70} paddingAngle={2}>
                {data.map((entry) => (
                  <Cell key={entry.name} fill={COLORS[entry.name] ?? "#cbd5e1"} />
                ))}
              </Pie>
              <Tooltip formatter={(value) => formatCurrencyOrMask(Number(value), hidden)} />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <ul className="flex-1 space-y-1.5 text-xs">
          {data.map((entry) => (
            <li key={entry.name} className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-1.5 capitalize text-slate-600">
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: COLORS[entry.name] ?? "#cbd5e1" }} />
                {entry.name}
              </span>
              <span className="text-right">
                <span className="block text-slate-700">{formatCurrencyOrMask(entry.value, hidden)}</span>
                <span className="block text-slate-400">{entry.percent.toFixed(1)}%</span>
              </span>
            </li>
          ))}
        </ul>
      </div>
      <p className="mt-3 text-xs text-slate-400">
        BTC-Anteil am Portfolio: {portfolio.btc_percent_of_assets.toFixed(1)}%
      </p>
    </Card>
  );
}
