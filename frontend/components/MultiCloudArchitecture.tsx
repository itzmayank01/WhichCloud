"use client";

import { useState } from "react";
import { PricedDiagram } from "@/components/PricedDiagram";
import { money, type Option } from "@/lib/api";

/**
 * The priced comparison: one workload, three clouds, a budget to check it
 * against.
 *
 * Selecting a provider draws its architecture with that provider's own
 * services and what each one costs. Every figure is computed from the
 * catalog — none are written into this file.
 */

const CHROME: Record<
  string,
  { label: string; logo: string; border: string; tint: string }
> = {
  aws: {
    label: "AWS Cloud",
    logo: "logos:aws",
    border: "#232F3E",
    tint: "#fafbfc",
  },
  azure: {
    label: "Microsoft Azure",
    logo: "logos:microsoft-azure",
    border: "#0078D4",
    tint: "#f8fbfe",
  },
  gcp: {
    label: "Google Cloud",
    logo: "logos:google-cloud",
    border: "#1A73E8",
    tint: "#f9fbfe",
  },
};



export function MultiCloudArchitecture({
  byProvider,
}: {
  byProvider: Record<string, Option>;
}) {
  const providers = Object.keys(byProvider).filter((p) => byProvider[p]);
  const complete = providers.filter((p) => byProvider[p].complete);
  const cheapest = complete.length
    ? complete.reduce((a, b) =>
        byProvider[a].monthly_usd <= byProvider[b].monthly_usd ? a : b,
      )
    : null;
  const incomplete = providers.filter((p) => !byProvider[p].complete);

  // A fixed reference budget, stated rather than typed: this is a showcase,
  // and an input that only recolours a label is a control with nothing behind
  // it. The real budget is part of the requirement on the estimate page.
  const budgetValue = 400;

  // Generated from the same figures shown above, so the sentence cannot drift
  // from the numbers — and only complete options are ever compared.
  let insight: string | null = null;
  if (cheapest && complete.length > 1) {
    const others = complete
      .filter((p) => p !== cheapest)
      .map((p) => {
        const pct = Math.round(
          ((byProvider[p].monthly_usd - byProvider[cheapest].monthly_usd) /
            byProvider[cheapest].monthly_usd) *
            100,
        );
        return `${CHROME[p]?.label ?? p} costs ${pct}% more`;
      });
    insight = `${CHROME[cheapest]?.label ?? cheapest} is the cheapest complete option at ${money(
      byProvider[cheapest].monthly_usd,
    )}/mo. ${others.join("; ")}.`;
  }

  // The cheapest complete option opens first; a partial total never leads.
  const [active, setActive] = useState(cheapest ?? providers[0]);

  return (
    <div className="flex flex-col gap-5">
      <p className="text-[15px] text-ink-2">
        Priced against a{" "}
        <span className="font-mono font-medium text-ink">$400/month</span>{" "}
        reference budget.
      </p>

      <div role="tablist" aria-label="Cloud provider" className="grid gap-3 sm:grid-cols-3">
        {providers.map((p) => {
          const o = byProvider[p];
          const wins = p === cheapest;
          const on = p === active;
          return (
            <button
              key={p}
              role="tab"
              aria-selected={on}
              onClick={() => setActive(p)}
              className={`rounded-xl border px-5 py-4 text-left transition-all duration-150 ${
                on
                  ? "border-accent bg-accent-wash shadow-[0_2px_12px_-4px_rgba(36,81,217,.3)]"
                  : "border-line bg-white hover:border-line-strong hover:bg-sunk"
              }`}
            >
              <div className="flex items-center gap-2">
                <span className="text-[16px] font-semibold">
                  {CHROME[p]?.label ?? p}
                </span>
                {wins && (
                  <span className="rounded-full bg-accent px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-white">
                    Cheapest
                  </span>
                )}
              </div>
              <div className="tnum mt-1.5 font-mono text-[30px] font-semibold leading-none">
                {money(o.monthly_usd, 0)}
                <span className="ml-1 text-[15px] font-normal text-ink-3">/mo</span>
              </div>
              {!o.complete && (
                <div className="mt-2 font-mono text-[13px] text-caution">
                  {o.missing.length} component{o.missing.length === 1 ? "" : "s"} unpriced
                </div>
              )}
              {budgetValue > 0 && o.complete && (
                <div
                  className={`mt-2 font-mono text-[13px] ${
                    o.monthly_usd <= budgetValue ? "text-accent" : "text-spend"
                  }`}
                >
                  {o.monthly_usd <= budgetValue
                    ? `${money(budgetValue - o.monthly_usd)} under budget`
                    : `${money(o.monthly_usd - budgetValue)} over budget`}
                </div>
              )}
              <div
                className={`mt-2.5 text-[13px] font-medium transition-colors ${
                  on ? "text-accent" : "text-ink-3"
                }`}
              >
                {on ? "Showing architecture" : "View architecture →"}
              </div>
            </button>
          );
        })}
      </div>

      <PricedDiagram key={active} option={byProvider[active]} provider={active} />

      {insight && (
        <p className="rounded-xl border border-line bg-sunk px-5 py-4 text-[15px] leading-relaxed text-ink-2">
          {insight}
          {incomplete.length > 0 && (
            <>
              {" "}
              <span className="text-caution">
                {incomplete.map((p) => CHROME[p]?.label ?? p).join(" and ")} cannot be
                compared — {byProvider[incomplete[0]].missing.join(", ")} have no
                published price, so the total shown is below the real bill.
              </span>
            </>
          )}
        </p>
      )}
    </div>
  );
}
