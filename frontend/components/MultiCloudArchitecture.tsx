"use client";

import { useEffect, useRef, useState } from "react";
import { Icon } from "@iconify/react";
import { PricedDiagram } from "@/components/PricedDiagram";
import { api, comparableTotals, money, type Option } from "@/lib/api";

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



/* Which city each provider region actually is. A reader choosing "India"
   should be able to see that the three prices are not all from the same
   city -- AWS and GCP are Mumbai, Azure is Pune -- rather than assume it. */
const REGION_CITY: Record<string, string> = {
  "ap-south-1": "Mumbai",
  centralindia: "Pune",
  "asia-south1": "Mumbai",
  "us-east-1": "N. Virginia",
  eastus: "Virginia",
  "us-east1": "S. Carolina",
  // EU West is three countries, not three cities, which is worth showing.
  "eu-west-1": "Ireland",
  westeurope: "Netherlands",
  "europe-west1": "Belgium",
  "ap-southeast-1": "Singapore",
  southeastasia: "Singapore",
  "asia-southeast1": "Singapore",
};

const REGION_LABEL: Record<string, string> = {
  india: "India",
  "us-east": "US East",
  "eu-west": "EU West",
  singapore: "Singapore",
};

export function MultiCloudArchitecture({
  byProvider: initial,
  initialRegion = "india",
  regions = [],
}: {
  byProvider: Record<string, Option>;
  initialRegion?: string;
  regions?: string[];
}) {
  /* The comparison is fetched again in the browser when the region or the
     budget changes. Everything else on this page plays at the reader; this is
     the one place they can ask it something and have it answer, and the
     answer is a real call rather than a filter over pre-loaded data -- prices
     genuinely differ by region and pretending otherwise would be the same
     lie the rest of the site avoids. */
  const [byProvider, setByProvider] = useState(initial);
  const [region, setRegion] = useState(initialRegion);
  /* Held as text, not a number. Coercing every keystroke with Number()
     turned an empty field into 0, so clearing it and typing 1000 left the
     zero in front and read "01000". The string is what the reader typed; the
     number is derived from it. */
  const [budgetText, setBudgetText] = useState("400");
  const budgetValue = Math.max(0, Number(budgetText) || 0);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const first = useRef(true);

  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    let cancelled = false;
    setLoading(true);
    setFailed(false);

    api
      .compare({
        goal: "an online shop",
        workload_type: "web",
        traffic_pattern: "spiky",
        traffic_scale: "medium",
        storage_gb: 200,
        egress_gb: 500,
        region,
      })
      .then((compare) => {
        if (cancelled) return;
        const next: Record<string, Option> = {};
        for (const [provider, options] of Object.entries(compare.clouds)) {
          const balanced = options.find((o) => o.label === "Balanced") ?? options[0];
          if (balanced) next[provider] = balanced;
        }
        if (Object.keys(next).length) setByProvider(next);
      })
      .catch(() => !cancelled && setFailed(true))
      .finally(() => !cancelled && setLoading(false));

    return () => {
      cancelled = true;
    };
  }, [region]);

  const providers = Object.keys(byProvider).filter((p) => byProvider[p]);
  const complete = providers.filter((p) => byProvider[p].complete);

  /* "Cheapest" is a comparative claim and needs something to compare
     against. With one complete estimate and the rest partial there is no
     comparison to win -- and badging the one full architecture "cheapest"
     beside a greyed "≥$336" invites exactly the wrong conclusion, because
     the partial figure is a floor that may well end up higher. The insight
     sentence below already required two; the badge did not, which is how a
     21-service AWS total came to be labelled cheaper than a 7-service one. */
  const comparable = complete.length > 1;
  const cheapest = comparable
    ? complete.reduce((a, b) =>
        byProvider[a].monthly_usd <= byProvider[b].monthly_usd ? a : b,
      )
    : null;
  /** The single complete estimate, when it is the only one we can price. */
  const soleComplete = !comparable && complete.length === 1 ? complete[0] : null;

  /* Like-for-like, but ONLY while some cloud is still incomplete.
     
     It exists because raw totals cannot be compared when one cloud prices
     twenty-two components and another prices seven -- the second looks
     cheaper for a reason that has nothing to do with its rates.

     Once every cloud prices every capability the raw totals ARE the
     comparison, and this becomes actively wrong: it intersects on label
     text, and clouds legitimately name the same capability differently
     (AWS splits threat detection into compute and database lines, GCP
     bills one). Left on, it silently dropped six capabilities that all
     three do price and under-reported every cloud. */
  const allComplete = complete.length === providers.length;
  const likeForLike = allComplete
    ? []
    : comparableTotals(
        Object.fromEntries(providers.map((p) => [p, [byProvider[p]]])),
      );
  const likeForLikeBy = Object.fromEntries(
    likeForLike.map((r) => [r.provider, r]),
  );
  const likeForLikeBest = likeForLike[0]?.provider ?? null;
  const incomplete = providers.filter((p) => !byProvider[p].complete);

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
  const [active, setActive] = useState(cheapest ?? soleComplete ?? providers[0]);

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
        {regions.length > 1 && (
          <label className="flex items-center gap-2.5 text-[14.5px] text-ink-2">
            Region
            <select
              value={region}
              onChange={(e) => setRegion(e.target.value)}
              className="rounded-lg border border-line bg-surface px-2.5 py-1.5 text-[14px] font-medium text-ink"
            >
              {regions.map((r) => (
                <option key={r} value={r}>
                  {REGION_LABEL[r] ?? r}
                </option>
              ))}
            </select>
          </label>
        )}

        <label className="flex items-center gap-2.5 text-[14.5px] text-ink-2">
          Budget
          <span className="flex items-center rounded-lg border border-line bg-surface pl-2.5">
            <span className="font-mono text-[14px] text-ink-3">$</span>
            <input
              type="text"
              inputMode="numeric"
              value={budgetText}
              onChange={(e) => {
                // Digits only, and no leading zeros to accumulate in front of
                // what was typed.
                const digits = e.target.value.replace(/[^\d]/g, "").slice(0, 7);
                setBudgetText(digits.replace(/^0+(?=\d)/, ""));
              }}
              onBlur={() => setBudgetText(String(budgetValue || 0))}
              className="tnum w-[86px] bg-transparent py-1.5 pl-1 pr-2.5 font-mono text-[14px] font-medium text-ink outline-none"
              aria-label="Monthly budget in dollars"
            />
            <span className="pr-2.5 font-mono text-[13px] text-ink-3">/mo</span>
          </span>
        </label>

        {loading && (
          <span className="font-mono text-[13px] font-medium text-ink-3">
            re-pricing…
          </span>
        )}
        {failed && (
          <span className="font-mono text-[13px] font-medium text-caution">
            could not re-price that region
          </span>
        )}
      </div>

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
          const usedPct = budgetValue
            ? Math.min(100, Math.round((o.monthly_usd / budgetValue) * 100))
            : 0;
          const over = budgetValue > 0 && o.monthly_usd > budgetValue;
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
                    : "border-line hover:border-line-strong hover:elev-2"
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
                  {p === soleComplete && (
                    <span className="ml-auto shrink-0 rounded-full bg-accent-wash px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-[0.06em] text-accent">
                      Fully priced
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
                      {/* An empty budget has nothing to be a percentage of.
                          "0% of $0" is not a smaller claim than the real one,
                          it is a meaningless one. */}
                      <span className={over ? "text-spend" : "text-ink-3"}>
                        {budgetValue > 0
                          ? `${usedPct}% of ${money(budgetValue, 0)}`
                          : "no budget set"}
                      </span>
                      <span
                        className={
                          wins ? "font-semibold text-save" : "text-ink-3"
                        }
                      >
                        {wins
                          ? "cheapest"
                          : p === soleComplete
                            ? "only complete estimate"
                            : `+${money(delta, 0)}`}
                      </span>
                    </div>
                  </>
                ) : (
                  <div className="mt-3.5 font-mono text-[12.5px] font-medium text-caution">
                    partial, {o.missing.length} component
                    {o.missing.length === 1 ? "" : "s"} unpriced
                  </div>
                )}

                {/* The only figure on a partial card that can honestly be
                    set beside the others. */}
                {likeForLikeBy[p] && likeForLike.length > 1 && (
                  <div className="mt-2.5 border-t border-line pt-2.5">
                    <div className="flex items-baseline justify-between font-mono text-[12.5px] font-medium">
                      <span className="text-ink-3">
                        on {likeForLikeBy[p].covered} shared services
                      </span>
                      <span
                        className={
                          p === likeForLikeBest
                            ? "font-semibold text-save"
                            : "text-ink-2"
                        }
                      >
                        {money(likeForLikeBy[p].total, 0)}
                        {p === likeForLikeBest ? " ·  lowest" : ""}
                      </span>
                    </div>
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
                  {o.region}
                  {REGION_CITY[o.region] ? ` · ${REGION_CITY[o.region]}` : ""} ·{" "}
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
