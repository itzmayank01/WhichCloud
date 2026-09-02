"use client";

import { useState } from "react";
import { money, type Node, type Option, type Recommendation } from "@/lib/api";

/**
 * The rail beside the canvas: what was asked, what it costs, and why.
 *
 * Everything here is what the diagram cannot say for itself. It is one
 * scrolling column rather than a page, so the canvas keeps the viewport and
 * the numbers stay reachable without moving it.
 */

type Bucket = { key: string; label: string; value: number };

const BUCKETS: { key: string; label: string; kinds: string[] }[] = [
  // Lambda and API Gateway are compute (they run the app); DynamoDB is the
  // database. Bucketing them here rather than into "Other" is what keeps a
  // serverless bill's largest lines from hiding behind a label that says
  // nothing about what is being paid for.
  {
    key: "compute",
    label: "Compute",
    kinds: ["compute", "compute_fargate", "cache", "lambda", "apigateway"],
  },
  // Timestream is a purpose-built database, not "Other" -- on an IoT bill it
  // is one of the largest lines and belongs where the reader looks for the
  // store.
  { key: "database", label: "Database", kinds: ["database", "database_replica", "dynamodb", "timestream"] },
  { key: "storage", label: "Storage", kinds: ["storage", "backup"] },
  {
    key: "network",
    label: "Networking",
    kinds: ["network", "loadbalancer", "nat", "dns", "tls", "flowlogs"],
  },
  {
    key: "security",
    label: "Security & ops",
    kinds: ["waf", "audit", "kms", "secrets", "auth", "threat", "posture", "monitoring", "tracing"],
  },
  /* Named rather than left to the catch-all. On the top tier a warehouse is
     routinely the single largest line on the bill -- reporting it as "Other"
     put $631/mo, more than the database, behind a label that says nothing
     about what is being paid for. */
  {
    key: "ai",
    label: "AI / ML",
    kinds: ["rekognition", "comprehend"],
  },
  // The event pipeline's front door: device connectivity and the stream that
  // carries events in. Distinct from the analytics that query them.
  {
    key: "ingest",
    label: "Ingest / streaming",
    kinds: ["iot", "streaming", "kafka", "firehose"],
  },
  {
    key: "analytics",
    label: "Analytics & search",
    kinds: ["warehouse", "search", "athena", "glue"],
  },
  {
    key: "messaging",
    label: "Messaging",
    kinds: ["email", "queue", "notification"],
  },
  { key: "other", label: "Other", kinds: [] },
];

/** The dataviz skill's validated categorical palette (light mode), in its
 *  documented slot order. Validated with the skill's own checker against the
 *  adjacent pairlist, which is the one a stacked bar and its legend use.
 *  Three of these sit under 3:1 contrast on this surface, so the relief rule
 *  applies -- the legend below states every value directly rather than
 *  leaving the colour to carry it. */
const COLORS = [
  "#2a78d6", "#eb6834", "#1baf7a", "#eda100",
  "#e87ba4", "#008300", "#4a3aa7", "#e34948",
];

function bucketize(nodes: Node[]): Bucket[] {
  const totals = new Map<string, number>();
  for (const node of nodes) {
    if (!node.priced || node.kind === "client") continue;
    const bucket =
      BUCKETS.find((b) => b.kinds.includes(node.kind)) ?? BUCKETS[BUCKETS.length - 1];
    totals.set(bucket.key, (totals.get(bucket.key) ?? 0) + node.monthly_usd);
  }
  return BUCKETS.map((b) => ({ key: b.key, label: b.label, value: totals.get(b.key) ?? 0 }))
    .filter((b) => b.value > 0)
    .sort((a, b) => b.value - a.value);
}

function Section({
  title,
  children,
  defaultOpen = true,
}: {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border-b border-line">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-4 py-3 text-left transition-colors hover:bg-sunk"
      >
        <span className="font-mono text-[10.5px] uppercase tracking-[0.12em] text-ink-3">
          {title}
        </span>
        <svg
          viewBox="0 0 20 20"
          className={`h-3.5 w-3.5 text-ink-3 transition-transform ${open ? "" : "-rotate-90"}`}
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden
        >
          <path d="M5 8l5 5 5-5" />
        </svg>
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </div>
  );
}

