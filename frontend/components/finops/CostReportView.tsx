"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { Icon } from "@iconify/react";
import { api, FinOpsReportResponse } from "@/lib/api";
import { CurrencyCode, formatCurrency } from "@/lib/currency";

type FilterRule = {
  dimension: "Resource" | "Service" | "Tag" | "Account" | "Region" | "Category";
  tagKey?: string;
  operator: "is" | "is not" | "contains" | "does not contain" | "starts with" | "ends with" | "flexible match";
  value: string;
};

type FilterSet = {
  id: string;
  provider: "AWS" | "Azure" | "GCP" | "All Providers" | "Kubernetes";
  rules: FilterRule[];
  allocationPct?: number;
};

type ChartMode = "bar" | "line" | "area" | "pie";
type MetricAxis = "cost" | "usage" | "count";

interface CostReportViewProps {
  provider?: string;
  currency?: CurrencyCode;
  accountId?: string;
}

export function CostReportView({
  provider = "aws",
  currency = "USD",
  accountId = "616551057703",
}: CostReportViewProps) {
  const { getToken } = useAuth();
  const [data, setData] = useState<FinOpsReportResponse | null>(null);
  const [loading, setLoading] = useState(true);

  // Sub-tabs: Overview, Anomalies (27), Forecasts
  const [activeSubTab, setActiveSubTab] = useState<"overview" | "anomalies" | "forecasts">("overview");

  // 4 Chart Modes matching Image 1: Bar, Line, Area, Pie
  const [chartMode, setChartMode] = useState<ChartMode>("area");

  // Y-Axis Metric Switcher matching Image 3: Cost, Usage, Count
  const [metricAxis, setMetricAxis] = useState<MetricAxis>("cost");
  const [showChartSettings, setShowChartSettings] = useState(false);
  const [additionalYAxis, setAdditionalYAxis] = useState(true);

  // Group By State matching Image 2
  const [showGroupByDropdown, setShowGroupByDropdown] = useState(false);
  const [selectedGroupings, setSelectedGroupings] = useState<string[]>(["Category", "Subcategory"]);

  // Filter Modal State
  const [showFilterModal, setShowFilterModal] = useState(false);
  const [filterSets, setFilterSets] = useState<FilterSet[]>([
    {
      id: "fs-1",
      provider: provider === "azure" ? "Azure" : provider === "gcp" ? "GCP" : "AWS",
      rules: [
        {
          dimension: "Service",
          operator: "is",
          value: provider === "azure" ? "Azure Kubernetes Service" : provider === "gcp" ? "Google Kubernetes Engine" : "AmazonEC2",
        },
        {
          dimension: "Category",
          operator: "is",
          value: "Data Transfer",
        },
      ],
    },
  ]);
  const [activeOperatorDropdownIdx, setActiveOperatorDropdownIdx] = useState<number | null>(null);
  const [isVqlMode, setIsVqlMode] = useState(false);

  // Date controls
  const [interval, setInterval] = useState("Last Month");
  const [dateBin, setDateBin] = useState("Cumulative");

  // Import Budget Modal matching Image 5
  const [showBudgetModal, setShowBudgetModal] = useState(false);
  const [budgetUploaded, setBudgetUploaded] = useState(false);
  const [uploadingBudget, setUploadingBudget] = useState(false);

  // Network costs inspection modal
  const [inspectNetworkResource, setInspectNetworkResource] = useState<string | null>(null);

  // Hover state on chart elements
  const [hoveredDateIdx, setHoveredDateIdx] = useState<number | null>(null);
  const [hoveredPieSlice, setHoveredPieSlice] = useState<string | null>(null);

  // Load saved budget or default based on connected cloud provider
  const storageKey = `whichcloud_budget_${provider}_${accountId}`;
  const [budgetTarget] = useState<number>(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem(storageKey);
      if (saved) return parseFloat(saved) || 50.0;
    }
    return provider === "aws" ? 50.0 : 45000.0;
  });

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    (async () => {
      try {
        const token = await getToken();
        const res = await api.finopsReports(
          provider,
          interval.toLowerCase().replace(" ", "_"),
          dateBin.toLowerCase(),
          selectedGroupings.join(","),
          accountId,
          token ?? undefined,
        );
        if (mounted) {
          setData(res);
          setLoading(false);
        }
      } catch (err) {
        console.error(err);
        if (mounted) setLoading(false);
      }
    })();

    return () => {
      mounted = false;
    };
  }, [provider, accountId, interval, dateBin, selectedGroupings, getToken]);

  if (loading || !data) {
    return (
      <div className="flex min-h-[400px] flex-col items-center justify-center">
        <Icon icon="line-md:loading-loop" className="h-8 w-8 text-accent animate-spin" />
        <span className="mt-3 text-[13.5px] text-ink-3">Fetching real-time costs from connected account...</span>
      </div>
    );
  }

  const allGroupingOptions = [
    "Ungrouped",
    "Account",
    "Billing Account",
    "Region",
    "Service",
    "Resource",
    "Provider",
    "Category",
    "Subcategory",
    "Charge Type",
    "Tag",
  ];

  const toggleGrouping = (opt: string) => {
    if (opt === "Ungrouped") {
      setSelectedGroupings([]);
      return;
    }
    if (selectedGroupings.includes(opt)) {
      setSelectedGroupings(selectedGroupings.filter((g) => g !== opt));
    } else {
      setSelectedGroupings([...selectedGroupings.filter((g) => g !== "Ungrouped"), opt]);
    }
  };

  const handleSimulateBudgetUpload = () => {
    setUploadingBudget(true);
    setTimeout(() => {
      setUploadingBudget(false);
      setBudgetUploaded(true);
      setTimeout(() => {
        setShowBudgetModal(false);
        setBudgetUploaded(false);
      }, 1200);
    }, 1000);
  };

  // Mock instance counts over time for Count Y-Axis mode (matching Image 3)
  const countSeries = [
    { date: "Mar 30", count: 125 },
    { date: "Apr 06", count: 132 },
    { date: "Apr 13", count: 140 },
    { date: "Apr 20", count: 147 },
    { date: "Apr 27", count: 154 },
    { date: "May 04", count: 161 },
    { date: "May 11", count: 169 },
    { date: "May 18", count: 176 },
    { date: "May 25", count: 183 },
    { date: "Jun 01", count: 190 },
    { date: "Jun 08", count: 198 },
    { date: "Jun 15", count: 205 },
    { date: "Jun 22", count: 212 },
    { date: "Jun 29", count: 219 },
  ];

  return (
    <div className="mt-4 flex flex-col space-y-6">
      {/* Sub-Header matching Image 4: Document icon, Report Title, Save & Import Budget buttons */}
      <div className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-5 shadow-xs sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#3B82F6] text-white shadow-sm">
            <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor" aria-hidden="true">
              <rect x="3.5" y="13" width="4" height="7.5" rx="1.2" />
              <rect x="10" y="8" width="4" height="12.5" rx="1.2" />
              <rect x="16.5" y="3.5" width="4" height="17" rx="1.2" />
            </svg>
          </div>
          <div>
            <div className="text-[12px] font-medium text-ink-3">Cost Reports</div>
            <h2 className="text-[19px] font-bold text-ink flex items-center gap-2">
              <span>{metricAxis === "count" ? "EC2 Instances Running & Scaling" : data.report_name}</span>
              <Icon icon="mdi:pencil-outline" className="h-4 w-4 text-ink-3 hover:text-ink cursor-pointer" />
            </h2>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowBudgetModal(true)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-3.5 py-1.5 text-[13px] font-medium text-ink hover:bg-sunk shadow-2xs transition-all"
          >
            <Icon icon="mdi:upload-outline" className="h-4 w-4 text-accent" />
            <span>Import Budget</span>
          </button>
          <button
            onClick={() => alert("Report configuration saved.")}
            className="inline-flex items-center gap-1.5 rounded-lg bg-[#7c3aed] px-4 py-1.5 text-[13px] font-semibold text-white shadow-xs hover:bg-[#6d28d9] transition-all"
          >
            <Icon icon="mdi:content-save-outline" className="h-4 w-4" />
            <span>Save as New</span>
          </button>
        </div>
      </div>

      {/* Sub-Tabs: Overview, Anomalies (27), Forecasts */}
      <div className="flex items-center gap-4 border-b border-line px-2">
        <button
          onClick={() => setActiveSubTab("overview")}
          className={`pb-3 text-[13.5px] font-semibold transition-all ${
            activeSubTab === "overview"
              ? "border-b-2 border-accent text-accent"
              : "text-ink-2 hover:text-ink"
          }`}
        >
          Overview
        </button>
        <button
          onClick={() => setActiveSubTab("anomalies")}
          className={`flex items-center gap-1.5 pb-3 text-[13.5px] font-semibold transition-all ${
            activeSubTab === "anomalies"
              ? "border-b-2 border-accent text-accent"
              : "text-ink-2 hover:text-ink"
          }`}
        >
          <span>Anomalies</span>
          <span className="rounded-full bg-red-500 px-2 py-0.2 text-[10.5px] font-bold text-white">
            27
          </span>
        </button>
        <button
          onClick={() => setActiveSubTab("forecasts")}
          className={`pb-3 text-[13.5px] font-semibold transition-all ${
            activeSubTab === "forecasts"
              ? "border-b-2 border-accent text-accent"
              : "text-ink-2 hover:text-ink"
          }`}
        >
          Forecasts
        </button>
      </div>

      {/* Budget KPI Triple-Badge Summary */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="rounded-xl border border-line bg-surface p-4 shadow-2xs">
          <div className="flex items-center justify-between text-[12px] font-medium text-ink-3">
            <span>Accrued Costs</span>
            <span
              className={`rounded px-2 py-0.5 text-[11px] font-bold ${
                (data.change_pct ?? 0) < 0
                  ? "bg-emerald-500/10 text-emerald-500"
                  : "bg-red-500/10 text-red-500"
              }`}
            >
              {(data.change_pct ?? 0) > 0 ? `+${data.change_pct}%` : `${data.change_pct ?? 0}%`}
            </span>
          </div>
          <div className="mt-1 font-mono text-[22px] font-bold text-ink">
            {formatCurrency(data.total_accrued_usd, currency, 2)}
          </div>
        </div>

        <div className="rounded-xl border border-line bg-surface p-4 shadow-2xs">
          <div className="flex items-center justify-between text-[12px] font-medium text-ink-3">
            <span>Forecasted Month-End</span>
            <span className="rounded bg-emerald-500/10 px-2 py-0.5 text-[11px] font-bold text-emerald-500">
              {provider === "aws" ? "On track" : "-2.4%"}
            </span>
          </div>
          <div className="mt-1 font-mono text-[22px] font-bold text-emerald-500">
            {provider === "aws"
              ? formatCurrency(25.48, currency, 2)
              : formatCurrency(data.total_accrued_usd * 1.08, currency, 2)}
          </div>
        </div>

        <div className="rounded-xl border border-line bg-surface p-4 shadow-2xs">
          <div className="flex items-center justify-between text-[12px] font-medium text-ink-3">
            <span>Target Budget Envelope</span>
            <span className="rounded bg-accent/10 px-2 py-0.5 text-[11px] font-bold text-accent">
              {Math.round((data.total_accrued_usd / Math.max(1, budgetTarget)) * 100)}% Used
            </span>
          </div>
          <div className="mt-1 font-mono text-[22px] font-bold text-accent">
            {formatCurrency(budgetTarget, currency, 2)}
          </div>
        </div>
      </div>

      {/* Toolbar matching Image 2 & 3: Filters, Group By, Cost Settings, Chart Settings popover */}
      <div className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-4 shadow-xs md:flex-row md:items-center md:justify-between">
        {/* Left: Filters, Group By, Settings */}
        <div className="relative flex flex-wrap items-center gap-2.5">
          {/* Filters Button */}
          <button
            onClick={() => setShowFilterModal(true)}
            className="inline-flex items-center gap-2 rounded-lg border-2 border-[#7c3aed] bg-surface px-3.5 py-1.5 text-[13.5px] font-semibold text-ink shadow-xs hover:bg-sunk transition-all"
          >
            <Icon icon="mdi:filter-variant" className="h-4 w-4 text-[#7c3aed]" />
            <span>Filters</span>
            {filterSets.length > 0 && (
              <span className="rounded-full bg-[#7c3aed] px-1.5 py-0.2 text-[10px] text-white">
                {filterSets.reduce((acc, f) => acc + f.rules.length, 0)}
              </span>
            )}
          </button>

          {/* Group By Dropdown Button matching Image 2 */}
          <div className="relative">
            <button
              onClick={() => setShowGroupByDropdown(!showGroupByDropdown)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-3.5 py-1.5 text-[13.5px] font-medium text-ink hover:bg-sunk shadow-2xs"
            >
              <Icon icon="mdi:grid-large" className="h-4 w-4 text-ink-3" />
              <span>
                Group By • {selectedGroupings.length === 0 ? "Ungrouped" : selectedGroupings.length}
              </span>
              <Icon icon="mdi:chevron-down" className="h-4 w-4 text-ink-3" />
            </button>

            {/* Dropdown Menu matching Image 2 */}
            {showGroupByDropdown && (
              <div className="absolute left-0 top-full z-40 mt-1.5 w-56 rounded-xl border border-line bg-surface p-2 shadow-xl backdrop-blur-md">
                <div className="px-2 py-1 text-[11px] font-bold uppercase tracking-wider text-ink-3">
                  Group By...
                </div>
                <div className="mt-1 space-y-0.5 max-h-64 overflow-y-auto">
                  {allGroupingOptions.map((opt) => {
                    const isChecked =
                      opt === "Ungrouped"
                        ? selectedGroupings.length === 0
                        : selectedGroupings.includes(opt);
                    return (
                      <label
                        key={opt}
                        className="flex cursor-pointer items-center justify-between rounded-md px-2 py-1.5 text-[13px] hover:bg-sunk text-ink"
                      >
                        <div className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => toggleGrouping(opt)}
                            className="rounded border-line text-[#7c3aed] focus:ring-0"
                          />
                          <span>{opt}</span>
                        </div>
                        {opt === "Category" && (
                          <span className="text-[11px] text-ink-3">Only</span>
                        )}
                      </label>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          <button
            onClick={() => alert("Cost Settings: Currency USD, Amortization Enabled, Taxes Included.")}
            className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-3 py-1.5 text-[13px] font-medium text-ink hover:bg-sunk shadow-2xs"
          >
            <Icon icon="mdi:cog-outline" className="h-4 w-4 text-ink-3" />
            <span>Cost Settings</span>
          </button>

          {/* Chart Settings with Y-Axis Popover matching Image 3 */}
          <div className="relative">
            <button
              onClick={() => setShowChartSettings(!showChartSettings)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-3 py-1.5 text-[13px] font-medium text-ink hover:bg-sunk shadow-2xs"
            >
              <Icon icon="mdi:tune-vertical" className="h-4 w-4 text-ink-3" />
              <span>Chart Settings</span>
              <span className="rounded bg-accent/10 px-1.5 py-0.2 text-[10px] font-bold text-accent uppercase">
                {metricAxis}
              </span>
            </button>

            {/* Y-Axis Metric Popover matching Image 3 */}
            {showChartSettings && (
              <div className="absolute left-0 top-full z-40 mt-1.5 w-64 rounded-2xl border border-line bg-surface p-4 shadow-xl">
                <div className="text-[12px] font-bold text-ink">Y-Axis Metric</div>
                <div className="mt-2 flex rounded-lg border border-line bg-sunk p-1">
                  {(["cost", "usage", "count"] as const).map((m) => (
                    <button
                      key={m}
                      onClick={() => {
                        setMetricAxis(m);
                        setShowChartSettings(false);
                      }}
                      className={`flex-1 rounded-md py-1 text-[12px] font-semibold capitalize transition-all ${
                        metricAxis === m
                          ? "bg-accent text-white shadow-xs"
                          : "text-ink-2 hover:text-ink"
                      }`}
                    >
                      {m}
                    </button>
                  ))}
                </div>

                <div className="mt-4 text-[12px] font-bold text-ink">Additional Y-Axes</div>
                <div className="mt-2 flex rounded-lg border border-line bg-sunk p-1">
                  <button
                    onClick={() => setAdditionalYAxis(true)}
                    className={`flex-1 rounded-md py-1 text-[12px] font-medium ${
                      additionalYAxis ? "bg-accent text-white" : "text-ink-2 hover:text-ink"
                    }`}
                  >
                    On
                  </button>
                  <button
                    onClick={() => setAdditionalYAxis(false)}
                    className={`flex-1 rounded-md py-1 text-[12px] font-medium ${
                      !additionalYAxis ? "bg-accent text-white" : "text-ink-2 hover:text-ink"
                    }`}
                  >
                    Off
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Date & Range Controls matching Image 1 */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Comparison Date Range */}
          <div className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-3 py-1.5 text-[12.5px] font-mono text-ink-2 shadow-2xs">
            <Icon icon="mdi:calendar-sync-outline" className="h-4 w-4 text-ink-3" />
            <span>{data.comparing_label || "Comparing Nov 1 - Nov 30 ⇋ Dec 1 - Dec 31"}</span>
          </div>

          <select
            value={dateBin}
            onChange={(e) => setDateBin(e.target.value)}
            className="rounded-lg border border-line bg-surface px-3 py-1.5 text-[13px] font-medium text-ink focus:border-accent focus:outline-none shadow-2xs"
          >
            <option value="Cumulative">Cumulative</option>
            <option value="Weekly">Weekly</option>
            <option value="Daily">Daily</option>
            <option value="Monthly">Monthly</option>
          </select>

          {/* Quick Icon Group for 4 Chart Types matching Image 1 */}
          <div className="flex rounded-lg border border-line bg-surface p-0.5 shadow-2xs">
            <button
              onClick={() => setChartMode("bar")}
              title="Bar Charts"
              className={`rounded p-1.5 ${chartMode === "bar" ? "bg-accent text-white shadow-xs" : "text-ink-3 hover:text-ink"}`}
            >
              <Icon icon="mdi:chart-box" className="h-4 w-4" />
            </button>
            <button
              onClick={() => setChartMode("line")}
              title="Line Chart"
              className={`rounded p-1.5 ${chartMode === "line" ? "bg-accent text-white shadow-xs" : "text-ink-3 hover:text-ink"}`}
            >
              <Icon icon="mdi:chart-line" className="h-4 w-4" />
            </button>
            <button
              onClick={() => setChartMode("area")}
              title="Area Chart"
              className={`rounded p-1.5 ${chartMode === "area" ? "bg-accent text-white shadow-xs" : "text-ink-3 hover:text-ink"}`}
            >
              <Icon icon="mdi:chart-areaspline" className="h-4 w-4" />
            </button>
            <button
              onClick={() => setChartMode("pie")}
              title="Pie Chart"
              className={`rounded p-1.5 ${chartMode === "pie" ? "bg-accent text-white shadow-xs" : "text-ink-3 hover:text-ink"}`}
            >
              <Icon icon="mdi:chart-pie" className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Main Graph Card */}
      <div className="rounded-2xl border border-line bg-surface p-6 shadow-xs">
        {/* Accrued Headline with % change */}
        <div className="border-b border-line pb-4">
          <div className="flex items-baseline gap-3">
            <span className="font-mono text-[32px] font-bold text-ink">
              {metricAxis === "count"
                ? "219 Active Instances"
                : metricAxis === "usage"
                ? "48,290 Hours"
                : formatCurrency(data.total_accrued_usd, currency, 2)}
            </span>
            <span
              className={`rounded-md px-2 py-0.5 text-[13px] font-bold font-mono ${
                (data.change_pct ?? 0) < 0
                  ? "bg-emerald-500/10 text-emerald-500"
                  : "bg-red-500/10 text-red-500"
              }`}
            >
              {(data.change_pct ?? 0) > 0 ? `+${data.change_pct}%` : `${data.change_pct ?? 0}%`} vs previous period
            </span>
          </div>
          <div className="text-[13px] text-ink-3">
            {metricAxis === "count"
              ? "Accrued Instance Count (for this timeframe)"
              : metricAxis === "usage"
              ? "Total Compute & Transfer Units"
              : "Accrued Costs (for this timeframe)"}
          </div>

          {/* Legend row with interactive pills */}
          <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-[12.5px] text-ink-2">
            {data.legend.map((item) => (
              <div key={item.id} className="flex items-center gap-1.5">
                <span
                  className="h-3 w-3 rounded-full shadow-2xs"
                  style={{ backgroundColor: item.color }}
                />
                <span className="font-medium text-ink">
                  {item.name} ({formatCurrency(item.accrued, currency, 2)})
                </span>
              </div>
            ))}
            <div className="flex items-center gap-1.5">
              <span className="h-3 w-3 rounded-full bg-slate-400" />
              <span className="font-medium text-ink">
                Target Budget ({formatCurrency(budgetTarget, currency, 0)})
              </span>
            </div>
          </div>
        </div>

        {/* Dynamic Live Chart Display Container */}
        {(() => {
          const isCumulative = dateBin.toLowerCase() === "cumulative";
          const numPoints = data.series.length;

          // Maximum value for chart Y-axis scaled dynamically to the account
          const rawMax = Math.max(
            ...data.series.map((s) => (isCumulative ? (s.cumulative ?? s.total) : s.total)),
            budgetTarget,
            provider === "aws" ? 30.0 : 1000.0
          );
          const maxVal = metricAxis === "count"
            ? 250
            : metricAxis === "usage"
            ? 50000
            : Math.ceil(rawMax * 1.25);
          const midVal = maxVal / 2;

          // Coordinate mapping in 700x240 SVG viewbox
          const plotLeft = 40;
          const plotRight = 660;
          const plotWidth = plotRight - plotLeft; // 620
          const plotTop = 25;
          const plotBottom = 215;
          const plotHeight = plotBottom - plotTop; // 190

          const points = data.series.map((item, idx) => {
            const x = numPoints <= 1 ? 350 : plotLeft + (idx / (numPoints - 1)) * plotWidth;
            const val = isCumulative ? (item.cumulative ?? item.total) : item.total;
            const y = Math.max(plotTop, Math.min(plotBottom, plotBottom - (val / maxVal) * plotHeight));
            return { x, y, val, date: item.date, item };
          });

          const budgetPoints = data.series.map((item, idx) => {
            const x = numPoints <= 1 ? 350 : plotLeft + (idx / (numPoints - 1)) * plotWidth;
            const bVal = isCumulative
              ? (budgetTarget / Math.max(1, numPoints)) * (idx + 1)
              : budgetTarget / Math.max(1, numPoints);
            const y = Math.max(plotTop, Math.min(plotBottom, plotBottom - (bVal / maxVal) * plotHeight));
            return { x, y, bVal };
          });

          const activeHoverIdx =
            hoveredDateIdx !== null && hoveredDateIdx >= 0 && hoveredDateIdx < points.length
              ? hoveredDateIdx
              : points.length - 1;
          const curPoint = points[activeHoverIdx] || points[0];
          const curBudget = budgetPoints[activeHoverIdx] || budgetPoints[0];

          const spendLinePath = points.map((p, i) => (i === 0 ? `M ${p.x} ${p.y}` : `L ${p.x} ${p.y}`)).join(" ");
          const spendAreaPath = points.length > 0
            ? `${spendLinePath} L ${points[points.length - 1].x} ${plotBottom} L ${points[0].x} ${plotBottom} Z`
            : "";
          const budgetLinePath = budgetPoints.map((p, i) => (i === 0 ? `M ${p.x} ${p.y}` : `L ${p.x} ${p.y}`)).join(" ");

          const diffFromBudget = curPoint ? (curPoint.val ?? 0) - curBudget.bVal : 0;
          const pctVariance = Math.round((Math.abs(diffFromBudget) / Math.max(0.01, curBudget.bVal)) * 100);
          const isOverBudget = diffFromBudget > 0;

          return (
            <div className="mt-8 relative h-80 w-full">
              {/* Y Axis Grid lines dynamically scaled */}
              <div className="absolute inset-0 flex flex-col justify-between pointer-events-none text-[11px] font-mono text-ink-3 border-b border-line">
                <div className="flex items-center justify-between border-b border-line/40 pb-1">
                  <span>
                    {metricAxis === "count"
                      ? "250 Instances"
                      : formatCurrency(maxVal, currency, 2)}
                  </span>
                  <div className="w-full border-b border-dashed border-line/30 ml-4" />
                </div>
                <div className="flex items-center justify-between border-b border-line/40 pb-1">
                  <span>
                    {metricAxis === "count"
                      ? "125 Instances"
                      : formatCurrency(midVal, currency, 2)}
                  </span>
                  <div className="w-full border-b border-dashed border-line/30 ml-4" />
                </div>
                <div className="flex items-center justify-between pb-1">
                  <span>{formatCurrency(0, currency, 2)}</span>
                  <div className="w-full border-b border-line/50 ml-4" />
                </div>
              </div>

              {/* MODE 1: Dynamic Donut / Pie Chart */}
              {chartMode === "pie" && (() => {
                const totalSpend = data.legend.reduce((acc, l) => acc + l.accrued, 0) || data.total_accrued_usd;
                const circumference = 226.195;
                let accumulatedLength = 0;

                return (
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="relative flex flex-col items-center">
                      <svg className="h-64 w-64 transform -rotate-90 overflow-visible" viewBox="0 0 100 100">
                        {data.legend.map((item) => {
                          const pct = item.accrued / Math.max(0.01, totalSpend);
                          const sliceLength = pct * circumference;
                          const strokeDasharray = `${sliceLength} ${circumference - sliceLength}`;
                          const strokeDashoffset = -accumulatedLength;
                          accumulatedLength += sliceLength;

                          return (
                            <circle
                              key={item.id}
                              cx="50"
                              cy="50"
                              r="36"
                              fill="transparent"
                              stroke={item.color}
                              strokeWidth="22"
                              strokeDasharray={strokeDasharray}
                              strokeDashoffset={strokeDashoffset}
                              className="cursor-pointer hover:opacity-85 transition-all"
                              onMouseEnter={() =>
                                setHoveredPieSlice(
                                  `${item.name}: ${formatCurrency(item.accrued, currency, 2)} (${(pct * 100).toFixed(1)}%)`
                                )
                              }
                              onMouseLeave={() => setHoveredPieSlice(null)}
                            />
                          );
                        })}
                      </svg>

                      {/* Donut Center Label */}
                      <div className="absolute inset-0 flex flex-col items-center justify-center text-center pointer-events-none">
                        <span className="text-[11px] uppercase font-bold text-ink-3">Total Spend</span>
                        <span className="font-mono text-[18px] font-bold text-ink">
                          {formatCurrency(data.total_accrued_usd, currency, 2)}
                        </span>
                      </div>

                      {hoveredPieSlice && (
                        <div className="mt-3 rounded-lg bg-surface border border-line px-3 py-1.5 text-[12px] font-mono font-bold text-ink shadow-lg">
                          {hoveredPieSlice}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })()}

              {/* MODE 2: Dynamic Stacked Multi-Bar Chart */}
              {chartMode === "bar" && (
                <div className="absolute inset-x-8 bottom-6 top-4 flex items-end justify-between px-4">
                  {data.series.map((bucket, idx) => {
                    const val = isCumulative ? (bucket.cumulative ?? bucket.total) : bucket.total;
                    const barHeightPct = Math.max(6, Math.min(100, (val / maxVal) * 100));
                    return (
                      <div
                        key={bucket.date}
                        onMouseEnter={() => setHoveredDateIdx(idx)}
                        className="relative flex flex-col items-center group cursor-pointer flex-1 max-w-[90px] mx-2"
                      >
                        <div
                          className="w-full rounded-t-lg flex flex-col-reverse overflow-hidden transition-all duration-300 hover:opacity-90 shadow-xs border border-line/60"
                          style={{ height: `${(barHeightPct / 100) * plotHeight}px` }}
                        >
                          {data.legend.map((item) => {
                            const itemVal = bucket.breakdown?.[item.id] || (item.accrued / data.legend.length);
                            const itemPct = Math.round((itemVal / Math.max(0.01, bucket.total)) * 100);
                            return (
                              <div
                                key={item.id}
                                style={{ height: `${itemPct}%`, backgroundColor: item.color }}
                                title={`${item.name}: ${formatCurrency(itemVal, currency, 2)}`}
                              />
                            );
                          })}
                        </div>
                        <span
                          className={`mt-2 text-[11px] font-mono transition-colors ${
                            activeHoverIdx === idx ? "font-bold text-accent" : "text-ink-3"
                          }`}
                        >
                          {bucket.date}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* MODE 3: Dynamic Live Area / Line Chart with Interactive Tooltip */}
              {(chartMode === "area" || chartMode === "line") && (
                <div className="absolute inset-x-4 bottom-6 top-4">
                  <svg className="h-full w-full overflow-visible" viewBox="0 0 700 240" preserveAspectRatio="none">
                    <defs>
                      <linearGradient id="finopsAreaGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#7c3aed" stopOpacity="0.38" />
                        <stop offset="100%" stopColor="#7c3aed" stopOpacity="0.0" />
                      </linearGradient>
                    </defs>

                    {/* Target Budget Line (smooth blue/grey) */}
                    <path
                      d={budgetLinePath}
                      fill="none"
                      stroke="#94a3b8"
                      strokeWidth="2.5"
                      strokeDasharray="5 5"
                    />

                    {/* Actual Spend Area Fill */}
                    {chartMode === "area" && (
                      <path
                        d={spendAreaPath}
                        fill="url(#finopsAreaGradient)"
                      />
                    )}

                    {/* Actual Spend Line */}
                    <path
                      d={spendLinePath}
                      fill="none"
                      stroke="#7c3aed"
                      strokeWidth="3.5"
                    />

                    {/* Interactive Hover Point & Guideline */}
                    {curPoint && (
                      <g className="transition-all duration-150">
                        <line
                          x1={curPoint.x}
                          y1={plotTop}
                          x2={curPoint.x}
                          y2={plotBottom}
                          stroke="#94a3b8"
                          strokeWidth="1.5"
                          strokeDasharray="4 4"
                        />
                        <circle
                          cx={curPoint.x}
                          cy={curBudget.y}
                          r="5"
                          fill="#94a3b8"
                          stroke="#ffffff"
                          strokeWidth="2"
                        />
                        <circle
                          cx={curPoint.x}
                          cy={curPoint.y}
                          r="6.5"
                          fill="#7c3aed"
                          stroke="#ffffff"
                          strokeWidth="2.5"
                        />
                      </g>
                    )}
                  </svg>

                  {/* Floating Live Tooltip */}
                  {curPoint && (
                    <div
                      className="absolute z-30 rounded-xl border border-line bg-surface/95 backdrop-blur-md p-3.5 shadow-2xl text-left pointer-events-none transition-all duration-150"
                      style={{
                        left: `${Math.max(6, Math.min(66, (curPoint.x / 700) * 100 - 16))}%`,
                        top: "10%",
                      }}
                    >
                      <div className="text-[12px] font-semibold text-ink-3">
                        {curPoint.date} • {isCumulative ? "Cumulative to date" : "Period spend"}
                      </div>
                      <div className="mt-2 space-y-1.5 text-[12.5px]">
                        <div className="flex items-center justify-between gap-6">
                          <span className="flex items-center gap-1.5 text-ink-2">
                            <span className="h-2 w-2 rounded-full bg-slate-400" />
                            Target Budget
                          </span>
                          <span className="font-mono font-bold text-ink">
                            {formatCurrency(curBudget.bVal, currency, 2)}
                          </span>
                        </div>
                        <div className="flex items-center justify-between gap-6">
                          <span className="flex items-center gap-1.5 text-accent font-semibold">
                            <span className="h-2 w-2 rounded-full bg-[#7c3aed]" />
                            Actual Spend
                          </span>
                          <span
                            className={`font-mono font-bold ${
                              isOverBudget ? "text-red-500" : "text-emerald-500"
                            }`}
                          >
                            {formatCurrency(curPoint ? (curPoint.val ?? 0) : 0, currency, 2)}
                          </span>
                        </div>
                      </div>
                      <div
                        className={`mt-2 rounded-lg px-2 py-0.5 text-[11px] font-bold ${
                          isOverBudget
                            ? "bg-red-500/10 text-red-500"
                            : "bg-emerald-500/10 text-emerald-500"
                        }`}
                      >
                        {isOverBudget
                          ? `⚠️ Over Target Budget by +${pctVariance}%`
                          : `✅ Within Target Budget (-${pctVariance}%)`}
                      </div>
                    </div>
                  )}

                  {/* X Axis Dates from Live Account Series */}
                  <div className="mt-3 flex justify-between px-6 text-[11px] font-mono text-ink-3">
                    {points.map((p, idx) => (
                      <button
                        key={p.date}
                        onClick={() => setHoveredDateIdx(idx)}
                        onMouseEnter={() => setHoveredDateIdx(idx)}
                        className={`cursor-pointer transition-colors ${
                          activeHoverIdx === idx
                            ? "font-bold text-accent"
                            : "hover:text-ink"
                        }`}
                      >
                        {p.date}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })()}

        {/* BOTTOM TAB BAR matching Image 1: [ Bar Charts ] [ Line Chart ] [ Area Chart ] [ Pie Chart ] */}
        <div className="mt-8 flex items-center justify-center border-t border-line pt-4">
          <div className="inline-flex items-center gap-2 sm:gap-6">
            <button
              onClick={() => setChartMode("bar")}
              className={`flex items-center gap-2 pb-2 text-[14px] font-semibold transition-all ${
                chartMode === "bar"
                  ? "border-b-2 border-[#7c3aed] text-[#7c3aed]"
                  : "text-ink-2 hover:text-ink"
              }`}
            >
              <Icon icon="mdi:chart-box" className="h-4 w-4" />
              <span>Bar Charts</span>
            </button>
            <button
              onClick={() => setChartMode("line")}
              className={`flex items-center gap-2 pb-2 text-[14px] font-semibold transition-all ${
                chartMode === "line"
                  ? "border-b-2 border-[#7c3aed] text-[#7c3aed]"
                  : "text-ink-2 hover:text-ink"
              }`}
            >
              <Icon icon="mdi:chart-line" className="h-4 w-4" />
              <span>Line Chart</span>
            </button>
            <button
              onClick={() => setChartMode("area")}
              className={`flex items-center gap-2 pb-2 text-[14px] font-semibold transition-all ${
                chartMode === "area"
                  ? "border-b-2 border-[#7c3aed] text-[#7c3aed]"
                  : "text-ink-2 hover:text-ink"
              }`}
            >
              <Icon icon="mdi:chart-areaspline" className="h-4 w-4" />
              <span>Area Chart</span>
            </button>
            <button
              onClick={() => setChartMode("pie")}
              className={`flex items-center gap-2 pb-2 text-[14px] font-semibold transition-all ${
                chartMode === "pie"
                  ? "border-b-2 border-[#7c3aed] text-[#7c3aed]"
                  : "text-ink-2 hover:text-ink"
              }`}
            >
              <Icon icon="mdi:chart-pie" className="h-4 w-4" />
              <span>Pie Chart</span>
            </button>
          </div>
        </div>
      </div>

      {/* Multi-Dimensional Drilldown Table matching Image 2 */}
      <div className="overflow-hidden rounded-2xl border border-line bg-surface shadow-xs">
        <div className="flex items-center justify-between border-b border-line px-6 py-4">
          <div>
            <h3 className="text-[16px] font-bold text-ink">
              Multi-Dimensional Drilldown Breakdown
            </h3>
            <p className="text-[12.5px] text-ink-3">
              Grouped by {selectedGroupings.join(" → ")} with period-over-period delta.
            </p>
          </div>
          <div className="flex items-center gap-2 text-[12px] font-mono">
            <span className="rounded bg-sunk px-2.5 py-1 text-ink-2">
              {metricAxis.toUpperCase()} VIEW
            </span>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-[13.5px]">
            <thead className="border-b border-line bg-sunk/50 text-[11.5px] font-semibold uppercase tracking-wider text-ink-3">
              <tr>
                <th className="py-3 pl-6 pr-3">Service</th>
                <th className="py-3 px-3">Region</th>
                <th className="py-3 px-3">Category</th>
                <th className="py-3 px-3">Subcategory</th>
                <th className="py-3 px-3 text-right">
                  {metricAxis === "count" ? "Accrued Count" : "Accrued Costs (Dec 1 - 31)"}
                </th>
                <th className="py-3 px-3 text-right">
                  {metricAxis === "count" ? "Previous Count" : "Previous Period (Nov 1 - 30)"}
                </th>
                <th className="py-3 pr-6 text-right">Change %</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {data.table_items.map((item) => (
                <tr key={item.id} className="hover:bg-sunk/40 transition-colors">
                  {/* Service with drilldown icons matching Image 2 */}
                  <td className="py-3.5 pl-6 pr-3">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => {
                          setSelectedGroupings(["Service", "Region", "Category", "Subcategory"]);
                        }}
                        title="Drill down"
                        className="flex h-6 w-6 items-center justify-center rounded border border-line bg-surface text-ink-3 hover:border-accent hover:text-accent"
                      >
                        <Icon icon="mdi:shape-outline" className="h-3.5 w-3.5" />
                      </button>
                      <span className="font-semibold text-ink">{item.service}</span>
                    </div>
                  </td>

                  {/* Region */}
                  <td className="py-3.5 px-3 font-mono text-[12.5px] text-ink-2">
                    {item.region}
                  </td>

                  {/* Category */}
                  <td className="py-3.5 px-3 text-ink-2">{item.category}</td>

                  {/* Subcategory */}
                  <td className="py-3.5 px-3 font-mono text-[12px] text-purple-400">
                    <div className="flex items-center gap-1.5">
                      <span>{item.subcategory}</span>
                      {item.has_network_costs && (
                        <button
                          onClick={() => setInspectNetworkResource(item.resource)}
                          className="rounded border border-[#7c3aed]/30 bg-[#7c3aed]/10 px-1.5 py-0.2 text-[10px] font-semibold text-[#7c3aed]"
                        >
                          Flow
                        </button>
                      )}
                    </div>
                  </td>

                  {/* Accrued Value */}
                  <td className="py-3.5 px-3 text-right font-mono font-bold text-ink">
                    {metricAxis === "count" ? "17" : formatCurrency(item.accrued_usd, currency, 2)}
                  </td>

                  {/* Previous Period Value */}
                  <td className="py-3.5 px-3 text-right font-mono text-ink-3">
                    {metricAxis === "count" ? "14" : item.prev_usd ? formatCurrency(item.prev_usd, currency, 2) : "—"}
                  </td>

                  {/* Change % */}
                  <td className="py-3.5 pr-6 text-right">
                    {item.change_pct !== undefined ? (
                      <span
                        className={`inline-block font-mono text-[12.5px] font-semibold ${
                          item.change_pct < 0 ? "text-emerald-500" : "text-red-500"
                        }`}
                      >
                        {item.change_pct > 0 ? `+${item.change_pct}%` : `${item.change_pct}%`}
                      </span>
                    ) : (
                      <span className="text-ink-3">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* IMPORT BUDGET MODAL matching Image 5 */}
      {showBudgetModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
          <div className="relative w-full max-w-md rounded-2xl border border-line bg-surface p-6 shadow-2xl">
            <button
              onClick={() => setShowBudgetModal(false)}
              className="absolute right-4 top-4 rounded-md p-1 text-ink-3 hover:text-ink"
            >
              <Icon icon="mdi:close" className="h-5 w-5" />
            </button>

            <h3 className="text-[18px] font-bold text-ink">Import Budget Data</h3>
            <p className="mt-2 text-[13px] leading-relaxed text-ink-2">
              Import multiple budgets by uploading a CSV. Please review the formatting guide before uploading a file.
            </p>

            {/* Drag & Drop Upload Zone matching Image 5 */}
            <div className="mt-5 flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-[#7c3aed]/40 bg-[#7c3aed]/5 p-8 text-center transition-all hover:bg-[#7c3aed]/10">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand text-white shadow-md">
                <svg viewBox="0 0 24 24" className="h-7 w-7" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
              </div>
              <div className="mt-4 flex items-center gap-1.5 text-[13px] text-ink-2">
                <span>Max</span>
                <span className="rounded bg-accent/20 px-1.5 py-0.5 font-mono text-[11px] font-bold text-accent">
                  CSV
                </span>
                <span>size (500MB)</span>
              </div>
            </div>

            {budgetUploaded && (
              <div className="mt-4 rounded-xl border border-emerald-500/20 bg-emerald-500/10 p-3 text-[13px] text-emerald-500 flex items-center gap-2">
                <Icon icon="mdi:check-circle" className="h-4 w-4" />
                <span>Budget targets imported successfully! Updating forecasts...</span>
              </div>
            )}

            {/* Modal Actions */}
            <div className="mt-6 flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setShowBudgetModal(false)}
                className="rounded-lg border border-line px-4 py-2 text-[13.5px] font-medium text-ink-2 hover:bg-sunk hover:text-ink"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSimulateBudgetUpload}
                disabled={uploadingBudget || budgetUploaded}
                className="inline-flex items-center gap-2 rounded-lg bg-[#7c3aed] px-5 py-2 text-[13.5px] font-semibold text-white shadow-xs hover:bg-[#6d28d9] disabled:opacity-50 transition-all"
              >
                {uploadingBudget ? (
                  <>
                    <Icon icon="line-md:loading-loop" className="h-4 w-4" />
                    <span>Processing CSV...</span>
                  </>
                ) : (
                  <span>Upload File</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* FILTER BUILDER MODAL */}
      {showFilterModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
          <div className="relative w-full max-w-2xl rounded-2xl border border-line bg-surface p-6 shadow-2xl max-h-[90vh] overflow-y-auto">
            <button
              onClick={() => setShowFilterModal(false)}
              className="absolute right-4 top-4 rounded-md p-1 text-ink-3 hover:text-ink"
            >
              <Icon icon="mdi:close" className="h-5 w-5" />
            </button>

            <div className="flex items-center justify-between border-b border-line pb-4">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#7c3aed]/10 text-[#7c3aed]">
                  <Icon icon="mdi:filter-variant" className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-[17px] font-bold text-ink">Cost Report Filters</h3>
                  <p className="text-[12px] text-ink-3">Configure multi-cloud exact or flexible matching rules</p>
                </div>
              </div>

              <button
                onClick={() => setIsVqlMode(!isVqlMode)}
                className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-sunk px-3 py-1 text-[12px] font-mono text-ink-2 hover:text-ink"
              >
                <Icon icon="mdi:code-braces" className="h-3.5 w-3.5" />
                <span>{isVqlMode ? "Visual Builder" : "View Query Code"}</span>
              </button>
            </div>

            {isVqlMode ? (
              <div className="mt-5 space-y-3">
                <div className="rounded-xl border border-line bg-[#0d1117] p-4 font-mono text-[13px] text-emerald-400">
                  <pre>{`// WhichCloud Cost Query Filter
from costs
where provider = "${provider}"
  and costs.service = "AmazonEC2"
  and costs.category = "Data Transfer"
  and costs.tag["Teams"] =~ "Team A"
  and allocation_pct = 0.50`}</pre>
                </div>
              </div>
            ) : (
              <div className="mt-5 space-y-6">
                {filterSets.map((fs, fsIdx) => (
                  <div key={fs.id} className="rounded-xl border border-line bg-sunk/30 p-4 space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-[13px] font-semibold text-ink">
                          {fsIdx === 0 ? "All Costs" : "Or Costs"}
                        </span>
                        <span className="text-[12px] text-ink-3">from</span>
                        <span className="inline-flex items-center gap-1.5 rounded bg-surface border border-line px-2 py-0.5 text-[12px] font-medium text-ink">
                          <Icon
                            icon={
                              fs.provider.toLowerCase().includes("azure")
                                ? "logos:microsoft-azure"
                                : fs.provider.toLowerCase().includes("gcp") || fs.provider.toLowerCase().includes("google")
                                ? "logos:google-cloud"
                                : fs.provider.toLowerCase().includes("github")
                                ? "logos:github-icon"
                                : "logos:aws"
                            }
                            className="h-3 w-3"
                          />
                          {fs.provider}
                        </span>
                      </div>

                      <button
                        onClick={() => setFilterSets(filterSets.filter((f) => f.id !== fs.id))}
                        className="text-ink-3 hover:text-red-500"
                        title="Remove Filter Set"
                      >
                        <Icon icon="mdi:delete-outline" className="h-4 w-4" />
                      </button>
                    </div>

                    {fs.rules.map((rule, rIdx) => (
                      <div key={rIdx} className="flex flex-wrap items-center gap-2 pt-1">
                        <span className="text-[12.5px] text-ink-3">
                          {rIdx === 0 ? "where" : "and"}
                        </span>

                        <div className="inline-flex items-center gap-1 rounded-md border border-line bg-surface px-2.5 py-1 text-[12.5px] font-medium text-ink">
                          <Icon icon="mdi:chip" className="h-3.5 w-3.5 text-ink-3" />
                          <span>{rule.dimension}</span>
                        </div>

                        <input
                          type="text"
                          value={rule.value}
                          onChange={(e) => {
                            const newSets = [...filterSets];
                            newSets[fsIdx].rules[rIdx].value = e.target.value;
                            setFilterSets(newSets);
                          }}
                          placeholder="Select or enter value..."
                          className="rounded-md border border-line bg-surface px-2.5 py-1 text-[12.5px] text-ink focus:border-[#7c3aed] focus:outline-none"
                        />

                        <div className="relative">
                          <button
                            onClick={() =>
                              setActiveOperatorDropdownIdx(
                                activeOperatorDropdownIdx === rIdx ? null : rIdx
                              )
                            }
                            className="inline-flex items-center gap-1 rounded-md border-2 border-[#7c3aed] bg-surface px-2.5 py-0.5 text-[12.5px] font-medium text-[#7c3aed]"
                          >
                            <span>{rule.operator}</span>
                            <Icon icon="mdi:chevron-down" className="h-3.5 w-3.5" />
                          </button>

                          {activeOperatorDropdownIdx === rIdx && (
                            <div className="absolute left-0 top-full z-50 mt-1 w-36 rounded-lg border border-line bg-surface py-1 shadow-lg">
                              {(
                                [
                                  "is",
                                  "is not",
                                  "contains",
                                  "does not contain",
                                  "starts with",
                                  "ends with",
                                  "flexible match",
                                ] as const
                              ).map((op) => (
                                <button
                                  key={op}
                                  onClick={() => {
                                    const newSets = [...filterSets];
                                    newSets[fsIdx].rules[rIdx].operator = op;
                                    setFilterSets(newSets);
                                    setActiveOperatorDropdownIdx(null);
                                  }}
                                  className={`flex w-full items-center justify-between px-3 py-1.5 text-left text-[12px] hover:bg-sunk ${
                                    rule.operator === op
                                      ? "font-bold text-[#7c3aed]"
                                      : "text-ink"
                                  }`}
                                >
                                  <span>{op}</span>
                                  {rule.operator === op && (
                                    <Icon icon="mdi:check" className="h-3.5 w-3.5" />
                                  )}
                                </button>
                              ))}
                            </div>
                          )}
                        </div>

                        <button
                          onClick={() => {
                            const newSets = [...filterSets];
                            newSets[fsIdx].rules = newSets[fsIdx].rules.filter(
                              (_, idx) => idx !== rIdx
                            );
                            setFilterSets(newSets);
                          }}
                          className="text-ink-3 hover:text-red-500 p-1"
                        >
                          <Icon icon="mdi:delete-outline" className="h-4 w-4" />
                        </button>
                      </div>
                    ))}

                    <div className="flex items-center gap-3 pt-2">
                      <button
                        onClick={() => {
                          const newSets = [...filterSets];
                          newSets[fsIdx].rules.push({
                            dimension: "Tag",
                            operator: "flexible match",
                            value: "Team A",
                          });
                          setFilterSets(newSets);
                        }}
                        className="rounded-md border border-line bg-surface px-2.5 py-1 text-[12px] font-medium text-ink hover:bg-sunk"
                      >
                        New Rule
                      </button>
                    </div>
                  </div>
                ))}

                <button
                  onClick={() =>
                    setFilterSets([
                      ...filterSets,
                      {
                        id: `fs-${Date.now()}`,
                        provider: "AWS",
                        rules: [
                          {
                            dimension: "Resource",
                            operator: "is",
                            value: "Amazon Relational Database Service",
                          },
                        ],
                      },
                    ])
                  }
                  className="inline-flex w-full items-center justify-center gap-1.5 rounded-xl border border-dashed border-line py-2.5 text-[13px] font-medium text-ink-2 hover:border-accent hover:text-ink"
                >
                  <Icon icon="mdi:plus" className="h-4 w-4" />
                  <span>Add a Filter</span>
                </button>
              </div>
            )}

            <div className="mt-6 flex items-center justify-between border-t border-line pt-4">
              <button
                onClick={() => setFilterSets([])}
                className="text-[12.5px] font-medium text-ink-3 hover:text-ink"
              >
                Clear All Filters
              </button>
              <div className="flex gap-2.5">
                <button
                  onClick={() => setShowFilterModal(false)}
                  className="rounded-lg border border-line px-4 py-1.5 text-[13px] font-medium text-ink-2 hover:bg-sunk"
                >
                  Cancel
                </button>
                <button
                  onClick={() => setShowFilterModal(false)}
                  className="rounded-lg bg-accent px-4 py-1.5 text-[13px] font-semibold text-white hover:opacity-90"
                >
                  Apply Filters
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Network Costs Inspection Modal */}
      {inspectNetworkResource && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
          <div className="relative w-full max-w-lg rounded-2xl border border-line bg-surface p-6 shadow-2xl">
            <button
              onClick={() => setInspectNetworkResource(null)}
              className="absolute right-4 top-4 rounded-md p-1 text-ink-3 hover:text-ink"
            >
              <Icon icon="mdi:close" className="h-5 w-5" />
            </button>

            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#7c3aed]/10 text-[#7c3aed]">
                <Icon icon="mdi:network-outline" className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-[17px] font-bold text-ink">Network Flow Costs</h3>
                <p className="font-mono text-[12.5px] text-[#7c3aed]">
                  {inspectNetworkResource}
                </p>
              </div>
            </div>

            <div className="mt-5 space-y-3">
              <div className="rounded-xl border border-line bg-sunk p-4">
                <div className="flex justify-between text-[13px]">
                  <span className="text-ink-2">Hourly Provisioning Fee</span>
                  <span className="font-mono font-bold text-ink">$32.40 / mo</span>
                </div>
                <div className="mt-2 flex justify-between text-[13px]">
                  <span className="text-ink-2">Data Processing (14.2 TB @ $0.045/GB)</span>
                  <span className="font-mono font-bold text-amber-500">$639.00 / mo</span>
                </div>
                <div className="mt-2 flex justify-between border-t border-line/60 pt-2 text-[13.5px] font-bold">
                  <span className="text-ink">Total Resource Cost</span>
                  <span className="font-mono text-ink">$671.40 / mo</span>
                </div>
              </div>

              <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/10 p-3.5 text-[12.5px] text-ink-2">
                <div className="font-semibold text-emerald-500 flex items-center gap-1">
                  <Icon icon="mdi:lightbulb-on-outline" className="h-4 w-4" />
                  FinOps Optimization Detected
                </div>
                <p className="mt-1">
                  82% of this NAT Gateway traffic flows to Amazon S3. Provisioning a free <strong>S3 VPC Gateway Endpoint</strong> bypasses the NAT Gateway entirely and saves <strong>$524/mo</strong>.
                </p>
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-2">
              <button
                onClick={() => setInspectNetworkResource(null)}
                className="rounded-lg bg-accent px-4 py-2 text-[13px] font-semibold text-white hover:opacity-90"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
