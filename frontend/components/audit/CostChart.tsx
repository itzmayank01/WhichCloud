"use client";

import { useMemo, useState } from "react";
import { axisMoney, money, type Grouped, type DateBin } from "@/lib/costReport";
import { seriesColor } from "@/lib/seriesPalette";

export type ChartType = "stacked" | "line" | "area" | "donut";

export const CHART_TYPES: { id: ChartType; label: string }[] = [
  { id: "stacked", label: "Stacked bar" },
  { id: "line", label: "Line" },
  { id: "area", label: "Area" },
  { id: "donut", label: "Share" },
];

/* Hand-drawn SVG rather than a charting library: the published artifact
   runs under a CSP that blocks external scripts, the shapes here are
   rectangles and polylines, and a dependency would be several hundred
   kilobytes to draw them. */

const PAD = { top: 12, right: 16, bottom: 28, left: 56 };
const HEIGHT = 260;

function niceCeiling(value: number): number {
  if (value <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  for (const step of [1, 2, 2.5, 5, 10]) {
    if (value <= step * magnitude) return step * magnitude;
  }
  return 10 * magnitude;
}

function tickLabel(bucket: string, size: DateBin): string {
  if (!bucket) return "undated";
  const date = new Date(`${bucket}T00:00:00Z`);
  if (size === "month") {
    return date.toLocaleDateString("en-US", { month: "short", year: "2-digit", timeZone: "UTC" });
  }
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}

export function CostChart({
  grouped, type, size,
}: {
  grouped: Grouped;
  type: ChartType;
  size: DateBin;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const { buckets, series } = grouped;

  /* Stacked and area charts are read against the column total; line and
     donut are read against the largest single group. Scaling all four the
     same way would squash a line chart into the bottom of its own axis. */
  const max = useMemo(() => {
    if (type === "line") {
      return niceCeiling(Math.max(...series.flatMap((s) => s.points), 0));
    }
    return niceCeiling(
      Math.max(...buckets.map((_, i) =>
        series.reduce((sum, s) => sum + s.points[i], 0)), 0),
    );
  }, [buckets, series, type]);

  if (buckets.length === 0 || series.length === 0) {
    return (
      <div className="flex h-[260px] items-center justify-center text-sm text-ink-3">
        Nothing to chart under these filters.
      </div>
    );
  }

  if (type === "donut") return <Donut grouped={grouped} />;

  const width = 720;
  const plotW = width - PAD.left - PAD.right;
  const plotH = HEIGHT - PAD.top - PAD.bottom;
  const bandW = plotW / buckets.length;
  const x = (i: number) => PAD.left + bandW * i + bandW / 2;
  const y = (value: number) => PAD.top + plotH - (value / max) * plotH;

  const gridlines = [0, 0.25, 0.5, 0.75, 1].map((f) => f * max);

  const drawTick = (bucket: string, i: number) => (
    <text
      key={bucket || `t-${i}`}
      x={x(i)} y={HEIGHT - 8}
      textAnchor="middle" fontSize={11} fill="var(--ink-3)"
    >
      {tickLabel(bucket, size)}
    </text>
  );

  /* Every series' running base, so a stack sits on the one below it. */
  const bases: number[][] = [];
  const running = new Array(buckets.length).fill(0);
  for (const one of series) {
    bases.push([...running]);
    one.points.forEach((value, i) => { running[i] += value; });
  }

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${width} ${HEIGHT}`}
        className="w-full"
        style={{ height: HEIGHT }}
        role="img"
        aria-label={`Cost by ${size}`}
        onMouseLeave={() => setHover(null)}
      >
        <defs>
          <pattern id="partial-hatch" width={6} height={6}
            patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width={6} height={6} fill="var(--surface)" opacity={0.55} />
            <line x1={0} y1={0} x2={0} y2={6} stroke="var(--surface)" strokeWidth={3} />
          </pattern>
        </defs>

        {gridlines.map((value) => (
          <g key={value}>
            <line
              x1={PAD.left} x2={width - PAD.right}
              y1={y(value)} y2={y(value)}
              stroke="var(--border)" strokeWidth={1}
            />
            <text
              x={PAD.left - 8} y={y(value) + 4}
              textAnchor="end" fontSize={11} fill="var(--ink-3)"
            >
              {axisMoney(value)}
            </text>
          </g>
        ))}

        {type === "stacked" && series.map((one, si) => (
          <g key={one.key}>
            {one.points.map((value, i) => value <= 0 ? null : (
              <g key={i}>
                <rect
                  x={PAD.left + bandW * i + bandW * 0.15}
                  width={bandW * 0.7}
                  y={y(bases[si][i] + value)}
                  height={Math.max(0, y(bases[si][i]) - y(bases[si][i] + value))}
                  fill={seriesColor(one.key, si)}
                  opacity={hover === null || hover === i ? 1 : 0.35}
                />
                {/* A week the export only half covers draws as a short bar,
                    which a reader takes for a spending drop. Hatched, so
                    the shortfall reads as missing data rather than saving. */}
                {grouped.partial[i] && (
                  <rect
                    x={PAD.left + bandW * i + bandW * 0.15}
                    width={bandW * 0.7}
                    y={y(bases[si][i] + value)}
                    height={Math.max(0, y(bases[si][i]) - y(bases[si][i] + value))}
                    fill="url(#partial-hatch)"
                    pointerEvents="none"
                  />
                )}
              </g>
            ))}
          </g>
        ))}

        {type === "area" && series.map((one, si) => {
          const top = one.points.map((v, i) => `${x(i)},${y(bases[si][i] + v)}`);
          const bottom = one.points.map((_, i) =>
            `${x(buckets.length - 1 - i)},${y(bases[si][buckets.length - 1 - i])}`);
          return (
            <polygon
              key={one.key}
              points={[...top, ...bottom].join(" ")}
              fill={seriesColor(one.key, si)}
              opacity={hover === null ? 0.85 : 0.5}
            />
          );
        })}

        {type === "line" && series.map((one, si) => (
          <polyline
            key={one.key}
            points={one.points.map((v, i) => `${x(i)},${y(v)}`).join(" ")}
            fill="none"
            stroke={seriesColor(one.key, si)}
            strokeWidth={2}
            strokeLinejoin="round"
            opacity={hover === null ? 1 : 0.55}
          />
        ))}

        {/* One hit target per column, above the marks: hovering a thin
            line or a 2px band is a precision task nobody should be set. */}
        {buckets.map((bucket, i) => (
          <rect
            key={bucket || `undated-${i}`}
            x={PAD.left + bandW * i} y={PAD.top}
            width={bandW} height={plotH}
            fill="transparent"
            onMouseEnter={() => setHover(i)}
          />
        ))}
        {hover !== null && (
          <line
            x1={x(hover)} x2={x(hover)} y1={PAD.top} y2={PAD.top + plotH}
            stroke="var(--ink-3)" strokeWidth={1} strokeDasharray="3 3"
            pointerEvents="none"
          />
        )}

        {buckets.map((bucket, i) => {
          /* Thin out the labels rather than letting them overlap: a month
             of daily bars cannot carry 30 legible dates at this width.

             The last tick is worth drawing -- a reader wants to know where
             the series ends -- but only when it clears the one before it.
             Forcing it unconditionally overprinted "Mar 29" onto "Mar 30"
             whenever the count was not a clean multiple of the step. */
          const every = Math.ceil(buckets.length / 8);
          const last = buckets.length - 1;
          const onStep = i % every === 0;
          if (i === last) {
            if (onStep) return drawTick(bucket, i);
            if (last - Math.floor(last / every) * every < every / 2) return null;
          } else if (!onStep) {
            return null;
          }
          return drawTick(bucket, i);
        })}
      </svg>

      {hover !== null && (
        <Tooltip grouped={grouped} at={hover} size={size} />
      )}
    </div>
  );
}

function Tooltip({ grouped, at, size }: { grouped: Grouped; at: number; size: DateBin }) {
  const entries = grouped.series
    .map((one, si) => ({ key: one.key, value: one.points[at], color: seriesColor(one.key, si) }))
    .filter((e) => e.value > 0)
    .sort((a, b) => b.value - a.value);
  const total = entries.reduce((sum, e) => sum + e.value, 0);

  return (
    <div
      className="pointer-events-none absolute right-2 top-2 z-10 min-w-[180px] rounded-lg border border-line bg-surface p-3 shadow-lg"
    >
      <div className="mb-2 flex items-baseline justify-between gap-4 border-b border-line pb-1.5">
        <span className="text-xs font-semibold text-ink">
          {tickLabel(grouped.buckets[at], size)}
        </span>
        <span className="font-mono text-xs font-semibold text-ink">{money(total)}</span>
      </div>
      {grouped.partial[at] && (
        <p className="-mt-1 mb-2 text-[10px] leading-snug text-caution">
          Partial period — the export does not cover all of it.
        </p>
      )}
      <ul className="flex flex-col gap-1">
        {entries.slice(0, 8).map((entry) => (
          <li key={entry.key} className="flex items-center justify-between gap-3 text-[11px]">
            <span className="flex min-w-0 items-center gap-1.5">
              <span
                className="h-2 w-2 shrink-0 rounded-[2px]"
                style={{ background: entry.color }}
              />
              <span className="truncate text-ink-2">{entry.key}</span>
            </span>
            <span className="shrink-0 font-mono text-ink-2">{money(entry.value)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Donut({ grouped }: { grouped: Grouped }) {
  const total = grouped.total || 1;
  const R = 100;
  const r = 62;

  /* Each slice's start angle, accumulated up front rather than by
     mutating a counter inside the map. The running total is derived
     state, and building it during render is the kind of thing that goes
     wrong quietly the first time React renders the list twice. */
  const starts: number[] = [];
  grouped.series.reduce((angle, one) => {
    starts.push(angle);
    return angle + (one.total / total) * Math.PI * 2;
  }, -Math.PI / 2);

  return (
    <div className="flex h-[260px] items-center justify-center gap-8">
      <svg viewBox="-110 -110 220 220" style={{ width: 220, height: 220 }} role="img"
        aria-label="Share of spend">
        {grouped.series.map((one, si) => {
          const sweep = (one.total / total) * Math.PI * 2;
          const [a0, a1] = [starts[si], starts[si] + sweep];
          if (sweep <= 0) return null;
          /* A single group owning the whole bill would close the arc onto
             its own start point and vanish; draw it as a ring instead. */
          if (sweep >= Math.PI * 2 - 1e-6) {
            return (
              <circle key={one.key} cx={0} cy={0} r={(R + r) / 2}
                fill="none" stroke={seriesColor(one.key, si)} strokeWidth={R - r} />
            );
          }
          const big = sweep > Math.PI ? 1 : 0;
          const p = (radius: number, a: number) =>
            `${(radius * Math.cos(a)).toFixed(2)},${(radius * Math.sin(a)).toFixed(2)}`;
          return (
            <path
              key={one.key}
              d={`M ${p(R, a0)} A ${R} ${R} 0 ${big} 1 ${p(R, a1)} `
               + `L ${p(r, a1)} A ${r} ${r} 0 ${big} 0 ${p(r, a0)} Z`}
              fill={seriesColor(one.key, si)}
            />
          );
        })}
      </svg>
      <ul className="flex max-h-[240px] flex-col gap-1.5 overflow-y-auto pr-2">
        {grouped.series.map((one, si) => (
          <li key={one.key} className="flex items-center justify-between gap-6 text-xs">
            <span className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-[2px]"
                style={{ background: seriesColor(one.key, si) }} />
              <span className="text-ink-2">{one.key}</span>
            </span>
            <span className="font-mono text-ink-3">
              {((one.total / total) * 100).toFixed(1)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
