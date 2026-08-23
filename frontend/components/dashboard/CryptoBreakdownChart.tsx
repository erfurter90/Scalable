"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import { coinTicker } from "@/lib/coins";
import { formatCurrencyOrMask } from "@/lib/format";
import { usePrivacyMode } from "@/lib/privacy-context";
import type { CryptoBreakdown } from "@/lib/types";
import { Card, CardTitle } from "@/components/ui/Card";

// Coins are open-ended (unlike the fixed cash/btc/crypto/stocks/etf/other set), so colors are
// assigned by position in a cycling palette rather than a fixed per-key map.
const PALETTE = ["#a855f7", "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#06b6d4", "#ec4899", "#84cc16"];

export function CryptoBreakdownChart({ cryptoBreakdown }: { cryptoBreakdown: CryptoBreakdown | null }) {
  const { hidden } = usePrivacyMode();

  // Only worth its own chart once there's more than one coin to actually break down — a
  // single slice would just repeat what the main allocation chart already shows.
  if (!cryptoBreakdown || cryptoBreakdown.breakdown.length < 2) {
    return null;
  }

  const data = cryptoBreakdown.breakdown.map((item) => ({
    name: coinTicker(item.coin),
    value: Number(item.amount),
    percent: item.percent_of_crypto,
  }));

  return (
    <Card>
      <CardTitle>Krypto-Allokation im Detail</CardTitle>
      <div className="mt-2 flex items-center gap-4">
        <div className="h-40 w-40 shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={data} dataKey="value" nameKey="name" innerRadius={35} outerRadius={70} paddingAngle={2}>
                {data.map((entry, index) => (
                  <Cell key={entry.name} fill={PALETTE[index % PALETTE.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(value) => formatCurrencyOrMask(Number(value), hidden)} />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <ul className="flex-1 space-y-1.5 text-xs">
          {data.map((entry, index) => (
            <li key={entry.name} className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-1.5 text-slate-600">
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ backgroundColor: PALETTE[index % PALETTE.length] }}
                />
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
        Anteile innerhalb &quot;Andere Krypto&quot; — kann sich schnell verschieben, unabhängig von der
        Gesamt-Allokation oben.
      </p>
    </Card>
  );
}
