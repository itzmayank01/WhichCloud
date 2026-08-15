"use client";

import { useState } from "react";
import { Icon } from "@iconify/react";
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

            {/* Three across only once each card can hold a provider's full name
          beside its badge. Measured: the name ellipsises to "Go…" at 225px of
          card and is comfortable by 259px. sm gives ~200px and md ~232px,
          both inside that range; lg gives ~317px. So the columns start at lg
          and the cards stack below it, which costs some vertical space and
          never costs a provider its name. */}
      <div role="tablist" aria-label="Cloud provider" className="grid gap-3 lg:grid-cols-3">
        {providers.map((p) => {
          const o = byProvider[p];
          const chrome = CHROME[p];
          const wins = p === cheapest;
          const on = p === active;

          // How much of the reference budget this consumes, and how it
          // compares to the cheapest complete option. Both are derived here
          // rather than stated, so neither can drift from the figures.
          const usedPct = Math.min(
            100,
            Math.round((o.monthly_usd / budgetValue) * 100),
          );
          const over = o.monthly_usd > budgetValue;
          const delta =
            cheapest && o.complete && !wins
              ? o.monthly_usd - byProvider[cheapest].monthly_usd
              : 0;

          return (
            <button
              key={p}
              role="tab"
              aria-selected={on}
              onClick={() => setActive(p)}
              /* The winner keeps its own colour whether or not it is the
                 selected card. Two accents on one card -- green for cheapest,
                 blue for selected -- read as two different claims about the
                 same thing, so on this card selection is green as well. */
              className={`group relative overflow-hidden rounded-xl border bg-white text-left transition-all duration-150 ${
                wins
                  ? on
                    ? "border-save shadow-[0_4px_16px_-6px_rgba(11,122,69,.32)]"
                    : "border-save/45 shadow-[0_2px_10px_-6px_rgba(11,122,69,.25)] hover:border-save/70"
                  : on
                    ? "border-accent shadow-[0_4px_16px_-6px_rgba(36,81,217,.28)]"
                    : "border-line hover:border-line-strong hover:shadow-[0_2px_10px_-6px_rgba(11,13,18,.18)]"
              }`}
            >
              {/* Selection reads as a marked edge rather than a filled panel,
                  so the figures inside keep the same contrast whether or not
                  the card is the active one. */}
              <span
                aria-hidden
                className={`absolute inset-x-0 top-0 h-[3px] transition-opacity duration-150 ${
                  on ? "opacity-100" : "opacity-0"
                }`}
                style={{
                  background: wins
                    ? "var(--save)"
                    : (chrome?.border ?? "#2451d9"),
                }}
              />

              <div className="px-5 pb-4 pt-5">
                {/* One line, always. Letting the name wrap around the badge
                    pushes that card's total below the other two, and three
                    figures meant to be compared at a glance have to sit on
                    the same baseline. */}
                <div className="flex h-6 items-center gap-2">
                  {chrome?.logo && (
                    <Icon
                      icon={chrome.logo}
                      width={18}
                      height={18}
                      className="shrink-0"
                      aria-hidden
                    />
                  )}
                  <span className="truncate text-[15px] font-semibold tracking-[-0.01em]">
                    {chrome?.label ?? p}
                  </span>
                  {wins && (
                    <span className="ml-auto shrink-0 rounded-full bg-save px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-[0.06em] text-white">
                      Cheapest
                    </span>
                  )}
                </div>

                {/* A partial total is a floor, not a price. Showing it as a
                    bare figure invites comparison against the complete ones,
                    which is exactly the wrong conclusion. */}
                {/* The cheapest total is the answer this section was built to
                    give, so it is the only figure that carries colour. Green
                    on the winner and ink on the rest means the eye lands on
                    it before reading a single label. */}
                <div
                  className={`tnum mt-3 font-mono text-[32px] font-semibold leading-none tracking-[-0.02em] ${
                    !o.complete ? "text-ink-3" : wins ? "text-save" : "text-ink"
                  }`}
                >
                  {!o.complete && (
                    <span className="mr-0.5 text-[23px] font-normal">&ge;</span>
                  )}
                  {money(o.monthly_usd, 0)}
                  <span className="ml-1 text-[14px] font-normal text-ink-3">
                    /mo
                  </span>
                </div>

                {o.complete ? (
                  <>
                    <div className="mt-3.5 h-1 w-full overflow-hidden rounded-full bg-sunk">
                      <span
                        className="block h-full rounded-full transition-all duration-500"
                        style={{
                          width: `${usedPct}%`,
                          background: over
                            ? "var(--spend)"
                            : wins
                              ? "var(--save)"
                              : "var(--accent)",
                        }}
                      />
                    </div>
                    <div className="mt-2 flex items-baseline justify-between font-mono text-[12.5px] font-medium">
                      <span className={over ? "text-spend" : "text-ink-3"}>
                        {usedPct}% of {money(budgetValue, 0)}
                      </span>
                      <span
                        className={
                          wins ? "font-semibold text-save" : "text-ink-3"
                        }
                      >
                        {wins ? "cheapest" : `+${money(delta, 0)}`}
                      </span>
                    </div>
                  </>
                ) : (
                  <div className="mt-3.5 font-mono text-[12.5px] font-medium text-caution">
                    partial, {o.missing.length} component
                    {o.missing.length === 1 ? "" : "s"} unpriced
                  </div>
                )}
              </div>

              <div
                className={`flex items-center justify-between border-t px-5 py-2.5 text-[12.5px] font-medium transition-colors ${
                  on
                    ? wins
                      ? "border-save/25 text-save"
                      : "border-accent/25 bg-accent-wash text-accent"
                    : wins
                      ? "border-save/20 text-save/85 group-hover:text-save"
                      : "border-line text-ink-3 group-hover:text-ink-2"
                }`}
              >
                <span>{on ? "Showing architecture" : "View architecture"}</span>
                <span className="tnum font-mono text-[11.5px]">
                  {o.items.length} services
                </span>
              </div>
            </button>
          );
        })}
      </div>

      {/* No key: keying on the provider tears the diagram down and builds it
          again on every click, which throws away the measured scale and makes
          each switch flash at full size before settling. Switching provider
          is a prop change, so it is passed as one. */}
      <PricedDiagram option={byProvider[active]} provider={active} />

      {insight && (
        <p className="rounded-xl border border-line bg-sunk px-5 py-4 text-[15px] leading-relaxed text-ink-2">
          {insight}
          {incomplete.length > 0 && (
            <>
              {" "}
              <span className="text-caution">
                {incomplete.map((p) => CHROME[p]?.label ?? p).join(" and ")} cannot be
                compared. {byProvider[incomplete[0]].missing.join(", ")} have no
                published price, so the total shown is below the real bill.
              </span>
            </>
          )}
        </p>
      )}
    </div>
  );
}
