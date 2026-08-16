"use client";

import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { formatCurrency, formatDate } from "@/lib/format";
import type { NetWorthSnapshot } from "@/lib/types";
import { Card, CardTitle } from "@/components/ui/Card";

export function NetWorthHistoryChart({ history }: { history: NetWorthSnapshot[] }) {
  if (history.length < 2) {
    return (
      <Card>
        <CardTitle>Vermögensentwicklung</CardTitle>
        <p className="mt-2 text-sm text-slate-500">
          Noch nicht genug historische Daten für einen Chart — erfasse deine Finanzdaten über mehrere Tage.
        </p>
      </Card>
    );
  }

  const data = history.map((snapshot) => ({
    date: snapshot.snapshot_date,
    net_worth: Number(snapshot.net_worth),
  }));

  return (
    <Card>
      <CardTitle>Vermögensentwicklung</CardTitle>
      <div className="mt-3 h-56">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              <linearGradient id="netWorthGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#0f172a" stopOpacity={0.25} />
                <stop offset="100%" stopColor="#0f172a" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="date" tickFormatter={formatDate} tick={{ fontSize: 11 }} minTickGap={30} />
            <YAxis tick={{ fontSize: 11 }} width={70} tickFormatter={(v) => formatCurrency(v)} />
            <Tooltip labelFormatter={(label) => formatDate(String(label))} formatter={(value) => formatCurrency(Number(value))} />
            <Area type="monotone" dataKey="net_worth" stroke="#0f172a" fill="url(#netWorthGradient)" strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
