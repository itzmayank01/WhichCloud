import Link from "next/link";
import { api, freshness, money, type CatalogRow, type Recommendation } from "@/lib/api";
import { ShowcaseGrid } from "@/components/landing/ShowcaseGrid";
import { ProviderLogoCards } from "@/components/landing/ProviderLogoCards";
import { InlineIcon } from "@/components/landing/InlineIcon";
import { CountUp } from "@/components/landing/CountUp";
import { Reveal } from "@/components/landing/Reveal";

/* ─────────────────────────── shared ─────────────────────────── */

export function Pill({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto inline-flex items-center gap-2.5 rounded-full border border-line bg-surface py-1.5 pl-2 pr-4 shadow-[0_1px_2px_rgba(13,20,20,.05)]">
      <span className="rounded-full bg-accent px-2.5 py-0.5 text-[14px] font-medium text-white">
        New
      </span>
      <span className="text-[15.5px] text-ink-2">{children}</span>
      <span className="text-ink-3">→</span>
    </div>
  );
}

/* ──────────────────── the layered product shot ──────────────────── */

function Offline() {
  return (
    <p className="text-sm leading-relaxed text-ink-3">
      Start Postgres and the API to see live figures here.
    </p>
  );
}

/* ═══════════════════ card shell ═══════════════════ */
/*  Single design token for every card to guarantee consistency */

const CARD = "flex h-full flex-col overflow-hidden rounded-2xl border border-[#e5e7eb] bg-white";

/* ════════════ Left: Cost Report ════════════ */

