"use client";

import { useState } from "react";
import { ArchitectureDiagram } from "@/components/ArchitectureDiagram";
import { money, type Option } from "@/lib/api";
import { PROVIDER_LABEL } from "@/lib/services";

/**
 * The same workload, drawn on all three clouds.
 *
 * This is the product's question made visual: one architecture, three
 * providers, and the diagram redraws with each one's own service names while
 * the shape stays recognisably the same. The tabs carry the totals, so the
 * comparison is visible before anything is clicked.
 *
 * A provider that could not be fully priced says so on its tab rather than
 * appearing cheapest by omission.
 */
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

  const [active, setActive] = useState(cheapest ?? providers[0]);
  const option = byProvider[active];

  return (
    <div>
      <div
        role="tablist"
        aria-label="Cloud provider"
        className="flex flex-wrap gap-2"
      >
        {providers.map((p) => {
          const o = byProvider[p];
          const on = p === active;
          return (
            <button
              key={p}
              role="tab"
              aria-selected={on}
              onClick={() => setActive(p)}
              className={`flex-1 rounded-lg border px-4 py-3 text-left transition-all duration-150 ${
                on
                  ? "border-accent bg-accent-wash shadow-[0_2px_10px_-4px_rgba(36,81,217,.35)]"
                  : "border-line bg-surface hover:border-line-strong hover:bg-sunk"
              }`}
            >
              <div className="flex items-center gap-2">
                <span className="text-[15px] font-medium">{PROVIDER_LABEL[p] ?? p}</span>
                {p === cheapest && (
                  <span className="rounded bg-accent px-1.5 py-0.5 text-[11px] font-medium text-white">
                    cheapest
                  </span>
                )}
              </div>
              <div className="tnum mt-1 font-mono text-[22px] leading-none">
                {money(o.monthly_usd, 0)}
                <span className="ml-1 text-[13px] text-ink-3">/mo</span>
              </div>
              {!o.complete && (
                <div className="mt-1.5 font-mono text-[12px] text-caution">
                  {o.missing.length} component{o.missing.length === 1 ? "" : "s"} unpriced
                </div>
              )}
            </button>
          );
        })}
      </div>

      <div className="mt-4">
        <ArchitectureDiagram
          key={active}
          topology={option.topology}
          provider={active}
          caption={`${option.label} · ${option.region} · ${option.shape}`}
        />
      </div>

      {!option.complete && (
        <p className="mt-3 rounded-lg bg-caution-wash px-4 py-3 text-[14px] leading-relaxed text-ink-2">
          <span className="font-medium text-caution">Incomplete.</span>{" "}
          {PROVIDER_LABEL[active]} is missing a published price for{" "}
          {option.missing.join(", ")}, so this total is lower than the real
          bill — it is shown, not hidden, and never ranked as cheapest.
        </p>
      )}
    </div>
  );
}
