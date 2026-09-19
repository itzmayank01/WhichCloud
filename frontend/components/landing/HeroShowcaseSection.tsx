"use client";

import { useEffect, useState } from "react";
import { HeroShowcase, type ShowcaseData } from "@/components/landing/HeroShowcase";
import { api } from "@/lib/api";

const LABEL: Record<string, string> = {
  aws: "AWS",
  azure: "Microsoft Azure",
  gcp: "Google Cloud",
};

function Skeleton() {
  return (
    <div className="space-y-4">
      <div className="animate-pulse rounded-xl border border-line bg-sunk" style={{ height: 300 }} />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="animate-pulse rounded-xl border border-line bg-sunk" style={{ height: 200 }} />
        <div className="animate-pulse rounded-xl border border-line bg-sunk" style={{ height: 200 }} />
      </div>
    </div>
  );
}

/**
 * Fills the hero showcase from one comparison.
 *
 * Moved to client-side so ISR regeneration never waits on three parallel
 * API calls. Page renders immediately with skeleton, then hydrates with data.
 */
export function HeroShowcaseSection() {
  const [data, setData] = useState<ShowcaseData | null>(null);

  useEffect(() => {
    Promise.all([
      api.compare(
        {
          goal: "a video streaming API",
          workload_type: "api",
          traffic_pattern: "steady",
          traffic_scale: "high",
          storage_gb: 2000,
          egress_gb: 5000,
        },
        300,
      ),
      api.techniques().catch(() => ({ count: 0, techniques: [] })),
      api.health().catch(() => ({ prices: 0, providers: [] as string[] })),
    ])
      .then(([compare, techs, health]) => {
        const balanced = Object.entries(compare.clouds)
          .map(([id, options]) => ({
            id,
            option: options.find((o) => o.label === "Most reliable") ?? options[0],
          }))
          .filter((r) => r.option);

        if (balanced.length < 2) return;

        const whole = balanced.filter((r) => r.option.complete);
        if (whole.length === 0) return;

        const cheapest = whole.reduce((a, b) =>
          a.option.monthly_usd <= b.option.monthly_usd ? a : b,
        );
        const win = cheapest.option;

        const richest = whole.reduce((a, b) =>
          (b.option.applied?.length ?? 0) > (a.option.applied?.length ?? 0) ? b : a,
        );

        const shared = balanced
          .map((r) => new Set(r.option.items.map((i) => i.label.replace(/ ×.*$/, ""))))
          .reduce((a, b) => new Set([...a].filter((x) => b.has(x))));

        const categories = [...shared].sort();

        setData({
          chart: {
            categories,
            clouds: balanced
              .sort((a, b) => a.option.monthly_usd - b.option.monthly_usd)
              .map((r) => {
                const segments = categories.map((label) => ({
                  label,
                  value: r.option.items
                    .filter((i) => i.label.replace(/ ×.*$/, "") === label)
                    .reduce((sum, i) => sum + i.monthly_usd, 0),
                }));
                return {
                  id: r.id,
                  label: LABEL[r.id] ?? r.id,
                  total: segments.reduce((sum, s) => sum + s.value, 0),
                  segments,
                };
              }),
          },
          quote: "a video streaming API for India, busy all day",
          breakdown: [...win.items]
            .sort((a, b) => b.monthly_usd - a.monthly_usd)
            .slice(0, 5)
            .map((i) => ({
              label: i.label.replace(/ ×.*$/, ""),
              sku: i.sku ?? "—",
              monthly: i.monthly_usd,
            })),
          total: win.monthly_usd,
          saved: richest.option.measured_saving_usd,
          techniquesTested: techs.count ?? 0,
          catalogSize: health.prices ?? 0,
          applied: (richest.option.applied ?? [])
            .filter((a) => (a.saved_monthly_usd ?? 0) > 0)
            .sort((a, b) => (b.saved_monthly_usd ?? 0) - (a.saved_monthly_usd ?? 0))
            .slice(0, 4)
            .map((a) => ({
              name: a.name,
              saved: a.saved_monthly_usd ?? 0,
              versus: a.versus_sku ?? "the default",
              category: a.category ?? "compute",
            })),
          advisory: (richest.option.advisory ?? []).slice(0, 3).map((a) => a.name),
        });
      })
      .catch(() => {
        /* Renders nothing on any fetch failure */
      });
  }, []);

  return data ? <HeroShowcase data={data} /> : <Skeleton />;
}
