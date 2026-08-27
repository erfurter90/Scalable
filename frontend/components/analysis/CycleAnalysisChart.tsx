"use client";

import { useState, useEffect } from "react";
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

interface PriceData {
  date: string;
  price: number;
  volume?: number;
}

interface Cycle {
  id: string;
  label: string;
  startDate: string;
  endDate: string;
  startPrice: number;
  endPrice: number;
  minPrice: number;
  maxPrice: number;
  daysToATH: number;
  daysFromATH: number;
  data: Array<{ day: number; date: string; price: number; volume: number }>;
  color: string;
  localMinPrice: number;
  localMinDate: string;
  localMinDayIndex: number;
  localMaxPrice: number;
  localMaxDate: string;
  localMaxDayIndex: number;
  maxDrawdownPercent: number;
  nearestFibonacciLevel: number;
  drawdownFromPrice: number;
  drawdownToPrice: number;
}

const CYCLE_COLORS = ["#8b5cf6", "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#ec4899", "#14b8a6", "#f97316"];

const formatDate = (dateStr: string): string => {
  const [year, month, day] = dateStr.split('-');
  return `${day}.${month}.${year}`;
};

const FIBONACCI_LEVELS = [23.6, 38.2, 50, 61.8, 78.6];

const getNearestFibonacciLevel = (drawdown: number): number => {
  return FIBONACCI_LEVELS.reduce((prev, curr) =>
    Math.abs(curr - drawdown) < Math.abs(prev - drawdown) ? curr : prev
  );
};

const calculateMaxDrawdown = (prices: number[], localMaxIdx: number): { drawdownPercent: number; nearestFibonacci: number; fromPrice: number; toPrice: number } => {
  if (localMaxIdx === -1 || localMaxIdx >= prices.length - 1) {
    return { drawdownPercent: 0, nearestFibonacci: 0, fromPrice: 0, toPrice: 0 };
  }

  const maxPrice = prices[localMaxIdx];
  let minPrice = maxPrice;

  for (let i = localMaxIdx + 1; i < prices.length; i++) {
    if (prices[i] < minPrice) {
      minPrice = prices[i];
    }
  }

  const drawdownPercent = ((maxPrice - minPrice) / maxPrice) * 100;
  const nearestFibonacci = getNearestFibonacciLevel(drawdownPercent);

  return { drawdownPercent, nearestFibonacci, fromPrice: maxPrice, toPrice: minPrice };
};

const calculateSMA = (prices: number[], period: number): number[] => {
  const sma: number[] = [];
  for (let i = 0; i < prices.length; i++) {
    if (i < period - 1) {
      sma.push(NaN);
    } else {
      let sum = 0;
      for (let j = i - period + 1; j <= i; j++) {
        sum += prices[j];
      }
      sma.push(sum / period);
    }
  }
  return sma;
};

