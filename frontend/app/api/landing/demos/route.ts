import { NextResponse } from "next/server";
import { api, comparableTotals, money } from "@/lib/api";
import type { Scenario } from "@/components/landing/AskDemo";

/**
 * The three demo scenarios, priced on the server and cached at the edge.
 *
 * Same reasoning as ../showcase/route.ts: these were three cross-origin
 * POSTs from every visitor's browser, each preceded by a CORS preflight and
 * each returning a full comparison (~270 KB) that the client reduced to
 * nine formatted numbers. The questions are hardcoded and never vary, so
 * asking them per page view was pure waste.
 */

const REVALIDATE_S = 300;

const CACHE_HEADERS = {
  "Cache-Control": `public, s-maxage=${REVALIDATE_S}, stale-while-revalidate=86400`,
};
const ERROR_HEADERS = { "Cache-Control": "public, s-maxage=10" };

const LABELS: Record<string, string> = {
  aws: "AWS",
  azure: "Microsoft Azure",
  gcp: "Google Cloud",
};

/** Kept in step with AskDemoSection's chips, which stay client-side because
 *  they are static copy rather than data. */
const QUESTIONS = [
  {
    question: "An online shop for India, traffic comes in spikes",
    chips: ["web", "spiky", "medium", "india"],
    body: {
      goal: "an online shop",
      workload_type: "web",
      traffic_pattern: "spiky",
      traffic_scale: "medium",
      storage_gb: 200,
      egress_gb: 500,
    },
  },
  {
    question: "A read-heavy API, steady traffic all day",
    chips: ["api", "steady", "medium", "india"],
    body: {
      goal: "a read-heavy API",
      workload_type: "api",
      traffic_pattern: "steady",
      traffic_scale: "medium",
      storage_gb: 100,
      egress_gb: 300,
    },
  },
  {
    question: "Overnight batch jobs, interruptions are fine",
    chips: ["batch", "steady", "low", "india"],
    body: {
      goal: "nightly batch processing",
      workload_type: "batch",
      traffic_pattern: "steady",
      traffic_scale: "low",
      storage_gb: 500,
      egress_gb: 50,
    },
  },
];

export async function GET() {
  try {
    const built = await Promise.all(
      QUESTIONS.map(async (q) => {
        try {
          const compare = await api.compare(q.body, REVALIDATE_S);
          const priced = comparableTotals(compare.clouds, "Most reliable");
          if (priced.length < 2) return null;

          return {
            question: q.question,
            chips: q.chips,
            rows: priced.map((r, i) => ({
              provider: r.provider,
              label: LABELS[r.provider] ?? r.provider,
              monthly: `${money(r.total, 0)}/mo`,
              cheapest: i === 0,
            })),
          } satisfies Scenario;
        } catch {
          // One scenario failing should not blank the other two.
          return null;
        }
      }),
    );

    const scenarios = built.filter((s): s is Scenario => s !== null);
    if (scenarios.length === 0) {
      return NextResponse.json(
        { error: "No scenario could be priced." },
        { status: 503, headers: ERROR_HEADERS },
      );
    }

    return NextResponse.json({ scenarios }, { headers: CACHE_HEADERS });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Could not reach the pricing engine." },
      { status: 503, headers: ERROR_HEADERS },
    );
  }
}
