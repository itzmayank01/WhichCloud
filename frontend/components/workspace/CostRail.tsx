"use client";

import { useState } from "react";
import {
  money,
  type CloudId,
  type LineItem,
  type Node,
  type Option,
  type Recommendation,
} from "@/lib/api";
import { PROVIDER_SERVICES } from "@/lib/providerServices";

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
/* One desaturated ramp off the accent navy, not the default chart set.
 *
 * Blue/orange/green/yellow/pink says "chart" and drags four unrelated hues
 * into an interface that has to host three provider brand palettes without
 * fighting them. A single ramp keeps the chrome neutral and still separates
 * the categories, which is the only job the colour has here.
 *
 * The amber is LAST and belongs to the LARGEST category, so the eye lands on
 * whatever is actually driving the bill rather than on whichever slice
 * happened to be first. */
const RAMP = ["#1b3a6b", "#3e6491", "#6c8fb5", "#9cb6d2", "#c7d6e5"];
const LARGEST = "#b4530a";

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
        {/* Sentence case, sans, in ink. The mono-uppercase-tracked eyebrow
            is the single most recognisable tell of a generated interface, and
            five of them stacked down one panel read as decoration rather than
            structure. */}
        <span className="text-[15px] font-semibold text-ink">{title}</span>
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

/** 1_200_000 -> "1.2M". A quantity column has to stay narrow enough that the
 *  figures beside it still line up. */
function compact(n: number): string {
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e4) return `${(n / 1e3).toFixed(0)}k`;
  return n % 1 === 0 ? n.toLocaleString() : n.toFixed(1);
}

/** Line items gathered under the diagram node they pay for, biggest first.
 *
 *  The backend tags each line with the node KIND it belongs to, so this is a
 *  grouping rather than a guess: "Cloud SQL" gathers its instance, standby and
 *  storage rows instead of scattering them as three siblings sorted by price.
 *  The provider's own product name comes from the same catalog the diagram
 *  uses, which is why the sheet and the picture agree on what a thing is
 *  called. */
