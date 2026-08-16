import type { FearGreed } from "@/lib/types";
import { Card, CardTitle } from "@/components/ui/Card";
import { StatusBadge } from "@/components/ui/StatusBadge";

function classify(value: number): string {
  if (value <= 24) return "Extreme Angst";
  if (value <= 44) return "Angst";
  if (value <= 55) return "Neutral";
  if (value <= 75) return "Gier";
  return "Extreme Gier";
}

export function FearGreedGauge({ fearGreed }: { fearGreed: FearGreed }) {
  const { index } = fearGreed;

  return (
    <Card>
      <div className="flex items-center justify-between">
        <CardTitle>Fear &amp; Greed Index</CardTitle>
        <StatusBadge status={index.status} />
      </div>
      {index.status === "ok" && index.value !== null ? (
        <>
          <p className="mt-1 text-2xl font-semibold">{index.value.toFixed(0)}</p>
          <p className="text-sm text-slate-500">{classify(index.value)}</p>
          <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-gradient-to-r from-red-500 via-amber-400 to-emerald-500"
              style={{ width: `${index.value}%` }}
            />
          </div>
        </>
      ) : (
        <p className="mt-2 text-sm text-slate-500">Index derzeit nicht verfügbar.</p>
      )}
    </Card>
  );
}
