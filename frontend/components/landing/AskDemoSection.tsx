import { AskDemo, type Scenario } from "@/components/landing/AskDemo";
import { api, money } from "@/lib/api";

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
    const compare = await api.compare(q.body);
    const priced = Object.entries(compare.clouds)
      .map(([provider, options]) => ({
        provider,
        option: options.find((o) => o.label === "Balanced") ?? options[0],
      }))
      .filter((r) => r.option?.complete);

    if (priced.length < 2) return null;

    const cheapest = priced.reduce((a, b) =>
      a.option.monthly_usd <= b.option.monthly_usd ? a : b,
    );

    return {
      question: q.question,
      chips: q.chips,
      rows: priced
        .sort((a, b) => a.option.monthly_usd - b.option.monthly_usd)
        .map((r) => ({
          provider: r.provider,
          label: LABELS[r.provider] ?? r.provider,
          monthly: `${money(r.option.monthly_usd, 0)}/mo`,
          cheapest: r.provider === cheapest.provider,
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
