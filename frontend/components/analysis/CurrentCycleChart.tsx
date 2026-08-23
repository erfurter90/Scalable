"use client";

import { useState, useEffect } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";

interface PriceData {
  date: string;
  price: number;
}

export function CurrentCycleChart() {
  const [data, setData] = useState<Array<{ day: number; date: string; price: number }>>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [stats, setStats] = useState({
    minPrice: 0,
    maxPrice: 0,
    currentPrice: 0,
    totalDays: 0,
  });

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/bitcoin-history/prices?start_date=2022-06-01');
        const result = await response.json();

        if (result.prices && result.prices.length > 0) {
          // Konvertiere die Preisdaten für das Chart
          const chartData = result.prices.map((item: PriceData, index: number) => ({
            day: index + 1,
            date: item.date,
            price: item.price,
          }));

          setData(chartData);

          // Berechne Statistiken
          const prices = result.prices.map((p: PriceData) => p.price);
          setStats({
            minPrice: Math.min(...prices),
            maxPrice: Math.max(...prices),
            currentPrice: prices[prices.length - 1],
            totalDays: result.prices.length,
          });
        }
      } catch (error) {
        console.error('Failed to fetch bitcoin price history:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, []);

  if (isLoading) {
    return (
      <div className="w-full h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-slate-600">Lade Bitcoin-Preishistorie...</p>
        </div>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="w-full h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600">Fehler beim Laden der Preisdaten</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Chart */}
      <div className="w-full h-screen bg-white rounded-lg border border-slate-200 p-6">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 5, right: 30, left: 60, bottom: 50 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11 }}
              angle={-45}
              textAnchor="end"
              height={100}
              label={{ value: "Datum", position: "bottom", offset: 20 }}
              interval={Math.floor(data.length / 20)}
            />
            <YAxis
              scale="log"
              domain={[10000, 200000]}
              label={{ value: "Preis in USD (logarithmisch)", angle: -90, position: "insideLeft" }}
              tickFormatter={(value) => `$${(value / 1000).toFixed(0)}K`}
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
            <Legend />
            <Line
              type="monotone"
              dataKey="price"
              stroke="#f59e0b"
              dot={false}
              strokeWidth={2}
              connectNulls={true}
              isAnimationActive={false}
              name="Bitcoin Preis"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Statistiken */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 bg-slate-50 rounded-lg border border-slate-200">
          <p className="text-sm text-slate-600 mb-1">Minimum</p>
          <p className="text-lg font-semibold text-slate-900">
            ${stats.minPrice.toLocaleString('en-US', { maximumFractionDigits: 0 })}
          </p>
        </div>
        <div className="p-4 bg-slate-50 rounded-lg border border-slate-200">
          <p className="text-sm text-slate-600 mb-1">Maximum (ATH)</p>
          <p className="text-lg font-semibold text-green-600">
            ${stats.maxPrice.toLocaleString('en-US', { maximumFractionDigits: 0 })}
          </p>
        </div>
        <div className="p-4 bg-slate-50 rounded-lg border border-slate-200">
          <p className="text-sm text-slate-600 mb-1">Aktuell</p>
          <p className="text-lg font-semibold text-slate-900">
            ${stats.currentPrice.toLocaleString('en-US', { maximumFractionDigits: 0 })}
          </p>
        </div>
        <div className="p-4 bg-slate-50 rounded-lg border border-slate-200">
          <p className="text-sm text-slate-600 mb-1">Tage</p>
          <p className="text-lg font-semibold text-slate-900">
            {stats.totalDays}
          </p>
        </div>
      </div>

      {/* Info */}
      <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
        <h3 className="font-semibold text-blue-900 mb-2">Aktueller Bullrun-Zyklus</h3>
        <p className="text-sm text-blue-800">
          Echte historische Bitcoin-Preise von Juni 2022 bis August 2026.
          Zeigt den kompletten Verlauf vom Low über das Allzeithoch bis zur aktuellen Position.
        </p>
      </div>
    </div>
  );
}
