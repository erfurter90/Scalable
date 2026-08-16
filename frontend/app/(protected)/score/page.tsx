"use client";

import { useCurrentScore, useScoreHistory } from "@/lib/queries/useScore";
import { ScoreCard } from "@/components/dashboard/ScoreCard";
import { ScoreHistoryChart } from "@/components/charts/ScoreHistoryChart";
import { Card } from "@/components/ui/Card";

export default function ScorePage() {
  const current = useCurrentScore();
  const history = useScoreHistory();

  if (current.isLoading) {
    return <p className="text-sm text-slate-500">Lade Score…</p>;
  }

  if (current.isError || !current.data) {
    return <p className="text-sm text-red-600">Score konnte nicht geladen werden.</p>;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold">BTC Investment Score</h1>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ScoreCard score={current.data} />
        <ScoreHistoryChart history={history.data ?? []} />
      </div>

      <Card>
        <h2 className="mb-3 text-sm font-medium text-slate-500">Details je Teilbereich</h2>
        <div className="space-y-4">
          {current.data.subscores.map((sub) => (
            <div key={sub.name} className="border-b border-slate-100 pb-3 last:border-0 last:pb-0">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium capitalize">{sub.name}</span>
                <span className="text-xs text-slate-400">
                  Gewicht: {(sub.weight_declared * 100).toFixed(0)}%
                  {sub.weight_used !== null && sub.weight_used !== sub.weight_declared
                    ? ` (renormiert: ${(sub.weight_used * 100).toFixed(0)}%)`
                    : ""}
                </span>
              </div>
              {sub.status === "ok" ? (
                <>
                  <p className="text-sm text-slate-600">Wert: {sub.value?.toFixed(1)} / 100</p>
                  <pre className="mt-1 overflow-x-auto rounded-lg bg-slate-50 p-2 text-xs text-slate-500">
                    {JSON.stringify(sub.inputs, null, 2)}
                  </pre>
                </>
              ) : (
                <p className="text-sm text-slate-400">{sub.unavailable_reason}</p>
              )}
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
