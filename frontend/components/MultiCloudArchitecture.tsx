"use client";

import { useState } from "react";
import { HoverBoard } from "@/components/HoverBoard";
import { money, type Node as ApiNode, type Option } from "@/lib/api";
import { serviceName } from "@/lib/services";

/**
 * The same workload drawn on all three clouds, with a cost on every service
 * and a subtotal on every tier.
 *
 * Every figure is computed from the priced estimate. None are written into
 * this file — a landing page for a tool promising "computed, not guessed"
 * cannot contain a hand-typed price, or the promise is worth nothing.
 *
 * That constraint shows most clearly on GCP: it prices compute only, so its
 * total is genuinely lower and genuinely wrong. It is shown, labelled, and
 * excluded from any "cheapest" claim rather than quietly winning.
 */

const TIERS = [
  { id: "edge", label: "Edge", kinds: ["network", "loadbalancer"] },
  { id: "app", label: "Application tier", kinds: ["compute"] },
  { id: "data", label: "Data tier", kinds: ["database", "storage"] },
];

const SERVICE_COLOUR: Record<string, string> = {
  network: "#8C4FFF",
  loadbalancer: "#8C4FFF",
  compute: "#ED7100",
  database: "#3556C8",
  storage: "#4A8C1C",
  client: "#5A6270",
};

const CHROME: Record<string, { label: string; mark: string; tint: string }> = {
  aws: { label: "AWS Cloud", mark: "#232F3E", tint: "#fafbfc" },
  azure: { label: "Microsoft Azure", mark: "#0078D4", tint: "#f8fbfe" },
  gcp: { label: "Google Cloud", mark: "#1A73E8", tint: "#f9fbfe" },
};

/* Glyphs echo each service's silhouette — a bucket for storage, a cylinder
   for the database, a globe for the CDN — without reproducing the providers'
   icon artwork. AWS ships its set under CC-BY-ND, which forbids exactly the
   recolouring and resizing a component like this performs. */
const GLYPH: Record<string, React.ReactNode> = {
  client: (
    <>
      <circle cx="12" cy="8" r="3.4" />
      <path d="M5 20c0-3.9 3.1-7 7-7s7 3.1 7 7" />
    </>
  ),
  network: (
    <>
      <circle cx="12" cy="12" r="8.2" />
      <path d="M3.8 12h16.4M12 3.8c2.2 2.6 3.3 5.3 3.3 8.2s-1.1 5.6-3.3 8.2c-2.2-2.6-3.3-5.3-3.3-8.2S9.8 6.4 12 3.8Z" />
    </>
  ),
  loadbalancer: (
    <>
      <circle cx="12" cy="4.4" r="2" />
      <path d="M12 6.4v3.2M12 9.6 5.8 14.6M12 9.6l6.2 5" />
      <rect x="2.8" y="14.6" width="6" height="6" rx="1.4" />
      <rect x="15.2" y="14.6" width="6" height="6" rx="1.4" />
    </>
  ),
  compute: (
    <>
      <rect x="5.2" y="5.2" width="13.6" height="13.6" rx="2.2" />
      <rect x="9.4" y="9.4" width="5.2" height="5.2" rx="1" />
      <path d="M9 2.6v2.6M15 2.6v2.6M9 18.8v2.6M15 18.8v2.6M2.6 9h2.6M2.6 15h2.6M18.8 9h2.6M18.8 15h2.6" />
    </>
  ),
  database: (
    <>
      <ellipse cx="12" cy="6.2" rx="7" ry="3" />
      <path d="M5 6.2v11.6c0 1.7 3.1 3 7 3s7-1.3 7-3V6.2M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3" />
    </>
  ),
  storage: (
    <>
      <path d="M4.4 6.6h15.2l-1.3 13a1.6 1.6 0 0 1-1.6 1.4H7.3a1.6 1.6 0 0 1-1.6-1.4l-1.3-13Z" />
      <path d="M3 6.6h18M9.4 11v6M14.6 11v6" />
    </>
  ),
};

function Service({
  node,
  provider,
  active,
  dimmed,
  onEnter,
  onLeave,
}: {
  node: ApiNode;
  provider: string;
  active: boolean;
  dimmed: boolean;
  onEnter: () => void;
  onLeave: () => void;
}) {
  const colour = SERVICE_COLOUR[node.kind] ?? "#5A6270";

  return (
    <div
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
      onFocus={onEnter}
      onBlur={onLeave}
      tabIndex={0}
      className={`relative w-[190px] rounded-lg border bg-white px-3.5 py-3 outline-none transition-all duration-200 ${
        dimmed ? "opacity-40" : "opacity-100"
      } ${
        active
          ? "scale-[1.02] border-line-strong shadow-[0_10px_26px_-10px_rgba(11,13,18,.3)]"
          : "border-line shadow-[0_1px_2px_rgba(11,13,18,.04)]"
      }`}
    >
      <div className="flex items-start gap-3">
        <span
          className="grid h-11 w-11 shrink-0 place-items-center rounded-lg"
          style={{ background: colour, opacity: node.priced ? 1 : 0.35 }}
        >
          <svg
            viewBox="0 0 24 24"
            className="h-6 w-6"
            fill="none"
            stroke="#fff"
            strokeWidth="1.7"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden
          >
            {GLYPH[node.kind] ?? GLYPH.compute}
          </svg>
        </span>

        <div className="min-w-0 flex-1">
          <div className="text-[14px] font-semibold leading-tight text-ink">
            {serviceName(provider, node.kind, node.label)}
          </div>
          <div className="mt-1 truncate font-mono text-[13px] text-ink-3">
            {node.detail || node.sku || "—"}
          </div>
        </div>
      </div>

      <div className="mt-2.5 flex items-baseline justify-between border-t border-line pt-2.5">
        {node.priced ? (
          <>
            <span
              className="tnum font-mono text-[17px] font-semibold"
              style={{ color: colour }}
            >
              {money(node.monthly_usd)}
            </span>
            <span className="tnum font-mono text-[13px] text-ink-3">
              {Math.round(node.share * 100)}%
            </span>
          </>
        ) : (
          <span className="font-mono text-[13px] text-caution">not priced</span>
        )}
      </div>

      {node.optimized_by.length > 0 && (
        <span
          className="absolute -right-1 -top-1 h-3 w-3 rounded-full bg-accent ring-2 ring-white"
          title={`Optimized by ${node.optimized_by.join(", ")}`}
        />
      )}
    </div>
  );
}

