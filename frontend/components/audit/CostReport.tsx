"use client";

import { useMemo, useState } from "react";
import type { CostRow } from "@/lib/api";
import {
  DIMENSIONS, applyFilters, group, hasDates, money, projectedMonth,
  type DateBin, type Dimension, type Filter,
} from "@/lib/costReport";
import { seriesColor } from "@/lib/seriesPalette";
import { CostChart, CHART_TYPES, type ChartType } from "./CostChart";
import { FilterBar } from "./FilterBar";

const BINS: { id: DateBin; label: string }[] = [
  { id: "day", label: "Daily" },
  { id: "week", label: "Weekly" },
  { id: "month", label: "Monthly" },
];

/**
 * The cost report.
 *
 * Filter, group, bin, chart, drill down — over a billing export the
 * person uploaded themselves.
 *
 * What it deliberately does NOT do is show a number the bill cannot
 * support. There is no amortisation toggle, because amortising a
 * commitment needs the purchase record and a CUR line does not carry
 * one; no forecast beyond a flat run-rate, because a few days of one
 * export cannot support a slope; and no blended-vs-unblended switch,
 * because most exports contain only one of the two. Each of those is a
 * real platform feature resting on data a connected account would have
 * and an uploaded CSV does not.
 */
export function CostReport({ rows, warnings }: { rows: CostRow[]; warnings: string[] }) {
  const [filters, setFilters] = useState<Filter[]>([]);
  const [dimension, setDimension] = useState<Dimension>("service");
  const [size, setSize] = useState<DateBin>("day");
  const [chart, setChart] = useState<ChartType>("stacked");
  const [drill, setDrill] = useState<string | null>(null);

  const dated = hasDates(rows);
  const filtered = useMemo(() => applyFilters(rows, filters), [rows, filters]);
  const grouped = useMemo(
    () => group(filtered, dimension, dated ? size : "month"),
    [filtered, dimension, size, dated],
  );

  const bill = rows.reduce((sum, row) => sum + row.monthly_usd, 0);
  const shown = grouped.total;
  const projection = projectedMonth(grouped, size);

  return (
    <section className="flex flex-col gap-4">
      {/* ── headline ── */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-ink">Cost report</h2>
          <p className="mt-0.5 text-xs text-ink-3">
            {shown < bill - 0.01 ? (
              <>
                <span className="font-mono text-ink-2">{money(shown)}</span> of{" "}
                <span className="font-mono">{money(bill)}</span> shown under these filters
              </>
            ) : (
              <>
                <span className="font-mono text-ink-2">{money(bill)}</span> across{" "}
                {rows.length.toLocaleString()} billed cells
              </>
            )}
          </p>
        </div>
        {projection !== null && (
          <div className="text-right">
            <div className="font-mono text-lg font-semibold text-ink">{money(projection)}</div>
            <div className="text-[11px] text-ink-3">
              at this run rate, per 30.4 days
            </div>
          </div>
        )}
      </div>

      {!dated && (
        <p className="rounded-lg border border-line bg-sunk px-3 py-2 text-[11px] leading-relaxed text-ink-2">
          This export carries no date column, so there is no series to draw —
          every view below is one snapshot. Costs over time needs{" "}
          <code className="font-mono">lineItem/UsageStartDate</code> (AWS),{" "}
          <code className="font-mono">usage_start_time</code> (GCP) or{" "}
          <code className="font-mono">Date</code> (Azure).
        </p>
      )}

      <FilterBar rows={rows} filters={filters} onChange={setFilters} />

      {/* ── controls ── */}
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-y border-line py-2">
        <Control label="Group by">
          {DIMENSIONS.map((d) => (
            <Pill
              key={d.id}
              active={dimension === d.id}
              onClick={() => { setDimension(d.id); setDrill(null); }}
            >
              {d.label}
            </Pill>
          ))}
        </Control>

        {dated && (
          <Control label="Bin">
            {BINS.map((b) => (
              <Pill key={b.id} active={size === b.id} onClick={() => setSize(b.id)}>
                {b.label}
              </Pill>
            ))}
          </Control>
        )}

        <Control label="Chart">
          {CHART_TYPES.filter((c) => dated || c.id === "donut" || c.id === "stacked")
            .map((c) => (
              <Pill key={c.id} active={chart === c.id} onClick={() => setChart(c.id)}>
                {c.label}
              </Pill>
            ))}
        </Control>
      </div>

      <div className="rounded-xl border border-line bg-surface p-3">
        <CostChart grouped={grouped} type={dated ? chart : "donut"} size={size} />
        {grouped.partial.some(Boolean) && chart === "stacked" && (
          <p className="mt-1 px-1 text-[11px] text-ink-3">
            Hatched bars are periods the export only partly covers — they are
            short because the data stops, not because spend fell.
          </p>
        )}
      </div>

      {/* ── the table ── */}
      <div className="overflow-hidden rounded-xl border border-line">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-line bg-sunk text-left">
              <th className="px-3 py-2 text-xs font-semibold text-ink-2">
                {DIMENSIONS.find((d) => d.id === dimension)?.label}
              </th>
              <th className="w-[38%] px-3 py-2 text-xs font-semibold text-ink-2">
                Share
              </th>
              <th className="px-3 py-2 text-right text-xs font-semibold text-ink-2">
                Cost
              </th>
              <th className="px-3 py-2 text-right text-xs font-semibold text-ink-2">
                %
              </th>
            </tr>
          </thead>
          <tbody>
            {grouped.series.map((one, si) => {
              const pct = shown > 0 ? (one.total / shown) * 100 : 0;
              const isOpen = drill === one.key;
              return (
                <tr
                  key={one.key}
                  onClick={() => setDrill(isOpen ? null : one.key)}
                  className={`cursor-pointer border-b border-line last:border-0 transition-colors ${
                    isOpen ? "bg-accent-wash" : "hover:bg-sunk"
                  }`}
                >
                  <td className="px-3 py-2">
                    <span className="flex items-center gap-2">
                      <span
                        className="h-2.5 w-2.5 shrink-0 rounded-[2px]"
                        style={{ background: seriesColor(one.key, si) }}
                      />
                      <span className="text-ink">{one.key}</span>
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <span className="block h-1.5 w-full overflow-hidden rounded-full bg-sunk">
                      <span
                        className="block h-full rounded-full"
                        style={{
                          width: `${Math.max(pct, 0.5)}%`,
                          background: seriesColor(one.key, si),
                        }}
                      />
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-ink">
                    {money(one.total)}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-xs text-ink-3">
                    {pct.toFixed(1)}%
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr className="border-t border-line-strong bg-sunk">
              <td className="px-3 py-2 text-xs font-semibold text-ink-2" colSpan={2}>
                Total
                {grouped.otherCount > 0 && (
                  <span className="ml-1.5 font-normal text-ink-3">
                    — {grouped.otherCount} smaller group
                    {grouped.otherCount === 1 ? "" : "s"} folded into Other
                  </span>
                )}
              </td>
              <td className="px-3 py-2 text-right font-mono font-semibold text-ink">
                {money(shown)}
              </td>
              <td className="px-3 py-2" />
            </tr>
          </tfoot>
        </table>
      </div>

      {drill && (
        <DrillDown
          rows={filtered}
          dimension={dimension}
          value={drill}
          onClose={() => setDrill(null)}
        />
      )}

      {warnings.length > 0 && (
        <ul className="flex flex-col gap-1.5">
          {warnings.map((warning) => (
            <li
              key={warning}
              className="border-l-2 border-caution py-0.5 pl-2.5 text-[11px] leading-relaxed text-ink-2"
            >
              {warning}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/** One group, opened onto the other two axes. The question after "EC2 is
 *  our biggest line" is always "which EC2, and where" — and that is a
 *  regrouping of rows already in hand, not another request. */
function DrillDown({
  rows, dimension, value, onClose,
}: {
  rows: CostRow[];
  dimension: Dimension;
  value: string;
  onClose: () => void;
}) {
  const others = DIMENSIONS.filter((d) => d.id !== dimension);
  const inGroup = rows.filter(
    (row) => (row[dimension] || "Not specified") === value,
  );
  const total = inGroup.reduce((sum, row) => sum + row.monthly_usd, 0);

  return (
    <div className="rounded-xl border border-accent-line bg-accent-wash/40 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-xs font-semibold text-ink">
          {value}
          <span className="ml-2 font-mono font-normal text-ink-2">{money(total)}</span>
        </h3>
        <button
          type="button"
          onClick={onClose}
          className="text-[11px] text-ink-3 hover:text-ink-2"
        >
          Close
        </button>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {others.map((other) => {
          const inner = group(inGroup, other.id, "month", 6);
          return (
            <div key={other.id}>
              <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-ink-3">
                by {other.label}
              </div>
              <ul className="flex flex-col gap-1">
                {inner.series.map((one, si) => (
                  <li
                    key={one.key}
                    className="flex items-center justify-between gap-3 text-xs"
                  >
                    <span className="flex min-w-0 items-center gap-1.5">
                      <span
                        className="h-2 w-2 shrink-0 rounded-[2px]"
                        style={{ background: seriesColor(one.key, si) }}
                      />
                      <span className="truncate text-ink-2">{one.key}</span>
                    </span>
                    <span className="shrink-0 font-mono text-ink-2">
                      {money(one.total)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Control({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[11px] font-semibold uppercase tracking-wide text-ink-3">
        {label}
      </span>
      <div className="flex items-center gap-1">{children}</div>
    </div>
  );
}

function Pill({
  active, onClick, children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-md px-2 py-1 text-xs transition-colors ${
        active
          ? "bg-accent font-semibold text-white"
          : "text-ink-3 hover:bg-sunk hover:text-ink-2"
      }`}
    >
      {children}
    </button>
  );
}
