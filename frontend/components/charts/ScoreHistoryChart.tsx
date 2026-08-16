"use client";

import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { formatDate } from "@/lib/format";
import type { Score } from "@/lib/types";
import { Card, CardTitle } from "@/components/ui/Card";

export function ScoreHistoryChart({ history }: { history: Score[] }) {
  const data = history
    .filter((entry) => entry.total_score !== null)
    .map((entry) => ({ date: entry.score_date, score: entry.total_score as number }));

  if (data.length < 2) {
    return (
      <Card>
        <CardTitle>Score-Verlauf</CardTitle>
        <p className="mt-2 text-sm text-slate-500">Noch nicht genug Score-Historie für einen Chart.</p>
      </Card>
    );
  }

  return (
    <Card>
      <CardTitle>Score-Verlauf</CardTitle>
      <div className="mt-3 h-56">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <XAxis dataKey="date" tickFormatter={formatDate} tick={{ fontSize: 11 }} minTickGap={30} />
            <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} width={30} />
            <Tooltip labelFormatter={(label) => formatDate(String(label))} />
            <Line type="monotone" dataKey="score" stroke="#f59e0b" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
