"use client";

import { useDashboard } from "@/lib/queries/useDashboard";
import { useNetWorthHistory } from "@/lib/queries/useFinancials";
import { useScoreHistory } from "@/lib/queries/useScore";
import { NetWorthCard } from "@/components/dashboard/NetWorthCard";
import { BtcPriceCard } from "@/components/dashboard/BtcPriceCard";
import { FearGreedGauge } from "@/components/dashboard/FearGreedGauge";
import { ScoreCard } from "@/components/dashboard/ScoreCard";
import { PortfolioAllocationChart } from "@/components/dashboard/PortfolioAllocationChart";
import { CryptoBreakdownChart } from "@/components/dashboard/CryptoBreakdownChart";
import { NetWorthHistoryChart } from "@/components/charts/NetWorthHistoryChart";
import { ScoreHistoryChart } from "@/components/charts/ScoreHistoryChart";

export default function DashboardPage() {
  const dashboard = useDashboard();
  const netWorthHistory = useNetWorthHistory();
  const scoreHistory = useScoreHistory();

  if (dashboard.isLoading) {
    return <p className="text-sm text-slate-500">Lade Dashboard…</p>;
  }

  if (dashboard.isError || !dashboard.data) {
    return <p className="text-sm text-red-600">Dashboard konnte nicht geladen werden.</p>;
  }

  const { net_worth, net_worth_change_30d, portfolio, crypto_breakdown, market, score } = dashboard.data;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        <NetWorthCard netWorth={net_worth} change={net_worth_change_30d} />
        <BtcPriceCard btc={market.btc} />
        <FearGreedGauge fearGreed={market.fear_greed} />
        <ScoreCard score={score} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <PortfolioAllocationChart portfolio={portfolio} />
        <NetWorthHistoryChart history={netWorthHistory.data ?? []} />
      </div>

      <CryptoBreakdownChart cryptoBreakdown={crypto_breakdown} />

      <ScoreHistoryChart history={scoreHistory.data ?? []} />
    </div>
  );
}
