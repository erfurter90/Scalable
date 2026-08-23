"use client";

import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";
import type { BtcDominance } from "@/lib/types";
import { Card, CardTitle } from "@/components/ui/Card";

export function BtcDominanceCard({ btcDominance }: { btcDominance: BtcDominance }) {
  if (!btcDominance.dominance || btcDominance.dominance.status !== "ok" || btcDominance.dominance.value === null) {
    return null;
  }

  const dominancePercent = Number(btcDominance.dominance.value);
  const otherPercent = 100 - dominancePercent;

  const data = [
    { name: "BTC", value: dominancePercent },
    { name: "Others", value: otherPercent },
  ];

  return (
    <Card>
      <CardTitle>BTC-Dominanz</CardTitle>
      <div className="mt-4 flex items-center gap-6">
        <div className="h-40 w-40 shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                dataKey="value"
                nameKey="name"
                innerRadius={50}
                outerRadius={70}
                startAngle={90}
                endAngle={-270}
              >
                <Cell fill="#3b82f6" />
                <Cell fill="#cbd5e1" />
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="flex-1">
          <div className="mb-4">
            <div className="text-3xl font-bold text-blue-600">{dominancePercent.toFixed(1)}%</div>
            <p className="text-sm text-slate-600">Marktkapitalisierung</p>
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-blue-600" />
                Bitcoin
              </span>
              <span className="text-slate-700">{dominancePercent.toFixed(1)}%</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-slate-300" />
                Andere Coins
              </span>
              <span className="text-slate-700">{otherPercent.toFixed(1)}%</span>
            </div>
          </div>
        </div>
      </div>
      <p className="mt-3 text-xs text-slate-400">
        Der Prozentsatz der gesamten Kryptowährungsmarktkapitalisierung, die Bitcoin ausmacht.
      </p>
    </Card>
  );
}
