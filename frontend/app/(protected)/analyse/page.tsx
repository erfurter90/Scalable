"use client";

import { Card, CardTitle } from "@/components/ui/Card";
import { CycleAnalysisChart } from "@/components/analysis/CycleAnalysisChart";

export default function AnalysisPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">Analyse</h1>
      </div>

      <Card>
        <CardTitle>Bitcoin Bullrun-Zyklen Analyse</CardTitle>
        <p className="mt-2 text-sm text-slate-600">
          Echte historische Bitcoin-Preise mit automatischer Zyklus-Erkennung. Jeder Zyklus beginnt beim ersten Wert und endet beim nächsten Tiefpunkt nach einem Allzeithoch. Klicke auf die Legende oder die Karten, um Zyklen ein-/auszublenden.
        </p>
        <div className="mt-6">
          <CycleAnalysisChart />
        </div>
      </Card>

      <Card>
        <CardTitle>Halving-Zyklen Übersicht</CardTitle>
        <div className="mt-4 space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-3 bg-slate-50 rounded">
              <div className="text-sm font-semibold text-slate-700">2012 Halving</div>
              <div className="text-xs text-slate-600 mt-1">Nov 2012 - Nov 2013</div>
              <div className="text-xs text-slate-500 mt-1">Bullrun: ~1 Jahr</div>
            </div>
            <div className="p-3 bg-slate-50 rounded">
              <div className="text-sm font-semibold text-slate-700">2016 Halving</div>
              <div className="text-xs text-slate-600 mt-1">Jul 2016 - Jan 2018</div>
              <div className="text-xs text-slate-500 mt-1">Bullrun: ~1.5 Jahre</div>
            </div>
            <div className="p-3 bg-slate-50 rounded">
              <div className="text-sm font-semibold text-slate-700">2020 Halving</div>
              <div className="text-xs text-slate-600 mt-1">Mai 2020 - Nov 2021</div>
              <div className="text-xs text-slate-500 mt-1">Bullrun: ~1.5 Jahre</div>
            </div>
            <div className="p-3 bg-blue-50 rounded border border-blue-200">
              <div className="text-sm font-semibold text-blue-700">2024 Halving</div>
              <div className="text-xs text-blue-600 mt-1">Apr 2024 - ?</div>
              <div className="text-xs text-blue-500 mt-1 font-semibold">Aktueller Zyklus</div>
            </div>
          </div>
        </div>
        <p className="mt-4 text-xs text-slate-400">
          Basierend auf historischen Daten und der Annahme ähnlicher Zyklus-Längen.
        </p>
      </Card>
    </div>
  );
}
