"use client";

import { useDashboard } from "@/lib/queries/useDashboard";
import { useNetWorthHistory } from "@/lib/queries/useFinancials";
import { usePrivacyMode, PrivacyModeProvider } from "@/lib/privacy-context";
import { useScoreHistory } from "@/lib/queries/useScore";
import { Button } from "@/components/ui/Button";
import { NetWorthCard } from "@/components/dashboard/NetWorthCard";
import { RecentTransactionsCard } from "@/components/dashboard/RecentTransactionsCard";
import { BtcPriceCard } from "@/components/dashboard/BtcPriceCard";
import { BtcDominanceCard } from "@/components/dashboard/BtcDominanceCard";
import { FearGreedGauge } from "@/components/dashboard/FearGreedGauge";
import { ScoreCard } from "@/components/dashboard/ScoreCard";
import { PortfolioAllocationChart } from "@/components/dashboard/PortfolioAllocationChart";
import { CryptoBreakdownChart } from "@/components/dashboard/CryptoBreakdownChart";
import { NetWorthHistoryChart } from "@/components/charts/NetWorthHistoryChart";
import { ScoreHistoryChart } from "@/components/charts/ScoreHistoryChart";

export default function DashboardPage() {
  return (
    <PrivacyModeProvider>
      <DashboardContent />
    </PrivacyModeProvider>
  );
}

function DashboardContent() {
  const dashboard = useDashboard();
  const netWorthHistory = useNetWorthHistory();
  const scoreHistory = useScoreHistory();
  const { hidden, toggle } = usePrivacyMode();

  if (dashboard.isLoading) {
    return <p className="text-sm text-slate-500">Lade Dashboard…</p>;
  }

  if (dashboard.isError || !dashboard.data) {
    return <p className="text-sm text-red-600">Dashboard konnte nicht geladen werden.</p>;
  }

  const { net_worth, net_worth_change_30d, portfolio, crypto_breakdown, market, score } = dashboard.data;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">Dashboard</h1>
        <Button variant="secondary" onClick={toggle}>
          {hidden ? "Beträge anzeigen" : "Beträge verbergen"}
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        <NetWorthCard netWorth={net_worth} change={net_worth_change_30d} />
        <BtcPriceCard btc={market.btc} />
        <FearGreedGauge fearGreed={market.fear_greed} />
        <ScoreCard score={score} />
      </div>

      <RecentTransactionsCard />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <PortfolioAllocationChart portfolio={portfolio} />
        <NetWorthHistoryChart history={netWorthHistory.data ?? []} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <CryptoBreakdownChart cryptoBreakdown={crypto_breakdown} />
        <BtcDominanceCard btcDominance={market.btc_dominance} />
      </div>

      <ScoreHistoryChart history={scoreHistory.data ?? []} />
    </div>
  );
}