export function CycleAnalysisChart() {
  const [cycles, setCycles] = useState<Cycle[]>([]);
  const [allData, setAllData] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [visibleCycles, setVisibleCycles] = useState<Record<string, boolean>>({});
  const [priceZoom, setPriceZoom] = useState<[number, number] | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [dragStartY, setDragStartY] = useState<number | null>(null);
  const [chartRef, setChartRef] = useState<HTMLDivElement | null>(null);
  const [isLogarithmic, setIsLogarithmic] = useState(true);
  const [visibleMAs, setVisibleMAs] = useState<Record<string, boolean>>({ ma20: true, ma50: true, ma200: true });

  const identifyCycles = (prices: PriceData[]): Cycle[] => {
    const cycles: Cycle[] = [];
    const cycleBoundaries = [
      { start: null, end: "2011-10-20" },
      { start: "2011-10-20", end: "2015-01-14" },
      { start: "2015-01-14", end: "2018-12-15" },
      { start: "2018-12-15", end: "2022-11-21" },
      { start: "2022-11-21", end: null },
    ];

    cycleBoundaries.forEach((boundary, idx) => {
      const cycleNum = idx + 1;
      let startIdx = 0;
      if (boundary.start) {
        startIdx = prices.findIndex(p => p.date === boundary.start);
        if (startIdx === -1) {
          startIdx = prices.findIndex(p => p.date > boundary.start) || 0;
        }
      }

      let endIdx = prices.length - 1;
      if (boundary.end) {
        endIdx = prices.findIndex(p => p.date === boundary.end);
        if (endIdx === -1) {
          const foundIdx = prices.findIndex(p => p.date > boundary.end);
          endIdx = foundIdx > 0 ? foundIdx - 1 : prices.length - 1;
        }
      }

      if (startIdx <= endIdx && startIdx >= 0 && endIdx < prices.length) {
        const cycleData = prices.slice(startIdx, endIdx + 1);

        if (cycleData.length > 0) {
          const startDate = cycleData[0].date;
          const endDate = cycleData[cycleData.length - 1].date;
          const cyclePrices = cycleData.map(p => parseFloat(p.price.toString()));

          const maxPriceIdx = cyclePrices.indexOf(Math.max(...cyclePrices));
          const daysToATH = maxPriceIdx + 1;
          const daysFromATH = cycleData.length - maxPriceIdx;

          const findLocalExtrema = (prices: number[], windowSize: number = 15) => {
            const localMin = { price: Infinity, idx: -1 };
            const localMax = { price: -Infinity, idx: -1 };

            for (let i = windowSize; i < prices.length - windowSize; i++) {
              let isLocalMin = true;
              let isLocalMax = true;

              for (let j = i - windowSize; j <= i + windowSize; j++) {
                if (prices[j] < prices[i]) isLocalMin = false;
                if (prices[j] > prices[i]) isLocalMax = false;
              }

              if (isLocalMin && prices[i] < localMin.price) {
                localMin.price = prices[i];
                localMin.idx = i;
              }
              if (isLocalMax && prices[i] > localMax.price) {
                localMax.price = prices[i];
                localMax.idx = i;
              }
            }

            return { localMin, localMax };
          };

          const extrema = findLocalExtrema(cyclePrices);
          const drawdownData = calculateMaxDrawdown(cyclePrices, extrema.localMax.idx);

          cycles.push({
            id: `cycle-${cycleNum}`,
            label: `${formatDate(startDate)} - ${formatDate(endDate)}`,
            startDate,
            endDate,
            startPrice: cyclePrices[0],
            endPrice: cyclePrices[cyclePrices.length - 1],
            minPrice: Math.min(...cyclePrices),
            maxPrice: Math.max(...cyclePrices),
            daysToATH,
            daysFromATH,
            localMinPrice: extrema.localMin.price,
            localMinDate: extrema.localMin.idx >= 0 ? cycleData[extrema.localMin.idx].date : startDate,
            localMinDayIndex: extrema.localMin.idx >= 0 ? extrema.localMin.idx + 1 : 0,
            localMaxPrice: extrema.localMax.price,
            localMaxDate: extrema.localMax.idx >= 0 ? cycleData[extrema.localMax.idx].date : startDate,
            localMaxDayIndex: extrema.localMax.idx >= 0 ? extrema.localMax.idx + 1 : 0,
            maxDrawdownPercent: drawdownData.drawdownPercent,
            nearestFibonacciLevel: drawdownData.nearestFibonacci,
            drawdownFromPrice: drawdownData.fromPrice,
            drawdownToPrice: drawdownData.toPrice,
            data: cycleData.map((p, idx) => ({
              day: idx + 1,
              date: p.date,
              price: parseFloat(p.price.toString()),
              volume: p.volume ? parseFloat(p.volume.toString()) : 0,
            })),
            color: CYCLE_COLORS[cycles.length % CYCLE_COLORS.length],
          });
        }
      }
    });

    return cycles;
  };

  const createChartData = (cycles: Cycle[], visible: Record<string, boolean> = {}): any[] => {
    const maxDays = Math.max(...cycles.map(c => c.data.length));
    const chartData = [];

    for (let day = 1; day <= maxDays; day++) {
      const dataPoint: any = { day, dayLabel: `Day ${day}`, totalVolume: 0 };

      cycles.forEach(cycle => {
        if (day <= cycle.data.length) {
          dataPoint[cycle.id] = cycle.data[day - 1].price;
          if (visible[cycle.id] !== false) {
            dataPoint.totalVolume += cycle.data[day - 1].volume || 0;
          }
        }
      });

      chartData.push(dataPoint);
    }

    const allPrices = chartData.map(d => {
      const prices = cycles.map(c => d[c.id]).filter(p => p !== undefined);
      return prices.length > 0 ? Math.max(...prices) : NaN;
    });

    const sma20 = calculateSMA(allPrices, 20);
    const sma50 = calculateSMA(allPrices, 50);
    const sma200 = calculateSMA(allPrices, 200);

    chartData.forEach((d, i) => {
      d.ma20 = sma20[i];
      d.ma50 = sma50[i];
      d.ma200 = sma200[i];
    });

    return chartData;
  };

  useEffect(() => {
    const fetchAndProcessData = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/bitcoin-history/prices?start_date=2010-01-01');
        const result = await response.json();

        if (result.prices && result.prices.length > 0) {
          const identifiedCycles = identifyCycles(result.prices);
          setCycles(identifiedCycles);

          const visible: Record<string, boolean> = {};
          identifiedCycles.forEach(cycle => {
            visible[cycle.id] = true;
          });

          const chartData = createChartData(identifiedCycles, visible);
          setAllData(chartData);
          setVisibleCycles(visible);
        }
      } catch (error) {
        console.error('Failed to fetch bitcoin price history:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchAndProcessData();
  }, []);

  useEffect(() => {
    if (allData.length === 0) return;

    const localMaxDays = Math.max(...allData.map(d => d.day));

    const handleDocMouseDown = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (target.tagName === 'BUTTON' || target.closest('button')) {
        return;
      }
      if (chartRef && chartRef.contains(target)) {
        setIsDragging(true);
        setDragStartY(e.clientX);
      }
    };

    const handleDocMouseUp = (e: MouseEvent) => {
      if (isDragging && dragStartY !== null && chartRef && chartRef.contains(e.target as Node)) {
        const startDay = pixelToDay(dragStartY);
        const endDay = pixelToDay(e.clientX);

        const minDay = Math.max(0, Math.min(startDay, endDay));
        const maxDay = Math.min(localMaxDays, Math.max(startDay, endDay));

        if (maxDay - minDay > 1) {
          setPriceZoom([minDay, maxDay]);
        }
      }
      setIsDragging(false);
      setDragStartY(null);
    };

    const handleDocClick = (e: MouseEvent) => {
      if (chartRef && chartRef.contains(e.target as Node)) {
        setPriceZoom(null);
      }
    };

    document.addEventListener('mousedown', handleDocMouseDown);
    document.addEventListener('mouseup', handleDocMouseUp);
    document.addEventListener('click', handleDocClick);

    return () => {
      document.removeEventListener('mousedown', handleDocMouseDown);
      document.removeEventListener('mouseup', handleDocMouseUp);
      document.removeEventListener('click', handleDocClick);
    };
  }, [allData, isDragging, dragStartY, chartRef]);

  const handleLegendClick = (cycleId: string) => {
    const newVisibleCycles = {
      ...visibleCycles,
      [cycleId]: !visibleCycles[cycleId],
    };
    setVisibleCycles(newVisibleCycles);
    if (cycles.length > 0) {
      const newChartData = createChartData(cycles, newVisibleCycles);
      setAllData(newChartData);
    }
  };

  const maxDays = allData.length > 0 ? Math.max(...allData.map(d => d.day)) : 1;

  const pixelToDay = (pixelX: number): number => {
    if (!chartRef) return 0;

    const chartRect = chartRef.getBoundingClientRect();
    const leftMargin = 70;
    const rightMargin = 30;

    const chartLeft = chartRect.left + leftMargin;
    const chartRight = chartRect.right - rightMargin;
    const chartWidth = chartRight - chartLeft;

    if (chartWidth <= 0) return 0;

    const relativePos = (pixelX - chartLeft) / chartWidth;
    const clampedPos = Math.max(0, Math.min(1, relativePos));

    return Math.round(clampedPos * maxDays);
  };

  if (isLoading) {
    return <div className="w-full h-screen flex items-center justify-center"><p className="text-slate-600">Loading Bitcoin price history...</p></div>;
  }

  if (cycles.length === 0 || allData.length === 0) {
    return <div className="w-full h-screen flex items-center justify-center"><p className="text-red-600">Error loading price data</p></div>;
  }

  const yAxisTicksLog = [0.01, 0.05, 0.1, 0.5, 1, 5, 10, 50, 100, 500, 1000, 5000, 10000, 50000, 100000, 200000];
  const yAxisTicksLinear = [0, 15000, 30000, 45000, 60000, 75000, 90000, 105000, 120000, 150000];

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg border border-slate-200 p-6" style={{ pointerEvents: "none" }}>
        <div className="flex items-center justify-between mb-4" style={{ pointerEvents: "auto" }}>
          <h2 className="text-lg font-semibold">Bitcoin Bullrun Cycles</h2>
          <div className="flex gap-4">
            <div className="flex gap-3">
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" checked={visibleMAs.ma20} onChange={(e) => setVisibleMAs({...visibleMAs, ma20: e.target.checked})} className="w-4 h-4" />
                <span>SMA 20</span>
              </label>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" checked={visibleMAs.ma50} onChange={(e) => setVisibleMAs({...visibleMAs, ma50: e.target.checked})} className="w-4 h-4" />
                <span>SMA 50</span>
              </label>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" checked={visibleMAs.ma200} onChange={(e) => setVisibleMAs({...visibleMAs, ma200: e.target.checked})} className="w-4 h-4" />
                <span>SMA 200</span>
              </label>
            </div>
            <button onClick={() => setIsLogarithmic(!isLogarithmic)} className="px-4 py-2 bg-slate-100 hover:bg-slate-200 border border-slate-300 rounded text-sm font-medium transition-colors" style={{ pointerEvents: "auto" }}>
              {isLogarithmic ? "Logarithmic" : "Linear"} Scale
            </button>
          </div>
        </div>

        <div className="w-full" ref={setChartRef} style={{ cursor: isDragging ? "grabbing" : "grab", pointerEvents: "auto" }}>
          <div className="w-full h-[700px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={allData} margin={{ top: 5, right: 20, left: 60, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="day" type="number" tick={{ fontSize: 10 }} domain={priceZoom || [0, maxDays]} tickFormatter={(value) => `${value}`} ticks={Array.from({ length: Math.floor(maxDays / 100) + 1 }, (_, i) => i * 100)} />
                <YAxis scale={isLogarithmic ? "log" : "linear"} domain={isLogarithmic ? [0.01, 200000] : [0, 150000]} label={{ value: `Price in USD (${isLogarithmic ? "log" : "linear"})`, angle: -90, position: "insideLeft" }} tickFormatter={(value) => { if (value < 1) return `$${value.toFixed(2)}`; if (value < 1000) return `$${value.toFixed(0)}`; if (value < 1000000) return `$${(value / 1000).toFixed(0)}K`; return `$${(value / 1000000).toFixed(1)}M`; }} ticks={isLogarithmic ? yAxisTicksLog : yAxisTicksLinear} />
                <Tooltip formatter={(value) => typeof value === 'number' ? `$${value.toLocaleString('en-US', { maximumFractionDigits: 2 })}` : value} labelFormatter={(label) => `${label}`} contentStyle={{ backgroundColor: "rgba(255, 255, 255, 0.95)", border: "1px solid #ccc" }} />
                {cycles.map(cycle => (<Line key={cycle.id} type="monotone" dataKey={cycle.id} stroke={cycle.color} dot={false} strokeWidth={2} connectNulls={true} isAnimationActive={false} name={cycle.label} hide={!visibleCycles[cycle.id]} />))}
                {visibleMAs.ma20 && <Line type="monotone" dataKey="ma20" stroke="#ec4899" dot={false} strokeWidth={1.5} strokeDasharray="5 5" isAnimationActive={false} name="SMA 20" />}
                {visibleMAs.ma50 && <Line type="monotone" dataKey="ma50" stroke="#f59e0b" dot={false} strokeWidth={1.5} strokeDasharray="5 5" isAnimationActive={false} name="SMA 50" />}
                {visibleMAs.ma200 && <Line type="monotone" dataKey="ma200" stroke="#3b82f6" dot={false} strokeWidth={1.5} strokeDasharray="5 5" isAnimationActive={false} name="SMA 200" />}
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="w-full h-[200px] bg-slate-50 border-t border-slate-200">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={allData} margin={{ top: 5, right: 20, left: 60, bottom: 60 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="day" type="number" tick={{ fontSize: 11 }} label={{ value: "Days", position: "bottom", offset: 20 }} domain={priceZoom || [0, maxDays]} tickFormatter={(value) => `${value}`} ticks={Array.from({ length: Math.floor(maxDays / 100) + 1 }, (_, i) => i * 100)} />
                <YAxis label={{ value: "Volume (BTC)", angle: -90, position: "insideLeft" }} tickFormatter={(value) => `${(value / 1000).toFixed(0)}K`} />
                <Tooltip formatter={(value) => typeof value === 'number' ? `${value.toLocaleString('en-US', { maximumFractionDigits: 0 })} BTC` : value} labelFormatter={(label) => `Day ${label}`} contentStyle={{ backgroundColor: "rgba(255, 255, 255, 0.95)", border: "1px solid #ccc" }} />
                <Bar dataKey="totalVolume" fill="#94a3b8" isAnimationActive={false} name="Total Volume" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="border-t pt-4" style={{ marginLeft: "60px" }}>
          <div className="flex flex-col gap-2">
            {cycles.map(cycle => (
              <div key={cycle.id} className="flex items-center gap-2 cursor-pointer hover:opacity-70 transition-opacity" onClick={() => handleLegendClick(cycle.id)}>
                <div className="w-4 h-4 rounded" style={{ backgroundColor: cycle.color }} />
                <span className="text-sm text-slate-700">{cycle.label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {cycles.map((cycle) => (
          <div key={cycle.id} className="p-4 border rounded-lg cursor-pointer hover:bg-slate-50" onClick={() => setVisibleCycles(prev => ({...prev, [cycle.id]: !prev[cycle.id]}))} style={{ borderColor: cycle.color, borderWidth: 2 }}>
            <div className="flex items-center gap-2 mb-2">
              <div className="w-4 h-4 rounded" style={{ backgroundColor: cycle.color }} />
              <span className="font-semibold text-sm">{cycle.label}</span>
            </div>
            <div className="text-xs text-slate-600 space-y-1">
              <div>Duration: {cycle.data.length} days</div>
              <div>Start: ${cycle.startPrice.toLocaleString('en-US', { maximumFractionDigits: 2 })}</div>
              <div>End: ${cycle.endPrice.toLocaleString('en-US', { maximumFractionDigits: 2 })}</div>
              <div className="text-green-600 font-semibold">Max: ${cycle.maxPrice.toLocaleString('en-US', { maximumFractionDigits: 0 })}</div>
              <div className="text-red-600">Min: ${cycle.minPrice.toLocaleString('en-US', { maximumFractionDigits: 2 })}</div>
              <div className="pt-2 border-t border-slate-300 mt-2 text-slate-700">
                <div className="font-semibold text-slate-800">Days in cycle:</div>
                <div>Up to ATH: <span className="font-semibold text-green-600">{cycle.daysToATH} days</span></div>
                <div>From ATH: <span className="font-semibold text-orange-600">{cycle.daysFromATH} days</span></div>
              </div>
              <div className="pt-2 border-t border-slate-300 mt-2 text-slate-700">
                <div className="font-semibold text-slate-800">Local Extrema:</div>
                <div className="text-green-700 font-semibold">Max: ${cycle.localMaxPrice.toLocaleString('en-US', { maximumFractionDigits: 0 })}<span className="text-xs block">{formatDate(cycle.localMaxDate)} (Day {cycle.localMaxDayIndex})</span></div>
                <div className="text-red-700 font-semibold">Min: ${cycle.localMinPrice.toLocaleString('en-US', { maximumFractionDigits: 2 })}<span className="text-xs block">{formatDate(cycle.localMinDate)} (Day {cycle.localMinDayIndex})</span></div>
              </div>
              <div className="pt-2 border-t border-slate-300 mt-2 text-slate-700">
                <div className="font-semibold text-slate-800">Max Drawdown from ATH:</div>
                <div className="text-orange-700 font-semibold">Drawdown: <span className="text-lg">{cycle.maxDrawdownPercent.toFixed(1)}%</span> <span className="text-xs text-slate-600">(${cycle.drawdownFromPrice.toLocaleString('en-US', { maximumFractionDigits: 2 })} - ${cycle.drawdownToPrice.toLocaleString('en-US', { maximumFractionDigits: 2 })})</span><span className="text-xs block text-slate-600 mt-1">Fibonacci: {cycle.nearestFibonacciLevel.toFixed(1)}%</span></div>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="space-y-3">
        <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <h3 className="font-semibold text-blue-900 mb-2">Cycle Analysis</h3>
          <p className="text-sm text-blue-800">Total {cycles.length} cycles identified. Each cycle starts with the first value and ends at the next low after an all-time high. Click the legend or cards to show/hide cycles.</p>
        </div>
        <div className="p-4 bg-purple-50 border border-purple-200 rounded-lg">
          <h3 className="font-semibold text-purple-900 mb-2">Time Zoom</h3>
          <p className="text-sm text-purple-800">
            {priceZoom ? (
              <span>ZOOM: Day {Math.round(priceZoom[0])} - Day {Math.round(priceZoom[1])} | <span className="cursor-pointer hover:underline">Click to reset zoom</span></span>
            ) : (
              <span>Drag horizontally to zoom into a time range. Click to reset zoom to original view.</span>
            )}
          </p>
        </div>
      </div>
    </div>
  );
}
