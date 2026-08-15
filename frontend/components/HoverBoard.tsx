"use client";

import type { Node as ApiNode } from "@/lib/api";
import { money } from "@/lib/api";
import { serviceName } from "@/lib/services";

/**
 * The detail board that floats over the diagram while a service is hovered.
 *
 * Provider reference diagrams stop at the box. This is the panel that answers
 * the next question — what am I paying for this, what share of the bill is it,
 * and did an optimization already touch it — without navigating away from the
 * shape you are reading.
 *
 * It occupies fixed space rather than appearing and disappearing, so the
 * diagram never reflows underneath the cursor.
 */

const NOTE: Record<string, string> = {
  compute: "Application servers. Usually the easiest line to shrink — smaller instances, ARM, or fewer of them off-peak.",
  database: "Managed database. Often the largest line on the bill, and the one people forget to right-size.",
  storage: "Object storage. Cheap per gigabyte; the cost usually hides in egress rather than here.",
  network: "Data leaving the provider's network. The invisible half of most cloud bills.",
  loadbalancer: "Distributes traffic across instances. Fixed hourly cost regardless of load.",
  client: "Your users. Free, and the reason for everything to the right.",
};

export function HoverBoard({
  node,
  provider,
  total,
}: {
  node: ApiNode | null;
  provider: string;
  total: number;
}) {
  const idle = node === null;

  return (
    <div
      className={`rounded-xl border bg-white px-5 py-4 transition-all duration-200 ${
        idle
          ? "border-line"
          : "border-line-strong shadow-[0_12px_32px_-14px_rgba(11,13,18,.28)]"
      }`}
      aria-live="polite"
    >
      {idle ? (
        <div className="flex items-center gap-3">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-sunk">
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="#666e7c" strokeWidth="1.8" strokeLinecap="round">
              <path d="M5 12h14M13 6l6 6-6 6" />
            </svg>
          </span>
          <p className="text-[14.5px] text-ink-2">
            Hover any service to see what it costs and why it is there.
          </p>
        </div>
      ) : (
        <div className="flex flex-wrap items-start gap-x-8 gap-y-3">
          <div className="min-w-[200px]">
            <div className="font-mono text-[13px] uppercase tracking-[0.12em] text-ink-3">
              {node.kind}
            </div>
            <div className="mt-1 text-[17px] font-medium leading-tight">
              {serviceName(provider, node.kind, node.label)}
            </div>
            {node.sku && (
              <div className="mt-1 font-mono text-[13px] text-ink-2">{node.sku}</div>
            )}
          </div>

          <div>
            <div className="font-mono text-[13px] uppercase tracking-[0.12em] text-ink-3">
              Monthly
            </div>
            <div className="tnum mt-1 font-mono text-[24px] leading-none">
              {node.priced ? money(node.monthly_usd) : "—"}
            </div>
            {node.priced && total > 0 && (
              <div className="tnum mt-1 font-mono text-[13px] text-ink-2">
                {Math.round(node.share * 100)}% of {money(total, 0)}
              </div>
            )}
          </div>

          <div className="max-w-[380px] flex-1">
            <div className="font-mono text-[13px] uppercase tracking-[0.12em] text-ink-3">
              What it is
            </div>
            <p className="mt-1 text-[14px] leading-relaxed text-ink-2">
              {NOTE[node.kind] ?? "Part of the architecture."}
            </p>
            {node.optimized_by.length > 0 && (
              <p className="mt-2 flex items-center gap-2 text-[13.5px] text-accent">
                <span className="h-2 w-2 rounded-full bg-accent" />
                Optimized by {node.optimized_by.join(", ")}
              </p>
            )}
            {!node.priced && (
              <p className="mt-2 text-[13.5px] text-caution">
                No published price for this on {provider.toUpperCase()} — shown so
                the gap is visible rather than hidden.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
