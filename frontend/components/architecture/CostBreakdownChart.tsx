"use client";

import { useState } from "react";
import type { Node } from "@/lib/api";
import { money } from "@/lib/api";

/**
 * The bill, by category. `option.topology.nodes` carries ~24 `kind` values
 * server-side (compute, database, nat, dns, kms...) — too granular to chart
 * legibly, so this buckets them into six macro categories before drawing
 * anything. Colors come from the dataviz skill's validated default
 * categorical palette (checked this session: `HeroShowcase.tsx`'s decorative
 * landing-page ramp fails the CVD/normal-vision floors hard — not safe for a
 * chart people act on), assigned in fixed rank order so the biggest category
 * always gets the same color regardless of which categories are present.
 */

type Bucket = { key: string; label: string; value: number };

const BUCKETS: { key: string; label: string; kinds: string[] }[] = [
  { key: "compute", label: "Compute", kinds: ["compute", "cache"] },
  { key: "database", label: "Database", kinds: ["database", "database_replica"] },
  { key: "storage", label: "Storage", kinds: ["storage", "backup"] },
  {
    key: "network",
    label: "Networking",
    kinds: ["network", "loadbalancer", "nat", "dns", "tls", "flowlogs"],
  },
  {
    key: "security",
    label: "Security & ops",
    kinds: ["waf", "audit", "kms", "auth", "threat", "posture", "monitoring", "tracing"],
  },
  { key: "other", label: "Other", kinds: [] }, // catch-all: streaming, kafka, search, warehouse...
];

/** Validated this session: `node scripts/validate_palette.js` — all checks
 * pass for these six in fixed order (light mode; this app has no dark mode). */
const COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"];

function bucketize(nodes: Node[]): Bucket[] {
  const totals = new Map<string, number>();
  for (const node of nodes) {
    if (!node.priced || node.kind === "client") continue;
    const bucket = BUCKETS.find((b) => b.kinds.includes(node.kind)) ?? BUCKETS[BUCKETS.length - 1];
    totals.set(bucket.key, (totals.get(bucket.key) ?? 0) + node.monthly_usd);
  }
  return BUCKETS.map((b) => ({ key: b.key, label: b.label, value: totals.get(b.key) ?? 0 }))
    .filter((b) => b.value > 0)
    .sort((a, b) => b.value - a.value);
}

export function CostBreakdownChart({ nodes }: { nodes: Node[] }) {
  const buckets = bucketize(nodes);
  const [active, setActive] = useState<string | null>(null);
  const total = buckets.reduce((sum, b) => sum + b.value, 0);
  if (total === 0 || buckets.length === 0) return null;

  const colorFor = (key: string) => {
    const i = buckets.findIndex((b) => b.key === key);
    return COLORS[i] ?? "#c3cad6";
  };

  return (
    <div className="mt-2">
      <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-ink-3">
        Cost distribution
      </p>

      {/* single stacked bar — the mark is the hit target, hover/focus lifts
          the segment and shows category + value; the legend below repeats
          every value directly so nothing is hover-only */}
      <div
        className="relative mt-3 flex h-8 w-full overflow-hidden rounded-md"
        role="img"
        aria-label={`Cost distribution: ${buckets.map((b) => `${b.label} ${money(b.value, 2)}`).join(", ")}`}
      >
        {buckets.map((b) => {
          const pct = (b.value / total) * 100;
          const isActive = active === b.key;
          return (
            <div
              key={b.key}
              tabIndex={0}
              className="group relative flex items-center justify-center outline-none transition-[filter] duration-150"
              style={{
                width: `${pct}%`,
                background: colorFor(b.key),
                filter: isActive ? "brightness(1.08)" : "none",
                boxShadow: isActive ? "inset 0 0 0 2px rgba(255,255,255,.6)" : "none",
              }}
              onMouseEnter={() => setActive(b.key)}
              onMouseLeave={() => setActive(null)}
              onFocus={() => setActive(b.key)}
              onBlur={() => setActive(null)}
            >
              {pct >= 8 && (
                <span className="pointer-events-none select-none font-mono text-[11px] font-semibold text-white/95">
                  {Math.round(pct)}%
                </span>
              )}
              {isActive && (
                <div className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-2 -translate-x-1/2 whitespace-nowrap rounded-md bg-ink px-2.5 py-1.5 text-[12px] font-medium text-white shadow-lg">
                  {b.label} · {money(b.value, 2)}
                  <span className="ml-1 text-white/70">({Math.round(pct)}%)</span>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* legend — every value stated directly, not gated behind hover
          (the 3 mid-lightness colors above sit below 3:1 contrast on the
          chart surface, so per the dataviz relief rule this legend, plus the
          line-item table beneath it, is what keeps them legible) */}
      <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1.5 sm:grid-cols-3">
        {buckets.map((b) => (
          <button
            key={b.key}
            type="button"
            className="flex items-center gap-2 rounded px-1 py-0.5 text-left transition-colors hover:bg-sunk"
            onMouseEnter={() => setActive(b.key)}
            onMouseLeave={() => setActive(null)}
            onFocus={() => setActive(b.key)}
            onBlur={() => setActive(null)}
          >
            <span
              className="h-2.5 w-2.5 shrink-0 rounded-[2px]"
              style={{ background: colorFor(b.key), opacity: active && active !== b.key ? 0.4 : 1 }}
            />
            <span className="truncate text-[12.5px] text-ink-2">{b.label}</span>
            <span className="tnum ml-auto shrink-0 font-mono text-[12px] font-semibold text-ink">
              {money(b.value, 2)}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