function groupedItems(option: Option, cloud: CloudId) {
  const by = new Map<string, LineItem[]>();
  for (const item of option.items) {
    const key = item.group || item.label;
    by.set(key, [...(by.get(key) ?? []), item]);
  }
  return [...by.entries()]
    .map(([key, items]) => ({
      key,
      label:
        PROVIDER_SERVICES[cloud]?.[key]?.name ??
        (items[0].group_label || items[0].label),
      sku: items.length === 1 ? items[0].sku : items[0].sku.split(":")[0],
      total: items.reduce((sum, i) => sum + i.monthly_usd, 0),
      items,
    }))
    .sort((a, b) => b.total - a.total);
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
  cloud = "aws",
  highlightGroup = null,
  onHoverGroup,
  onSelectGroup,
  onSelectOption,
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
  cloud?: CloudId;
  /** Node <-> cost are the same object. The sheet reports which resource the
   *  reader is pointing at so the diagram can answer, and highlights whichever
   *  the diagram reports back. */
  highlightGroup?: string | null;
  onHoverGroup?: (group: string | null) => void;
  onSelectGroup?: (group: string) => void;
  /** Switch tiers. The rail names the cheapest shape that meets the brief
   *  when the shown one does not, and naming it without being able to go
   *  there leaves the reader to hunt for the tab. */
  onSelectOption?: (label: string) => void;
}) {
  const [active, setActive] = useState<string | null>(null);
  const buckets = option ? bucketize(option.topology.nodes) : [];
  const total = buckets.reduce((sum, b) => sum + b.value, 0);
  // What the compliant alternative actually costs. Naming it without its
  // price asks the reader to click to find out whether they can afford it.
  // On-demand first, matching the tier tabs. Quoting the committed price
  // here put $387.12 in the rail against $447.13 on the tab for the same
  // option -- two numbers for one thing, and the reader has no way to know
  // which one they would pay.
  const compliantOption = result?.options.find(
    (o) => o.label === result.cheapest_compliant,
  );
  const cheapestCompliantCost =
    compliantOption?.ondemand_monthly_usd ?? compliantOption?.monthly_usd ?? null;
  // buckets arrive largest-first, so index 0 is the one to flag.
  const colorFor = (key: string) => {
    const i = buckets.findIndex((b) => b.key === key);
    if (i === 0) return LARGEST;
    return RAMP[i] ?? RAMP[RAMP.length - 1];
  };

  return (
    <aside className="flex w-full shrink-0 flex-col overflow-y-auto border-line bg-surface lg:h-full lg:w-[380px] lg:border-r">
      {/* ── describe ── */}
      <div className="border-b border-line p-4">
        <label
          htmlFor="workspace-description"
          className="text-[15px] font-semibold text-ink"
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
            {/* The headline is the ON-DEMAND price: what you pay if you sign
                nothing. `monthly_usd` may include committed rates on compute
                and database, which is a price nobody can obtain today -- it
                needs a one-year term they have not agreed to. Leading with a
                blend of the two would be a number no user could act on. */}
            <div className="mt-3">
              <div className="tnum font-mono text-[40px] font-semibold leading-none tracking-[-0.02em] text-ink">
                {money(option.ondemand_monthly_usd ?? option.monthly_usd)}
              </div>
              <p className="mt-1.5 text-[13px] text-ink-muted">per month, on-demand</p>
            </div>
            {/* The shape as an aligned definition list. Labels in one column,
                values in another, values in mono so figures and identifiers
                line up down the page -- the same discipline as the cost sheet
                below, which is what makes the panel read as one document. */}
            {option.shape_parts?.length > 0 && (
              <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
                {option.shape_parts.map((part) => (
                  <div key={part.label} className="contents">
                    <dt className="text-[13px] text-ink-muted">{part.label}</dt>
                    <dd className="font-mono text-[13px] text-ink">{part.value}</dd>
                  </div>
                ))}
              </dl>
            )}
            {/* The commitment as a full sentence naming what it covers, not a
                parenthetical. It is a business decision, not a discount code. */}
            {option.ondemand_monthly_usd != null &&
              option.commitment_covers.length > 0 && (
                <p className="mt-1.5 text-[11.5px] leading-snug text-ink-2">
                  <span className="font-mono font-semibold text-save">
                    {money(option.monthly_usd)}/mo
                  </span>{" "}
                  with a 1-year commitment on{" "}
                  {option.commitment_covers.join(", ").toLowerCase()}
                </p>
              )}
            {option.steady_monthly_usd != null &&
              option.steady_monthly_usd < option.monthly_usd && (
                <p className="mt-1 font-mono text-[11.5px] text-ink-3">
                  spiky traffic · steady {money(option.steady_monthly_usd)} –
                  peak {money(option.monthly_usd)}/mo
                </p>
              )}
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
            {/* Above the cost sheet, not filed under "what this gives up".
                A price is only meaningful once you know whether the thing
                priced is the thing you asked for, and the cheapest shape is
                always one machine and one database — so on a workload whose
                owner wrote that it cannot go down, this is the lowest number
                on screen AND the one that fails the brief. Naming the cheaper
                compliant alternative turns the warning into a decision. */}
            {!option.compliant && (
              <div className="mt-2.5 rounded-lg border border-caution/30 bg-caution-wash px-2.5 py-2">
                <p className="text-[12px] font-semibold text-caution">
                  This does not meet what you asked for
                </p>
                <ul className="mt-1 space-y-1">
                  {option.unmet.map((u) => (
                    <li key={u} className="text-[12px] leading-relaxed text-caution">
                      {u}
                    </li>
                  ))}
                </ul>
                {result?.cheapest_compliant ? (
                  <p className="mt-1.5 text-[12px] leading-relaxed text-ink-2">
                    <button
                      type="button"
                      onClick={() => onSelectOption?.(result.cheapest_compliant!)}
                      className="font-semibold text-accent underline underline-offset-2"
                    >
                      {result.cheapest_compliant}
                    </button>{" "}
                    is the cheapest shape here that does
                    {cheapestCompliantCost != null && (
                      <>
                        , at{" "}
                        <span className="tnum font-mono font-semibold">
                          {money(cheapestCompliantCost)}/mo
                        </span>
                      </>
                    )}
                    .
                  </p>
                ) : (
                  <p className="mt-1.5 text-[12px] leading-relaxed text-ink-2">
                    Nothing on offer meets it at this budget. That is a fact
                    about the budget, not a reason to ship a single point of
                    failure.
                  </p>
                )}
              </div>
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

          {/* ── the cost sheet ──
              A quotation's shape, not a list: resource, then its components
              indented beneath, figures right-aligned on one edge so decimals
              stack. That shared right edge is the spine of the whole design --
              it is what makes a column of numbers readable as a rate sheet
              rather than as a pile of values. */}
          <Section title="Cost sheet" defaultOpen={false}>
            <div>
              {groupedItems(option, cloud).map((g) => (
                <div
                  key={g.key}
                  data-cost-group={g.key}
                  onMouseEnter={() => onHoverGroup?.(g.key)}
                  onMouseLeave={() => onHoverGroup?.(null)}
                  onClick={() => onSelectGroup?.(g.key)}
                  className={`cursor-pointer border-t border-rule py-2 transition-colors first:border-t-0 ${
                    highlightGroup === g.key ? "bg-accent-wash" : ""
                  }`}
                >
                  <div className="flex items-baseline gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-[13px] text-ink">{g.label}</div>
                      {g.sku && (
                        <div className="truncate font-mono text-[11px] text-ink-muted">
                          {g.sku}
                        </div>
                      )}
                    </div>
                    <span className="tnum shrink-0 font-mono text-[13px] font-semibold text-ink">
                      {money(g.total)}
                    </span>
                  </div>

                  {/* Components. No rule between them -- they belong to the
                      resource above, and ruling each one would break the group
                      back into the flat list this replaced. */}
                  {g.items.length > 1 &&
                    g.items.map((item) => (
                      <div
                        key={item.label + item.sku}
                        className="mt-1 flex items-baseline gap-2 pl-3"
                      >
                        <span className="min-w-0 flex-1 truncate text-[12px] text-ink-muted">
                          {item.label}
                        </span>
                        {/* Quantity is DERIVED by our engine; the rate is
                            published fact. They are set apart so a reader can
                            see which half of a number is an assumption -- when
                            someone disputes a figure it is almost always the
                            quantity, not the rate. */}
                        <span className="tnum shrink-0 font-mono text-[11px] text-ink-muted">
                          {compact(item.quantity)} {item.unit}
                        </span>
                        <span className="tnum w-[68px] shrink-0 text-right font-mono text-[11px] text-ink-muted">
                          ${item.unit_price < 0.01 ? item.unit_price.toFixed(6) : item.unit_price.toFixed(4)}
                        </span>
                        <span className="tnum w-[72px] shrink-0 text-right font-mono text-[12px] text-ink">
                          {money(item.monthly_usd)}
                        </span>
                      </div>
                    ))}
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
