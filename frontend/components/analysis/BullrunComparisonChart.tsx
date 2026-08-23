"use client";

import { useState, useEffect } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine } from "recharts";

// Generiert realistische tägliche Preisdaten mit Volatilität
function generateDailyPrices(
  startPrice: number,
  endPrice: number,
  days: number,
  volatility: number = 0.03
): number[] {
  const prices: number[] = [];
  let currentPrice = startPrice;
  const logReturn = Math.log(endPrice / startPrice) / days;

  // Grenzen basierend auf Start und End Preis
  const isUptrend = endPrice >= startPrice;
  const minPrice = Math.min(startPrice, endPrice) * 0.9;
  const maxPrice = Math.max(startPrice, endPrice) * 1.05; // Max 5% über dem höchsten Preis

  for (let i = 0; i <= days; i++) {
    // Volatilität wird begrenzt, damit sie den Trend nicht komplett umkehrt
    // Max 40% des logReturn
    const maxRandomWalk = Math.abs(logReturn) * 0.4;
    const randomWalk = (Math.random() - 0.5) * 2 * Math.min(volatility, maxRandomWalk);
    currentPrice = currentPrice * Math.exp(logReturn + randomWalk);

    // Grenzen einhalten
    currentPrice = Math.max(minPrice, Math.min(maxPrice, currentPrice));
    prices.push(currentPrice);
  }

  // Letzter Preis = Endpreis
  prices[days] = endPrice;
  return prices;
}

interface BullrunData {
  name: string;
  color: string;
  lowDate1: string;
  athDate: string;
  lowDate2: string;
  lowPrice1: number;
  athPrice: number;
  lowPrice2: number;
  bullrunDays: number;
  totalCycleDays: number;
  data: Array<{ day: number; price: number }>;
}

// Bitcoin Bullrun Zyklen: Von Low zu Low (Bullrun + anschließender Crash)
const generateBullruns = (): BullrunData[] => {
  const bullruns: BullrunData[] = [
    {
      name: "Zyklus 1",
      color: "#8b5cf6",
      lowDate1: "06/2010",
      athDate: "11/2013",
      lowDate2: "01/2015",
      lowPrice1: 0.01,
      athPrice: 1000,
      lowPrice2: 165,
      bullrunDays: 1249, // Jun 2010 → Nov 2013
      totalCycleDays: 1674, // Jun 2010 → Jan 2015 (gesamter Zyklus)
      data: [],
    },
    {
      name: "Zyklus 2",
      color: "#3b82f6",
      lowDate1: "01/2015",
      athDate: "12/2017",
      lowDate2: "12/2018",
      lowPrice1: 165,
      athPrice: 19000,
      lowPrice2: 3600,
      bullrunDays: 1431, // Jan 2015 → Dez 2017
      totalCycleDays: 1430, // Jan 2015 → Dez 2018
      data: [],
    },
    {
      name: "Zyklus 3",
      color: "#10b981",
      lowDate1: "12/2018",
      athDate: "11/2021",
      lowDate2: "06/2022",
      lowPrice1: 3600,
      athPrice: 69000,
      lowPrice2: 19000,
      bullrunDays: 1065, // Dez 2018 → Nov 2021
      totalCycleDays: 1277, // Dez 2018 → Jun 2022
      data: [],
    },
    {
      name: "Zyklus 4",
      color: "#f59e0b",
      lowDate1: "06/2022",
      athDate: "12/2024",
      lowDate2: "08/2026",
      lowPrice1: 16500,
      athPrice: 126000,
      lowPrice2: 76000, // Aktueller Preis (noch nicht am Low)
      bullrunDays: 906, // Jun 2022 → Dez 2024
      totalCycleDays: 1151, // Jun 2022 → Aug 2026
      data: [],
    },
  ];

  // Generiere tägliche Daten für jeden Zyklus (Low zu Low)
  bullruns.forEach((bullrun) => {
    // Bullrun-Phase (Low1 → ATH)
    const bullrunPrices = generateDailyPrices(
      bullrun.lowPrice1,
      bullrun.athPrice,
      bullrun.bullrunDays,
      0.06 // Erhöht von 0.04 auf 0.06 für mehr Volatilität
    );

    for (let day = 1; day <= bullrun.bullrunDays; day++) {
      bullrun.data.push({
        day,
        price: bullrunPrices[day - 1],
      });
    }

    // Crash-Phase (ATH → Low2), nur wenn nicht der aktuelle Zyklus
    if (bullrun.totalCycleDays > bullrun.bullrunDays) {
      const crashDays = bullrun.totalCycleDays - bullrun.bullrunDays;
      const crashPrices = generateDailyPrices(
        bullrun.athPrice,
        bullrun.lowPrice2,
        crashDays,
        0.07 // Erhöht von 0.05 auf 0.07 für mehr Volatilität
      );

      for (let day = 1; day <= crashDays; day++) {
        bullrun.data.push({
          day: bullrun.bullrunDays + day,
          price: crashPrices[day - 1],
        });
      }
    }
  });

  return bullruns;
};