export function CostRail({
  description,
  setDescription,
  onAsk,
  onUseExample,
  busy,
  error,
  result,
  option,
  because,
}: {
  description: string;
  setDescription: (value: string) => void;
  onAsk: () => void;
  onUseExample: () => void;
  busy: boolean;
  error: string | null;
  result: Recommendation | null;
  option: Option | null;
  because: string | null;
}) {
  const [active, setActive] = useState<string | null>(null);
  const buckets = option ? bucketize(option.topology.nodes) : [];
  const total = buckets.reduce((sum, b) => sum + b.value, 0);
  const colorFor = (key: string) =>
    COLORS[buckets.findIndex((b) => b.key === key)] ?? "#c3cad6";

  return (
    <aside className="flex w-full shrink-0 flex-col overflow-y-auto border-line bg-surface lg:h-full lg:w-[380px] lg:border-r">
      {/* ── describe ── */}
      <div className="border-b border-line p-4">
        <label
          htmlFor="workspace-description"
          className="font-mono text-[10.5px] uppercase tracking-[0.12em] text-ink-3"
        >
          Describe your app
        </label>
        <textarea
          id="workspace-description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={5}
          placeholder="What the system is for, how many people use it, what happens if it stops, and what you can spend."
          className="mt-2 w-full resize-y rounded-lg border border-line bg-canvas p-3 text-[13.5px] leading-relaxed text-ink outline-none transition-colors placeholder:text-ink-3 focus:border-accent"
        />
        <div className="mt-2.5 flex items-center gap-2">
          <button
            onClick={onAsk}
            disabled={busy}
            className="flex-1 rounded-lg bg-accent px-4 py-2 text-[13.5px] font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40"
          >
            {busy ? "Working…" : "Price it"}
          </button>
          {!description.trim() && (
            <button
              onClick={onUseExample}
              className="shrink-0 rounded-lg border border-line px-3 py-2 text-[12.5px] text-ink-2 transition-colors hover:bg-sunk"
            >
              Example
            </button>
          )}
        </div>
        {error && (
          <p className="mt-2.5 rounded-lg bg-caution-wash px-3 py-2 text-[12.5px] leading-relaxed text-caution">
            {error}
          </p>
        )}
      </div>

      {!option ? null : (
        <>
          {/* ── headline ── */}
          <div className="border-b border-line bg-canvas px-4 py-4">
            {result?.goal && (
              <p className="text-[13px] leading-snug text-ink-2">{result.goal}</p>
            )}
            <div className="mt-2.5 flex items-baseline gap-2">
              <span className="tnum font-mono text-[28px] font-semibold leading-none tracking-[-0.02em] text-ink">
                {money(option.monthly_usd)}
              </span>
              <span className="text-[12.5px] text-ink-3">/mo</span>
            </div>
            <p className="mt-1 font-mono text-[11.5px] text-ink-3">
              {option.label} · {option.shape}
            </p>
            {option.measured_saving_usd > 0 && (
              <p className="mt-1.5 font-mono text-[11.5px] font-medium text-save">
                −{money(option.measured_saving_usd)}/mo after optimizations
              </p>
            )}
            {because && (
              <p className="mt-2.5 text-[12.5px] leading-relaxed text-ink-2">{because}</p>
            )}
            {option.budget_saturated && (
              <p className="mt-2.5 rounded-lg bg-caution-wash px-2.5 py-2 text-[12px] leading-relaxed text-caution">
                Sized to the ceiling this workload can use. A higher budget
                won't add useful capacity — the extra is headroom.
              </p>
            )}
            {!option.complete && (
              <p className="mt-2.5 rounded-lg bg-caution-wash px-2.5 py-2 text-[12px] leading-relaxed text-caution">
                {option.missing.length} component
                {option.missing.length === 1 ? "" : "s"} could not be priced in
                this region — this total is a floor, not the answer.
              </p>
            )}
          </div>

          {/* ── cost distribution ── */}
          {total > 0 && (
            <Section title="Cost distribution">
              <div
                className="flex h-7 w-full overflow-hidden rounded-md"
                role="img"
                aria-label={`Cost by category: ${buckets
                  .map((b) => `${b.label} ${money(b.value, 2)}`)
                  .join(", ")}`}
              >
                {buckets.map((b) => {
                  const pct = (b.value / total) * 100;
                  const on = active === b.key;
                  return (
                    <div
                      key={b.key}
                      tabIndex={0}
                      onMouseEnter={() => setActive(b.key)}
                      onMouseLeave={() => setActive(null)}
                      onFocus={() => setActive(b.key)}
                      onBlur={() => setActive(null)}
                      title={`${b.label} ${money(b.value, 2)} (${Math.round(pct)}%)`}
                      className="flex items-center justify-center outline-none transition-[filter]"
                      style={{
                        width: `${pct}%`,
                        background: colorFor(b.key),
                        filter: on ? "brightness(1.1)" : undefined,
                        boxShadow: on ? "inset 0 0 0 2px rgba(255,255,255,.65)" : undefined,
                      }}
                    >
                      {pct >= 14 && (
                        <span className="select-none font-mono text-[10px] font-bold text-white/95">
                          {Math.round(pct)}%
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>

              <div className="mt-3 space-y-1">
                {buckets.map((b) => (
                  <div
                    key={b.key}
                    onMouseEnter={() => setActive(b.key)}
                    onMouseLeave={() => setActive(null)}
                    className="flex items-center gap-2 rounded px-1 py-1 transition-colors hover:bg-sunk"
                  >
                    <span
                      className="h-2.5 w-2.5 shrink-0 rounded-[2px] transition-opacity"
                      style={{
                        background: colorFor(b.key),
                        opacity: active && active !== b.key ? 0.35 : 1,
                      }}
                    />
                    <span className="flex-1 truncate text-[12.5px] text-ink-2">
                      {b.label}
                    </span>
                    <span className="tnum shrink-0 font-mono text-[12px] font-semibold text-ink">
                      {money(b.value)}
                    </span>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* ── every line ── */}
          <Section title="Every line" defaultOpen={false}>
            <div className="space-y-0.5">
              {option.items.map((item) => (
                <div
                  key={item.label + item.sku}
                  className="flex items-baseline justify-between gap-2 py-1"
                >
                  <div className="min-w-0">
                    <div className="truncate text-[12.5px] text-ink-2">{item.label}</div>
                    <div className="truncate font-mono text-[10.5px] text-ink-3">
                      {item.sku}
                    </div>
                  </div>
                  <span className="tnum shrink-0 font-mono text-[12px] font-semibold text-ink">
                    {money(item.monthly_usd)}
                  </span>
                </div>
              ))}
            </div>
          </Section>

          {/* ── why ── */}
          {(option.applied.length > 0 ||
            option.advisory.length > 0 ||
            (result?.not_applied.length ?? 0) > 0) && (
            <Section title="Why these choices" defaultOpen={false}>
              {option.applied.length > 0 && (
                <div className="space-y-2">
                  {option.applied.map((t) => (
                    <div key={t.id} className="rounded-lg bg-sunk px-2.5 py-2">
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="text-[12.5px] font-medium leading-snug text-ink">
                          {t.name}
                        </span>
                        {t.saved_monthly_usd != null && (
                          <span className="shrink-0 font-mono text-[12px] font-semibold text-save">
                            −{money(t.saved_monthly_usd)}
                          </span>
                        )}
                      </div>
                      {t.versus_sku && (
                        <p className="mt-0.5 font-mono text-[10.5px] text-ink-3">
                          vs {t.versus_sku}
                        </p>
                      )}
                      {t.reasons.map((r) => (
                        <p key={r} className="mt-1 text-[12px] leading-relaxed text-ink-2">
                          · {r}
                        </p>
                      ))}
                    </div>
                  ))}
                </div>
              )}

              {option.advisory.length > 0 && (
                <div className="mt-3">
                  <p className="text-[11.5px] font-medium text-ink-3">
                    Also worth doing, not priceable
                  </p>
                  <ul className="mt-1 space-y-0.5">
                    {option.advisory.map((t) => (
                      <li key={t.id} className="text-[12px] leading-relaxed text-ink-2">
                        {t.name}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {(result?.not_applied.length ?? 0) > 0 && (
                <div className="mt-3">
                  <p className="text-[11.5px] font-medium text-ink-3">Ruled out</p>
                  <ul className="mt-1 space-y-0.5">
                    {result?.not_applied.map((n) => (
                      <li key={n.id} className="text-[11.5px] leading-relaxed text-ink-3">
                        <span className="text-ink-2">{n.name}</span> — {n.reason}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </Section>
          )}

          {/* ── what it gives up ── */}
          {option.tradeoffs.length > 0 && (
            <Section title="What this gives up" defaultOpen={false}>
              <ul className="space-y-1">
                {option.tradeoffs.map((t) => (
                  <li key={t} className="text-[12.5px] leading-relaxed text-ink-2">
                    {t}
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {/* ── what was guessed ── */}
          {result && (result.assumed.length > 0 || result.sizing_basis) && (
            <Section title="What was assumed" defaultOpen={false}>
              {result.assumed.length > 0 && (
                <p className="text-[12px] leading-relaxed text-ink-2">
                  Guessed, because the description did not say:{" "}
                  {result.assumed.join(", ")}.
                </p>
              )}
              {result.clarifying_question && (
                <p className="mt-2 text-[12px] leading-relaxed text-ink-2">
                  {result.clarifying_question}
                </p>
              )}
              <p className="mt-2 text-[11.5px] leading-relaxed text-ink-3">
                {result.sizing_basis}
              </p>
            </Section>
          )}
        </>
      )}
    </aside>
  );
}
