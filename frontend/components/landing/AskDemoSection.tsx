import { AskDemo, type Scenario } from "@/components/landing/AskDemo";
import { api, comparableTotals, money } from "@/lib/api";

/**
 * Builds the demo's scenarios out of the live catalog.
 *
 * Every price the animation shows is one the engine returned for that
 * question, so the panel is a recording of the product rather than a mock-up
 * of it. If the API is unreachable the section does not render, which is the
 * right failure: a demo of pricing with invented prices is worse than no
 * demo.
 */

const LABELS: Record<string, string> = {
  aws: "AWS",
  azure: "Microsoft Azure",
  gcp: "Google Cloud",
};

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

async function build(q: (typeof QUESTIONS)[number]): Promise<Scenario | null> {
  try {
    /* Cached: the landing page asks these same fixed questions on every
       visit, so one engine run per five minutes serves everyone. */
    const compare = await api.compare(q.body, 300);

    /* Compared on the services every cloud prices, not on raw totals.
       Requiring every cloud to be complete used to hide this section
       entirely the moment AWS gained components the others have no
       adapter for; ranking the raw totals instead would have been worse,
       since a cloud missing eleven components looks cheapest precisely
       because it is missing them. */
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
    };
  } catch {
    return null;
  }
}

export async function AskDemoSection() {
  const built = await Promise.all(QUESTIONS.map(build));
  const scenarios = built.filter((s): s is Scenario => s !== null);
  if (!scenarios.length) return null;
  return <AskDemo scenarios={scenarios} />;
}
