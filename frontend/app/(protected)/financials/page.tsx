"use client";

import { useState } from "react";

import { useFinancialEntries } from "@/lib/queries/useFinancials";
import type { FinancialEntry } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { BitvavoSyncCard } from "@/components/financials/BitvavoSyncCard";
import { EntryTable } from "@/components/financials/EntryTable";
import { EntryFormModal } from "@/components/financials/EntryFormModal";
import { PurchaseModal } from "@/components/financials/PurchaseModal";

export default function FinancialsPage() {
  const entries = useFinancialEntries();
  const [modalState, setModalState] = useState<{ open: boolean; entry: FinancialEntry | null }>({
    open: false,
    entry: null,
  });
  const [purchaseEntry, setPurchaseEntry] = useState<FinancialEntry | null>(null);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">Finanzdaten</h1>
        <Button onClick={() => setModalState({ open: true, entry: null })}>+ Neuer Eintrag</Button>
      </div>

      <BitvavoSyncCard />

      <Card>
        {entries.isLoading ? (
          <p className="text-sm text-slate-500">Lade Einträge…</p>
        ) : entries.isError ? (
          <p className="text-sm text-red-600">Einträge konnten nicht geladen werden.</p>
        ) : (
          <EntryTable
            entries={entries.data ?? []}
            onEdit={(entry) => setModalState({ open: true, entry })}
            onAddPurchase={(entry) => setPurchaseEntry(entry)}
          />
        )}
      </Card>

      {modalState.open && (
        <EntryFormModal entry={modalState.entry} onClose={() => setModalState({ open: false, entry: null })} />
      )}

      {purchaseEntry && <PurchaseModal entry={purchaseEntry} onClose={() => setPurchaseEntry(null)} />}
    </div>
  );
}