const BULLRUNS = generateBullruns();

const CURRENT_DAY = 637; // Aktueller Stand im Zyklus 4

export function BullrunComparisonChart() {
  const [visibleCycles, setVisibleCycles] = useState<Record<string, boolean>>({
    "Zyklus 1": false,
    "Zyklus 2": false,
    "Zyklus 3": false,
    "Zyklus 4": true,
  });

  const [historicalPrices, setHistoricalPrices] = useState<Array<{ date: string; price: number }>>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Lade historische Bitcoin-Preise vom Backend
  useEffect(() => {
    const fetchPrices = async () => {
      try {
        // Lade alle Preise ab Juni 2022 (Start des aktuellen Zyklus)
        const response = await fetch('/api/bitcoin-history/prices?start_date=2022-06-01');
        const data = await response.json();

        if (data.prices) {
          setHistoricalPrices(data.prices);
        }
      } catch (error) {
        console.error('Failed to fetch bitcoin price history:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchPrices();
  }, []);

  // Find longest cycle to determine x-axis length
  const maxDays = Math.max(...BULLRUNS.map(r => r.data.length));

  // Create data points for all days with daily prices
  const allData = [];

  // Erstelle jeden Tag separat mit allen verfügbaren Daten
  for (let day = 1; day <= maxDays; day++) {
    const dataPoint: any = {
      day,
      dayLabel: `Tag ${day}`,
    };

    // For each cycle, get the price for this day if available
    BULLRUNS.forEach((bullrun) => {
      const cycleName = bullrun.name;
      if (day <= bullrun.data.length) {
        const dayData = bullrun.data[day - 1];
        dataPoint[cycleName] = dayData.price;
      }
    });

    allData.push(dataPoint);
  }

  // Handle legend click to toggle visibility
  const handleLegendClick = (e: any) => {
    const newVisible = { ...visibleCycles };
    if (newVisible.hasOwnProperty(e.dataKey)) {
      newVisible[e.dataKey] = !newVisible[e.dataKey];
      setVisibleCycles(newVisible);
    }
  };

  return (
    <div className="space-y-6">
      <div className="w-full h-screen">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={allData} margin={{ top: 5, right: 30, left: 60, bottom: 50 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="dayLabel"
              tick={{ fontSize: 11 }}
              angle={-45}
              textAnchor="end"
              height={100}
              label={{ value: "Tage im Bullrun-Zyklus", position: "bottom", offset: 20 }}
              interval={Math.ceil(maxDays / 20)}
            />
            <YAxis
              scale="log"
              domain={[0.01, 100000]}
              label={{ value: "Preis in USD (logarithmisch)", angle: -90, position: "insideLeft" }}
              tickFormatter={(value) => `$${value.toLocaleString('en-US', { notation: 'compact', compactDisplay: 'short' })}`}
            />
            <Tooltip
              formatter={(value) => {
                if (typeof value === 'number') {
                  return `$${value.toLocaleString('en-US', { maximumFractionDigits: 2 })}`;
                }
                return value;
              }}
              labelFormatter={(label) => `${label}`}
              contentStyle={{ backgroundColor: "rgba(255, 255, 255, 0.95)", border: "1px solid #ccc" }}
            />
            <Legend
              layout="vertical"
              align="right"
              verticalAlign="middle"
              wrapperStyle={{ paddingLeft: "20px", cursor: "pointer" }}
              onClick={handleLegendClick}
            />
            <Line
              type="monotone"
              dataKey={BULLRUNS[0].name}
              stroke={BULLRUNS[0].color}
              dot={false}
              strokeWidth={2}
              connectNulls={true}
              isAnimationActive={false}
              hide={!visibleCycles[BULLRUNS[0].name]}
            />
            <Line
              type="monotone"
              dataKey={BULLRUNS[1].name}
              stroke={BULLRUNS[1].color}
              dot={false}
              strokeWidth={2}
              connectNulls={true}
              isAnimationActive={false}
              hide={!visibleCycles[BULLRUNS[1].name]}
            />
            <Line
              type="monotone"
              dataKey={BULLRUNS[2].name}
              stroke={BULLRUNS[2].color}
              dot={false}
              strokeWidth={2}
              connectNulls={true}
              isAnimationActive={false}
              hide={!visibleCycles[BULLRUNS[2].name]}
            />
            <Line
              type="monotone"
              dataKey={BULLRUNS[3].name}
              stroke={BULLRUNS[3].color}
              dot={false}
              strokeWidth={3}
              strokeDasharray="5 5"
              connectNulls={true}
              isAnimationActive={false}
              hide={!visibleCycles[BULLRUNS[3].name]}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {BULLRUNS.map((bullrun) => (
          <div key={bullrun.name} className="p-4 border rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: bullrun.color }} />
              <span className="font-semibold text-sm">{bullrun.name} - Low zu Low</span>
            </div>
            <div className="text-xs text-slate-600 mb-2">
              <div><strong>Bullrun:</strong> {bullrun.lowDate1} → {bullrun.athDate}</div>
              <div className="text-slate-500">${bullrun.lowPrice1.toLocaleString()} → ${bullrun.athPrice.toLocaleString()}</div>
              <div className="text-slate-500 font-semibold">{bullrun.bullrunDays} Tage Bullrun</div>
              <div className="mt-2 pt-2 border-t"><strong>Gesamtzyklus:</strong> {bullrun.lowDate1} → {bullrun.lowDate2}</div>
              <div className="text-slate-500">${bullrun.lowPrice1.toLocaleString()} → ${bullrun.lowPrice2.toLocaleString()}</div>
              <div className="text-slate-500">{bullrun.totalCycleDays} Tage gesamt</div>
            </div>
            <div className="h-32">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={bullrun.data}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="dayLabel"
                    tick={{ fontSize: 10 }}
                    interval={Math.floor(bullrun.data.length / 4)}
                  />
                  <YAxis hide domain={[0, 100]} />
                  <Tooltip
                    formatter={(value) => `${value?.toFixed(1)}%`}
                    labelFormatter={(label) => `${label}`}
                  />
                  <Line
                    type="monotone"
                    dataKey="normalized"
                    stroke={bullrun.color}
                    dot={false}
                    isAnimationActive={false}
                    strokeWidth={2}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        ))}
      </div>

      <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
        <h3 className="font-semibold text-sm text-amber-900 mb-2">💡 Analyse</h3>
        <ul className="text-xs text-amber-800 space-y-1">
          <li>• <strong>Zyklus 1:</strong> 1.249 Tage (Tiefpunkt Juni 2010 → ATH November 2013)</li>
          <li>• <strong>Zyklus 2:</strong> 1.431 Tage (Tiefpunkt Januar 2015 → ATH Dezember 2017)</li>
          <li>• <strong>Zyklus 3:</strong> 1.065 Tage (Tiefpunkt Dezember 2018 → ATH November 2021)</li>
          <li>• <strong>Zyklus 4:</strong> 637 Tage bis ATH März 2024 (Aktuell: ~100% vom bisherigen ATH erreicht)</li>
          <li>• ⚠️ Die Zyklen werden kürzer - dies ist keine Finanzberatung</li>
        </ul>
      </div>
    </div>
  );
}
