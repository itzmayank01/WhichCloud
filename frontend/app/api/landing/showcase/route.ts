import { NextResponse } from "next/server";
import { api } from "@/lib/api";
import type { ShowcaseData } from "@/components/landing/HeroShowcase";

/**
 * The hero showcase's data, shaped on the server and cached at the edge.
 *
 * This used to run in the browser: three cross-origin calls per visitor
 * (/compare, /techniques, /health), of which /compare alone returns ~270 KB
 * that the client then reduced to the few dozen numbers below. Every one of
 * them was uncached -- `api.compare(body, 300)` passes `next: { revalidate }`,
 * which is a SERVER-side fetch extension that the browser ignores outright,
 * and a POST is never served from the HTTP cache anyway. So the landing page
 * asked a single-worker backend the same fixed question on every single page
 * view, each POST preceded by its own CORS preflight.
 *
 * Here it is one same-origin GET: no preflight, a few KB instead of ~270,
 * the reduction already done, and `s-maxage` lets Vercel's CDN serve
 * everyone from the edge between refreshes. `stale-while-revalidate` is the
 * part that matters most on a free-tier backend that sleeps -- once warm,
 * nobody ever waits for a refetch again; they get the previous answer
 * instantly while it updates behind them.
 */

const REVALIDATE_S = 300;

// Deliberately NOT `dynamic = "force-static"`. That would build this route
// at deploy time, which couples every Vercel build to a backend that sleeps
// after 15 minutes idle -- a cold one would stall or fail the build. Caching
// via headers keeps the CDN benefit without that coupling.
const CACHE_HEADERS = {
  "Cache-Control": `public, s-maxage=${REVALIDATE_S}, stale-while-revalidate=86400`,
};

// A failure must not be cached for five minutes -- that would turn one
// unlucky request into five minutes of a broken section for everyone.
const ERROR_HEADERS = { "Cache-Control": "public, s-maxage=10" };

const LABEL: Record<string, string> = {
  aws: "AWS",
  azure: "Microsoft Azure",
  gcp: "Google Cloud",
};

const WORKLOAD = {
  goal: "a video streaming API",
  workload_type: "api",
  traffic_pattern: "steady",
  traffic_scale: "high",
  storage_gb: 2000,
  egress_gb: 5000,
} as const;

export async function GET() {
  try {
    const [compare, techs, health] = await Promise.all([
      api.compare({ ...WORKLOAD }, REVALIDATE_S),
      // These two carry their own revalidate windows inside lib/api.ts.
      api.techniques().catch(() => ({ count: 0, techniques: [] })),
      api.health().catch(() => ({ prices: 0, providers: [] as string[] })),
    ]);

    const balanced = Object.entries(compare.clouds)
      .map(([id, options]) => ({
        id,
        option: options.find((o) => o.label === "Most reliable") ?? options[0],
      }))
      .filter((r) => r.option);

    const whole = balanced.filter((r) => r.option.complete);
    if (balanced.length < 2 || whole.length === 0) {
      return NextResponse.json(
        { error: "The comparison came back without two complete options." },
        { status: 503, headers: ERROR_HEADERS },
      );
    }

    const win = whole.reduce((a, b) =>
      a.option.monthly_usd <= b.option.monthly_usd ? a : b,
    ).option;

    const richest = whole.reduce((a, b) =>
      (b.option.applied?.length ?? 0) > (a.option.applied?.length ?? 0) ? b : a,
    );

    const shared = balanced
      .map((r) => new Set(r.option.items.map((i) => i.label.replace(/ ×.*$/, ""))))
      .reduce((a, b) => new Set([...a].filter((x) => b.has(x))));

    const categories = [...shared].sort();

    const data: ShowcaseData = {
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
    };

    return NextResponse.json(data, { headers: CACHE_HEADERS });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Could not reach the pricing engine." },
      { status: 503, headers: ERROR_HEADERS },
    );
  }
}