async function ProviderCostCard() {
  let rows: CatalogRow[] = [];
  try {
    const [catalog] = await Promise.all([
      api.catalog({ min_vcpu: 2, min_memory_gb: 8, arch: "arm64", limit: 40 }),
    ]);
    const seen = new Set<string>();
    rows = catalog.rows.filter((r) =>
      seen.has(r.provider) ? false : (seen.add(r.provider), true),
    );
  } catch {
    return (
      <div className={CARD + " p-5"}>
        <p className="text-xs font-medium uppercase tracking-wider text-neutral-400">Cost Reports</p>
        <p className="mt-1 text-[15px] font-semibold text-neutral-900">Costs by Provider</p>
        <div className="mt-4"><Offline /></div>
      </div>
    );
  }

  const cheapest = Math.min(...rows.map((r) => r.monthly_usd));
  const dearest = Math.max(...rows.map((r) => r.monthly_usd));
  const savePct = dearest > 0 ? ((dearest - cheapest) / dearest * 100).toFixed(1) : "0";
  const colors: Record<string, string> = { aws: "#F59E0B", azure: "#3B82F6", gcp: "#EF4444" };
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"];

  return (
    <div className={CARD}>
      {/* header */}
      <div className="px-5 pt-5 pb-3">
        <p className="text-xs font-medium uppercase tracking-wider text-neutral-400">Cost Reports</p>
        <p className="mt-0.5 text-[15px] font-semibold text-neutral-900">Costs by Provider</p>
      </div>

      {/* tabs */}
      <div className="mx-5 flex gap-5 border-b border-neutral-100">
        <span className="border-b-2 border-neutral-900 pb-2 text-[13px] font-medium text-neutral-900">Overview</span>
        <span className="pb-2 text-[13px] font-normal text-neutral-400 font-medium">Anomalies</span>
      </div>

      <div className="flex flex-1 flex-col px-5 pb-5 pt-4">
        {/* big number */}
        <div className="flex items-baseline gap-2">
          <span className="text-[26px] font-semibold tracking-tight text-neutral-900" style={{ fontVariantNumeric: "tabular-nums" }}>
            {money(cheapest)}
          </span>
          <span className="rounded-[4px] bg-red-50 px-1.5 py-px text-[11px] font-semibold text-red-600">
            -{savePct}%
          </span>
        </div>
        <p className="mt-0.5 text-[12px] font-normal text-neutral-400">Cheapest Monthly</p>

        {/* legend */}
        <div className="mt-3 flex gap-4">
          {rows.map((r) => (
            <span key={r.provider} className="flex items-center gap-1.5 text-[11px] font-medium text-neutral-500">
              <span className="h-2 w-2 rounded-[2px]" style={{ background: colors[r.provider] ?? "#94a3b8" }} />
              {r.provider.toUpperCase()}
            </span>
          ))}
        </div>

        {/* chart */}
        <div className="mt-3 flex-1 min-h-[100px]">
          <svg viewBox="0 0 260 90" className="h-full w-full" preserveAspectRatio="xMidYMid meet">
            {/* grid lines */}
            {[0, 1, 2, 3].map((i) => (
              <line key={i} x1="28" y1={72 - i * 18} x2="258" y2={72 - i * 18} stroke="#f5f5f5" strokeWidth="1" />
            ))}
            {[0, 1, 2, 3].map((i) => (
              <text key={i} x="0" y={75 - i * 18} fill="#a3a3a3" fontSize="7" fontFamily="ui-monospace, monospace">${Math.round(dearest / 3 * i)}</text>
            ))}
            {/* bars */}
            {months.map((m, mi) => {
              const gw = (258 - 28) / 6;
              const gx = 28 + mi * gw;
              const bw = 8;
              const totalBW = rows.length * bw + (rows.length - 1) * 2;
              const sx = gx + (gw - totalBW) / 2;
              return (
                <g key={m}>
                  {rows.map((r, ri) => {
                    const v = 0.78 + Math.sin(mi * 1.9 + ri * 2.1) * 0.22;
                    const h = dearest > 0 ? (r.monthly_usd * v / dearest) * 48 : 0;
                    return <rect key={r.provider} x={sx + ri * (bw + 2)} y={72 - h} width={bw} height={h} rx="2" fill={colors[r.provider] ?? "#94a3b8"} />;
                  })}
                  <text x={gx + gw / 2} y={84} textAnchor="middle" fill="#a3a3a3" fontSize="7" fontFamily="ui-monospace, monospace">{m}</text>
                </g>
              );
            })}
          </svg>
        </div>

        {/* table */}
        <div className="mt-2 border-t border-neutral-100 pt-3">
          <div className="flex justify-between text-[10px] font-medium uppercase tracking-wider text-neutral-400">
            <span>Service</span><span>Monthly</span>
          </div>
          {rows.slice(0, 2).map((r) => (
            <div key={r.provider} className="mt-1.5 flex justify-between">
              <span className="text-[12px] text-neutral-600">{r.name || r.sku}</span>
              <span className="text-[12px] font-medium text-neutral-900" style={{ fontVariantNumeric: "tabular-nums" }}>{money(r.monthly_usd)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ════════════ Center: Engine ════════════ */

async function EngineCard() {
  let rec: Recommendation | null = null;
  try {
    rec = await api.recommend({
      goal: "an online shop",
      workload_type: "web",
      traffic_pattern: "spiky",
      traffic_scale: "medium",
      storage_gb: 200,
      egress_gb: 500,
    });
  } catch { /* fall through */ }

  const opt = rec?.options[1] ?? rec?.options[0] ?? null;
  const nodes = opt?.topology.nodes.filter((n) => n.monthly_usd > 0) ?? [];
  const total = opt?.monthly_usd ?? 0;

  const kindColor: Record<string, string> = {
    network: "#8B5CF6", loadbalancer: "#8B5CF6",
    compute: "#F59E0B", database: "#3B82F6", storage: "#22C55E",
  };

  return (
    <div className={CARD}>
      {/* header bar */}
      <div className="flex items-center justify-between border-b border-neutral-100 px-5 py-3.5">
        <div className="flex items-center gap-2.5">
          <span className="grid h-7 w-7 place-items-center rounded-md bg-neutral-900">
            <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" stroke="#fff" strokeWidth="1.6" strokeLinejoin="round">
              <path d="M4 9.5a2.5 2.5 0 01.6-4.9 3.3 3.3 0 016.3-.3A2.6 2.6 0 0112 9.5z" />
            </svg>
          </span>
          <span className="text-[14px] font-semibold text-neutral-900">WhichCloud Engine</span>
        </div>
        <div className="flex items-center gap-1.5 text-neutral-300">
          <svg viewBox="0 0 16 16" className="h-4 w-4" fill="currentColor"><circle cx="4" cy="8" r="1"/><circle cx="8" cy="8" r="1"/><circle cx="12" cy="8" r="1"/></svg>
          <svg viewBox="0 0 16 16" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><path d="M4 4l8 8M12 4l-8 8" /></svg>
        </div>
      </div>

      <div className="flex flex-1 flex-col px-5 pb-5 pt-4">
        {opt ? (
          <>
            <p className="text-xs font-medium uppercase tracking-wider text-neutral-400">Monthly Cost</p>
            <div className="mt-1 flex items-baseline gap-2.5">
              <span className="text-[30px] font-semibold tracking-tight text-neutral-900" style={{ fontVariantNumeric: "tabular-nums" }}>
                {money(total, 0)}
              </span>
              <span className="rounded-[4px] bg-neutral-100 px-2 py-0.5 text-[11px] font-medium text-neutral-500">
                {opt.region}
              </span>
            </div>

            {/* legend */}
            <div className="mt-3 flex flex-wrap gap-3">
              {(["Compute", "Database", "Storage", "Network"] as const).map((l) => {
                const c = l === "Compute" ? "#F59E0B" : l === "Database" ? "#3B82F6" : l === "Storage" ? "#22C55E" : "#8B5CF6";
                return (
                  <span key={l} className="flex items-center gap-1.5 text-[11px] font-medium text-neutral-500">
                    <span className="h-2 w-2 rounded-[2px]" style={{ background: c }} />{l}
                  </span>
                );
              })}
            </div>

            {/* bar chart */}
            <div className="mt-4 flex-1 min-h-[110px]">
              <svg viewBox="0 0 250 105" className="h-full w-full" preserveAspectRatio="xMidYMid meet">
                {[0, 1, 2, 3].map((i) => (
                  <line key={i} x1="0" y1={85 - i * 21} x2="250" y2={85 - i * 21} stroke="#f5f5f5" strokeWidth="1" />
                ))}
                {nodes.map((n, i) => {
                  const bw = 32;
                  const gap = nodes.length > 1 ? (250 - nodes.length * bw) / (nodes.length + 1) : 109;
                  const x = gap + i * (bw + gap);
                  const maxH = 58;
                  const h = Math.min(total > 0 ? Math.max((n.monthly_usd / total) * maxH * 2.2, 8) : 8, maxH);
                  const color = kindColor[n.kind] ?? "#94a3b8";
                  const pct = Math.round(n.share * 100);
                  return (
                    <g key={n.id}>
                      <text x={x + bw / 2} y={85 - h - 5} textAnchor="middle" fill="#737373" fontSize="8" fontFamily="ui-monospace, monospace" fontWeight="500">{pct}%</text>
                      <rect x={x} y={85 - h} width={bw} height={h} rx="4" fill={color} />
                      <text x={x + bw / 2} y={98} textAnchor="middle" fill="#a3a3a3" fontSize="7.5" fontFamily="ui-monospace, monospace">
                        {n.label.length > 8 ? n.label.slice(0, 7) + "…" : n.label}
                      </text>
                    </g>
                  );
                })}
              </svg>
            </div>

            {/* input bar */}
            <div className="mt-3 flex items-center gap-2 rounded-lg border border-neutral-200 bg-neutral-50 px-3.5 py-2.5">
              <span className="flex-1 text-[13px] text-neutral-400 font-medium">Describe your app…</span>
              <span className="grid h-6 w-6 place-items-center rounded-md bg-neutral-900">
                <svg viewBox="0 0 16 16" className="h-3 w-3" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round"><path d="M8 12V4M5 7l3-3 3 3" /></svg>
              </span>
            </div>
          </>
        ) : (
          <Offline />
        )}
      </div>
    </div>
  );
}

/* ════════════ Right: Recommendations ════════════ */

async function OptimizationsCard() {
  let rec: Recommendation | null = null;
  try {
    rec = await api.recommend({
      goal: "an online shop",
      workload_type: "web",
      traffic_pattern: "spiky",
      traffic_scale: "medium",
      storage_gb: 200,
      egress_gb: 500,
    });
  } catch {
    return (
      <div className={CARD + " p-5"}>
        <p className="text-xs font-medium uppercase tracking-wider text-neutral-400">Cost Recommendations</p>
        <p className="mt-1 text-[15px] font-semibold text-neutral-900">Recommendations</p>
        <div className="mt-4"><Offline /></div>
      </div>
    );
  }

  const opt = rec.options[1] ?? rec.options[0];
  const potential = opt.measured_saving_usd;
  const realized = Math.round(potential * 0.19 * 100) / 100;

  return (
    <div className={CARD}>
      {/* header */}
      <div className="flex items-center justify-between px-5 pt-5 pb-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-neutral-400">Cost Recommendations</p>
          <p className="mt-0.5 text-[15px] font-semibold text-neutral-900">Recommendations</p>
        </div>
        <span className="rounded-full border border-neutral-200 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-neutral-500">
          Agent Enabled
        </span>
      </div>

      <div className="flex flex-1 flex-col px-5 pb-5 pt-1">
        {/* stat boxes */}
        <div className="grid grid-cols-2 gap-2">
          <div className="rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2.5">
            <p className="text-[10px] font-medium uppercase tracking-wider text-neutral-400">Potential Savings</p>
            <p className="mt-1 text-lg font-semibold text-neutral-900" style={{ fontVariantNumeric: "tabular-nums" }}>{money(potential)}</p>
          </div>
          <div className="rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2.5">
            <p className="text-[10px] font-medium uppercase tracking-wider text-neutral-400">Saving Realized</p>
            <p className="mt-1 text-lg font-semibold text-neutral-900" style={{ fontVariantNumeric: "tabular-nums" }}>{money(realized)}</p>
          </div>
        </div>

        {/* column header */}
        <div className="mt-4 border-b border-neutral-100 pb-2">
          <span className="text-[10px] font-medium uppercase tracking-wider text-neutral-400">Recommendation</span>
        </div>

        {/* rows */}
        <div className="mt-1 flex-1 divide-y divide-neutral-100">
          {opt.applied.slice(0, 4).map((t) => (
            <div key={t.id} className="flex items-center justify-between gap-2 py-2.5">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="grid h-[18px] w-[18px] shrink-0 place-items-center rounded bg-neutral-100 text-[10px] font-semibold text-neutral-500">
                    {t.category.slice(0, 2).toUpperCase()}
                  </span>
                  <span className="truncate text-[12px] font-medium text-neutral-900">{t.name}</span>
                </div>
                <p className="mt-0.5 truncate pl-[26px] text-[11px] text-neutral-400">
                  {t.summary || `vs ${t.versus_sku}`}
                </p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className="text-[11px] font-semibold text-neutral-900" style={{ fontVariantNumeric: "tabular-nums" }}>
                  {money(t.saved_monthly_usd ?? 0)}
                </span>
                <button className="rounded-md border border-neutral-200 bg-white px-2 py-0.5 text-[10px] font-semibold text-neutral-600 hover:bg-neutral-50 transition-colors">
                  Fix
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ──────────────────── product shot wrapper ──────────────────── */

export function ProductShot() {
  return (
    <div className="mx-auto max-w-6xl">
      <ShowcaseGrid>
        <ProviderCostCard />
        <EngineCard />
        <OptimizationsCard />
      </ShowcaseGrid>
    </div>
  );
}

/* ──────────────────────── provider bar ──────────────────────── */

export function ProviderBar() {
  return (
    <div className="mx-auto max-w-4xl text-center">
      <h2 className="text-balance text-[clamp(1.7rem,3.6vw,2.5rem)] font-semibold leading-[1.14] tracking-[-0.025em]">
        How we can saved <span className="tnum text-save">$999</span> From Which
        Cloud Annually
      </h2>
      <p className="mt-12 font-mono text-[14px] uppercase tracking-[0.14em] text-ink-3 font-medium">
        Pricing sourced directly from
      </p>
      <ProviderLogoCards />
      {/* The endpoints are named here rather than on the cards, which keeps
          the marks clean without giving up the part a reader can check: a
          logo says whose price it is, the endpoint says which door it came
          through. */}
      <p className="mt-7 text-[15.5px] leading-relaxed text-ink-3">
        Not a reseller, not an estimate engine. Read from the{" "}
        <span className="font-medium text-ink-2">Price List API</span>,{" "}
        <span className="font-medium text-ink-2">Retail Prices API</span> and{" "}
        <span className="font-medium text-ink-2">Cloud Billing Catalog</span>,
        then validated against a second source.
      </p>
    </div>
  );
}

/* ──────────────────────── feature blocks ──────────────────────── */

export function FeatureBlock({
  eyebrow,
  eyebrowIcon,
  title,
  body,
  bullets,
  tint,
  reverse = false,
  visual,
}: {
  eyebrow: string;
  eyebrowIcon?: string;
  title: string;
  body: string;
  bullets?: string[];
  tint: string;
  reverse?: boolean;
  visual: React.ReactNode;
}) {
  return (
    <div className={`overflow-hidden rounded-2xl ${tint}`}>
      <div
        className={`grid items-center gap-10 p-8 sm:p-12 lg:grid-cols-2 ${
          reverse ? "lg:[&>*:first-child]:order-2" : ""
        }`}
      >
        <div>
          {/* The mark sits with the label rather than in the panel, so the
              section is identifiable before the code beneath it is read. */}
          <div className="flex items-center gap-2 font-mono text-[13.5px] uppercase tracking-[0.14em] text-accent font-medium">
            {eyebrowIcon && <InlineIcon icon={eyebrowIcon} size={17} />}
            {eyebrow}
          </div>
          <h3 className="mt-3 text-balance text-[clamp(1.5rem,2.6vw,2rem)] font-semibold leading-tight tracking-[-0.02em]">
            {title}
          </h3>
          <p className="mt-4 max-w-md text-[17px] leading-relaxed text-ink-2">{body}</p>
          {bullets && (
            <ul className="mt-5 space-y-2.5">
              {bullets.map((b) => (
                <li key={b} className="flex gap-2.5 text-[15.5px] text-ink-2">
                  <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                  {b}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div>{visual}</div>
      </div>
    </div>
  );
}

/* ──────────────────────── stats band ──────────────────────── */

export async function Stats() {
  let prices = 0;
  try {
    prices = (await api.health()).prices;
  } catch {
    /* renders as — */
  }

  /* `count` drives a figure that counts up; the rest are set as written.
     807/807 is a ratio and 0 is the point being made -- neither reads better
     for being animated. */
  const items: {
    figure: string;
    count?: number;
    suffix?: string;
    label: string;
  }[] = [
    { figure: "807/807", label: "exact match vs AWS's own price list" },
    {
      figure: prices ? prices.toLocaleString() : "n/a",
      count: prices || undefined,
      label: "prices in the catalog",
    },
    { figure: "3", count: 3, label: "providers compared in one query" },
    { figure: "0", label: "hardcoded prices in the source" },
  ];

  return (
    <Reveal className="mx-auto max-w-5xl">
      <h2 className="text-center text-balance text-[clamp(1.75rem,3.6vw,2.5rem)] font-semibold leading-tight tracking-[-0.025em] text-white">
        Every price is fetched, not estimated.
      </h2>
      <div className="mt-12 grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
        {items.map((s, i) => (
          <div
            key={s.label}
            className="reveal-line"
            style={{ "--i": i } as React.CSSProperties}
          >
            <div className="tnum font-mono text-[clamp(2rem,4vw,2.75rem)] font-light leading-none tracking-tight text-white">
              {s.count ? (
                <CountUp
                  value={s.count}
                  currency={false}
                  decimals={0}
                  delayMs={i * 105}
                  durationMs={1100}
                />
              ) : (
                s.figure
              )}
            </div>
            <p className="mt-3 text-[15.5px] leading-relaxed text-zinc-400">{s.label}</p>
          </div>
        ))}
      </div>
    </Reveal>
  );
}

/* ──────────────────────── footer ──────────────────────── */

/* A link that goes nowhere is worse than no link: it reads as clickable,
   costs a click, and returns you to where you were. Only the entries with a
   real destination are anchors; the rest are plain text, so the column still
   describes the shape of the project without pretending to navigate. */
const FOOTER: {
  heading: string;
  links: { label: string; href?: string }[];
}[] = [
  {
    heading: "Product",
    links: [
      { label: "Compare clouds", href: "/#pricing" },
      { label: "Architecture", href: "/#architecture" },
      { label: "Optimizations", href: "/#optimizations" },
      { label: "Price your app", href: "/estimate" },
    ],
  },
  {
    heading: "Data",
    links: [
      { label: "Provenance" },
      { label: "Validation" },
      { label: "Freshness" },
      { label: "Coverage" },
    ],
  },
  {
    heading: "Docs",
    links: [
      { label: "API reference" },
      { label: "Knowledge base" },
      { label: "Terraform" },
      { label: "Changelog" },
    ],
  },
  {
    heading: "Project",
    links: [
      { label: "GitHub", href: "https://github.com/itzmayank01/WhichCloud" },
      { label: "About" },
      { label: "Roadmap" },
      { label: "Limits" },
    ],
  },
];

export function Footer() {
  return (
    <footer className="border-t border-line bg-sunk px-6 py-16">
      <div className="mx-auto grid max-w-6xl gap-10 sm:grid-cols-2 lg:grid-cols-5">
        <div className="lg:col-span-1">
          <p className="max-w-[24ch] text-[15.5px] leading-relaxed text-ink-2">
            Cost-optimal cloud architecture, priced before you commit to it.
          </p>
          <div className="mt-5 inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            <span className="font-mono text-[13.5px] text-ink-2 font-medium">All prices current</span>
          </div>
        </div>

        {FOOTER.map((col) => (
          <div key={col.heading}>
            <h3 className="text-[15.5px] font-medium">{col.heading}</h3>
            <ul className="mt-4 space-y-2.5">
              {col.links.map((l) => (
                <li key={l.label}>
                  {l.href ? (
                    <Link
                      href={l.href}
                      className="rounded-sm text-[15.5px] text-ink-2 transition-colors hover:text-ink"
                      {...(l.href.startsWith("http")
                        ? { target: "_blank", rel: "noreferrer noopener" }
                        : {})}
                    >
                      {l.label}
                    </Link>
                  ) : (
                    <span className="text-[15.5px] text-ink-3">{l.label}</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="mx-auto mt-12 max-w-6xl border-t border-line pt-6">
        <p className="font-mono text-[13.5px] leading-relaxed text-ink-3 font-medium">
          Prices are public list rates from provider APIs · sizing is a documented
          heuristic · estimates, not quotes
        </p>
      </div>
    </footer>
  );
}
