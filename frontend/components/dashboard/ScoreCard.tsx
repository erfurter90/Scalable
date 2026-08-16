import type { Score } from "@/lib/types";
import { Card, CardTitle } from "@/components/ui/Card";

export function ScoreCard({ score }: { score: Score }) {
  return (
    <Card>
      <CardTitle>BTC Investment Score</CardTitle>
      {score.total_score !== null ? (
        <>
          <p className="mt-1 text-2xl font-semibold">{score.total_score.toFixed(0)} / 100</p>
          <p className="text-xs text-slate-400">Gewichtungs-Version {score.weights_config_version}</p>
        </>
      ) : (
        <p className="mt-2 text-sm text-slate-500">Score derzeit nicht berechenbar (keine Daten verfügbar).</p>
      )}
      <div className="mt-3 space-y-1.5">
        {score.subscores.map((sub) => (
          <div key={sub.name} className="flex items-center gap-2 text-xs">
            <span className="w-20 shrink-0 capitalize text-slate-500">{sub.name}</span>
            {sub.status === "ok" && sub.value !== null ? (
              <>
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
                  <div className="h-full rounded-full bg-slate-900" style={{ width: `${sub.value}%` }} />
                </div>
                <span className="w-8 text-right text-slate-500">{sub.value.toFixed(0)}</span>
              </>
            ) : (
              <span className="text-slate-400">nicht verfügbar</span>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}
