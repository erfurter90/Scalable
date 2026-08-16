import type { DataPointStatus } from "@/lib/types";

const STYLES: Record<DataPointStatus, string> = {
  ok: "bg-emerald-50 text-emerald-700",
  unavailable: "bg-slate-100 text-slate-500",
  error: "bg-amber-50 text-amber-700",
};

const LABELS: Record<DataPointStatus, string> = {
  ok: "aktuell",
  unavailable: "nicht verfügbar",
  error: "Fehler",
};

// The one shared component every place a metric can be missing renders through — the app
// never shows a blank or fabricated value, only a real number or this honest badge.
export function StatusBadge({ status }: { status: DataPointStatus }) {
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${STYLES[status]}`}>
      {LABELS[status]}
    </span>
  );
}
