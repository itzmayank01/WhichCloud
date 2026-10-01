"use client";

import { useCallback, useEffect, useState } from "react";
import { HeroShowcase, type ShowcaseData } from "@/components/landing/HeroShowcase";
import { ShimmerBlock } from "@/components/ui/ShimmerBlock";
import { api } from "@/lib/api";

const LABEL: Record<string, string> = {
  aws: "AWS",
  azure: "Microsoft Azure",
  gcp: "Google Cloud",
};

//: Render's free tier sleeps the backend after 15 minutes idle; the first
//: request after that wakes it, which the client already retries through
//: (see fetchThroughWake in lib/api.ts) but can still take the better part
//: of a minute. Said here rather than left silent, same reasoning as the
//: AWS connect page's identical wait.
const SLOW_HINT_DELAY_MS = 6000;

function Skeleton({ slow }: { slow: boolean }) {
  return (
    <div className="space-y-4">
      <ShimmerBlock height={300} />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <ShimmerBlock height={200} />
        <ShimmerBlock height={200} />
      </div>
      {slow && (
        <p className="text-center text-[12.5px] text-ink-3">
          Waking up the pricing engine&hellip; first load after a few idle
          minutes can take up to a minute.
        </p>
      )}
    </div>
  );
}

function LoadError({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-line bg-canvas px-6 py-10 text-center">
      <p className="text-[13.5px] text-ink-2">
        Couldn&apos;t load the live example. The pricing engine may still be
        waking up, or the request timed out.
      </p>
      <button
        onClick={onRetry}
        className="rounded-lg border border-line bg-surface px-3 py-1.5 text-[12.5px] font-medium text-ink-2 hover:bg-sunk hover:text-ink"
      >
        Retry
      </button>
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
  const [failed, setFailed] = useState(false);
  const [slow, setSlow] = useState(false);
  // Bumped to re-run the effect below from the retry button, without
  // duplicating the fetch-and-shape logic in two places.
  const [attempt, setAttempt] = useState(0);

  const retry = useCallback(() => {
    setFailed(false);
    setSlow(false);
    setAttempt((n) => n + 1);
  }, []);

  useEffect(() => {
    // `failed`/`slow` are reset by retry() before it bumps `attempt`, so
    // the initial mount (where both already default to false) needs no
    // reset here.
    const slowTimer = setTimeout(() => setSlow(true), SLOW_HINT_DELAY_MS);

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

        if (balanced.length < 2) {
          setFailed(true);
          return;
        }

        const whole = balanced.filter((r) => r.option.complete);
        if (whole.length === 0) {
          setFailed(true);
          return;
        }

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
        setFailed(true);
      })
      .finally(() => {
        clearTimeout(slowTimer);
      });

    return () => clearTimeout(slowTimer);
  }, [attempt]);

  if (data) return <HeroShowcase data={data} />;
  if (failed) return <LoadError onRetry={retry} />;
  return <Skeleton slow={slow} />;
}
