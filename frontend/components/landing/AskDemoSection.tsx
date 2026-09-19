"use client";

import { useEffect, useState } from "react";
import { AskDemo, type Scenario } from "@/components/landing/AskDemo";
import { api, comparableTotals, money } from "@/lib/api";

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

/**
 * Builds the demo's scenarios out of the live catalog.
 *
 * Moved to client-side so ISR regeneration never waits on three parallel
 * comparison calls. Page renders immediately, then hydrates with data once it arrives.
 */
export function AskDemoSection() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);

  useEffect(() => {
    Promise.all(
      QUESTIONS.map(async (q) => {
        try {
          const compare = await api.compare(q.body, 300);
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
      }),
    )
      .then((built) => {
        const filtered = built.filter((s): s is Scenario => s !== null);
        if (filtered.length > 0) {
          setScenarios(filtered);
        }
      })
      .catch(() => {
        /* Renders nothing on any fetch failure */
      });
  }, []);

  /* Render immediately with placeholder data, then swap in real data once it loads. */
  const displayScenarios =
    scenarios.length > 0
      ? scenarios
      : QUESTIONS.map((q) => ({
          question: q.question,
          chips: q.chips,
          rows: [
            { provider: "aws", label: "AWS", monthly: "—", cheapest: false },
            { provider: "azure", label: "Microsoft Azure", monthly: "—", cheapest: false },
            { provider: "gcp", label: "Google Cloud", monthly: "—", cheapest: false },
          ],
        }));

  return (
    <div className={scenarios.length === 0 ? "opacity-50" : ""}>
      <AskDemo scenarios={displayScenarios} />
    </div>
  );
}
