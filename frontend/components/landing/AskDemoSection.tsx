"use client";

import { useEffect, useState } from "react";
import { AskDemo, type Scenario } from "@/components/landing/AskDemo";

/** The questions themselves are static copy, so they stay here and render
 *  immediately. Only their PRICES need the server. Kept in step with the
 *  same list in app/api/landing/demos/route.ts, which prices them. */
const QUESTIONS = [
  {
    question: "An online shop for India, traffic comes in spikes",
    chips: ["web", "spiky", "medium", "india"],
  },
  {
    question: "A read-heavy API, steady traffic all day",
    chips: ["api", "steady", "medium", "india"],
  },
  {
    question: "Overnight batch jobs, interruptions are fine",
    chips: ["batch", "steady", "low", "india"],
  },
];

/**
 * Builds the demo's scenarios from one same-origin, edge-cached request.
 *
 * This used to fire three cross-origin comparison POSTs from every
 * visitor's browser -- each with its own CORS preflight, each returning a
 * full ~270 KB comparison that was reduced here to nine formatted numbers,
 * and none of them cached. The questions are hardcoded and never vary, so
 * asking a single-worker backend all three on every page view was pure
 * waste. See app/api/landing/demos/route.ts.
 */
export function AskDemoSection() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);

  useEffect(() => {
    let live = true;

    fetch("/api/landing/demos")
      .then((res) => {
        if (!res.ok) throw new Error(`demos ${res.status}`);
        return res.json() as Promise<{ scenarios: Scenario[] }>;
      })
      .then((body) => {
        if (live && body.scenarios?.length) setScenarios(body.scenarios);
      })
      .catch(() => {
        /* Leaves the em-dash placeholders below in place. */
      });

    return () => {
      live = false;
    };
  }, []);

  /* Render immediately with placeholder prices, then swap in real ones. */
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