function Flow() {
  return (
    <div className="flex shrink-0 items-center px-1.5" aria-hidden>
      <svg width="30" height="12" viewBox="0 0 30 12" fill="none">
        <path d="M0 6h22" stroke="#aab1bd" strokeWidth="1.3" />
        <path
          d="M21 2.2 27 6l-6 3.8"
          stroke="#aab1bd"
          strokeWidth="1.3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );
}

function CloudDiagram({ option, provider }: { option: Option; provider: string }) {
  const [hovered, setHovered] = useState<string | null>(null);
  const chrome = CHROME[provider] ?? CHROME.aws;
  const nodes = option.topology.nodes;
  const users = nodes.find((n) => n.kind === "client");
  const total = nodes.reduce((s, n) => s + n.monthly_usd, 0);
  const focused = nodes.find((n) => n.id === hovered) ?? null;
  const dim = hovered !== null;

  const tiers = TIERS.map((t) => {
    const members = t.kinds
      .map((k) => nodes.find((n) => n.kind === k))
      .filter((n): n is ApiNode => Boolean(n));
    return { ...t, members, subtotal: members.reduce((s, n) => s + n.monthly_usd, 0) };
  }).filter((t) => t.members.length);

  return (
    <div className="rounded-xl border border-line bg-white p-5">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-[17px] font-semibold tracking-tight">
          {chrome.label} — cost breakdown by tier
        </h3>
        <span className="tnum font-mono text-[15px] text-ink-2">
          {money(option.monthly_usd)}/mo
        </span>
      </div>

      <div className="overflow-x-auto pb-1">
        <div className="flex min-w-[940px] items-stretch gap-1">
          {users && (
            <>
              <div className="flex items-center">
                <div className="w-[112px] text-center">
                  <span
                    className="mx-auto grid h-11 w-11 place-items-center rounded-lg"
                    style={{ background: SERVICE_COLOUR.client }}
                  >
                    <svg
                      viewBox="0 0 24 24"
                      className="h-6 w-6"
                      fill="none"
                      stroke="#fff"
                      strokeWidth="1.7"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      aria-hidden
                    >
                      {GLYPH.client}
                    </svg>
                  </span>
                  <div className="mt-2 text-[14px] font-semibold">Users</div>
                </div>
              </div>
              <div className="flex items-center">
                <Flow />
              </div>
            </>
          )}

          <div
            className="relative flex-1 rounded-xl border border-[#9aa3b2] px-4 pb-4 pt-9"
            style={{ background: chrome.tint }}
          >
            <span className="absolute left-4 top-2.5 flex items-center gap-2">
              <span
                className="grid h-5 w-5 place-items-center rounded"
                style={{ background: chrome.mark }}
              >
                <span className="h-1.5 w-1.5 rounded-[1px] bg-white" />
              </span>
              <span className="text-[13.5px] font-semibold text-ink-2">
                {chrome.label}
              </span>
            </span>

            <div className="flex items-start justify-between gap-1">
              {tiers.map((tier, i) => (
                <div key={tier.id} className="flex items-center">
                  <div className="relative rounded-lg border border-dashed border-[#b3bac6] px-3 pb-9 pt-8">
                    <span className="absolute left-1/2 top-2.5 -translate-x-1/2 whitespace-nowrap text-[13.5px] font-semibold text-ink-2">
                      {tier.label}
                    </span>

                    <div className="flex flex-col gap-2.5">
                      {tier.members.map((n) => (
                        <Service
                          key={n.id}
                          node={n}
                          provider={provider}
                          active={hovered === n.id}
                          dimmed={dim && hovered !== n.id}
                          onEnter={() => setHovered(n.id)}
                          onLeave={() => setHovered(null)}
                        />
                      ))}
                    </div>

                    {/* summed from this tier's own priced nodes, never typed in */}
                    <span className="absolute bottom-2.5 left-1/2 -translate-x-1/2 whitespace-nowrap font-mono text-[13px] text-ink-2">
                      {money(tier.subtotal)}
                      <span className="ml-2 text-ink-3">
                        {total > 0 ? Math.round((tier.subtotal / total) * 100) : 0}%
                      </span>
                    </span>
                  </div>
                  {i < tiers.length - 1 && <Flow />}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="mt-3">
        <HoverBoard node={focused} provider={provider} total={total} />
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-3">
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
          {[
            ["Compute", "#ED7100"],
            ["Database", "#3556C8"],
            ["Storage", "#4A8C1C"],
            ["Networking", "#8C4FFF"],
          ].map(([label, colour]) => (
            <span key={label} className="flex items-center gap-1.5">
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ background: colour as string }}
              />
              <span className="text-[13px] text-ink-2">{label}</span>
            </span>
          ))}
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-accent" />
            <span className="text-[13px] text-ink-2">optimized</span>
          </span>
        </div>
        <span className="font-mono text-[13px] text-ink-3">
          {option.label} · {option.region} · {option.shape}
        </span>
      </div>
    </div>
  );
}

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

      <CloudDiagram key={active} option={byProvider[active]} provider={active} />

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
