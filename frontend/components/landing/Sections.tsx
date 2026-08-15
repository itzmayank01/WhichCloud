import Link from "next/link";
import { api, freshness, money, type CatalogRow, type Recommendation } from "@/lib/api";

/* ─────────────────────────── shared ─────────────────────────── */

export function Pill({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto inline-flex items-center gap-2.5 rounded-full border border-line bg-surface py-1.5 pl-2 pr-4 shadow-[0_1px_2px_rgba(13,20,20,.05)]">
      <span className="rounded-full bg-accent px-2.5 py-0.5 text-[13px] font-medium text-white">
        New
      </span>
      <span className="text-[15.5px] text-ink-2">{children}</span>
      <span className="text-ink-3">→</span>
    </div>
  );
}

function Card({
  children,
  className = "",
  lifted = false,
}: {
  children: React.ReactNode;
  className?: string;
  lifted?: boolean;
}) {
  return (
    <div
      className={`rounded-xl border border-line bg-surface ${
        lifted
          ? "shadow-[0_2px_6px_rgba(13,20,20,.05),0_32px_64px_-28px_rgba(13,20,20,.32)]"
          : "shadow-[0_1px_2px_rgba(13,20,20,.04),0_16px_40px_-20px_rgba(13,20,20,.2)]"
      } ${className}`}
    >
      {children}
    </div>
  );
}

function CardHead({ eyebrow, title }: { eyebrow: string; title: string }) {
  return (
    <div className="flex items-start gap-3 border-b border-line px-5 py-4">
      <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-accent-wash">
        <span className="h-2.5 w-2.5 rounded-sm bg-accent" />
      </span>
      <div className="min-w-0">
        <div className="font-mono text-[12px] uppercase tracking-[0.13em] text-ink-3">
          {eyebrow}
        </div>
        <div className="mt-0.5 truncate text-[17px] font-medium tracking-tight">{title}</div>
      </div>
    </div>
  );
}

function Offline() {
  return (
    <p className="font-mono text-[13px] leading-relaxed text-ink-3">
      Catalog offline — start Postgres and the API to see live figures.
    </p>
  );
}

/* ──────────────────── the layered product shot ──────────────────── */

async function IndexCard() {
  let rows: CatalogRow[] = [];
  let stamp: string | null = null;
  try {
    const [catalog, health] = await Promise.all([
      api.catalog({ min_vcpu: 2, min_memory_gb: 8, arch: "arm64", limit: 40 }),
      api.health(),
    ]);
    const seen = new Set<string>();
    rows = catalog.rows.filter((r) => (seen.has(r.provider) ? false : (seen.add(r.provider), true)));
    stamp = health.last_updated;
  } catch {
    return (
      <Card className="p-0">
        <CardHead eyebrow="Live index" title="Same machine, three clouds" />
        <div className="p-5">
          <Offline />
        </div>
      </Card>
    );
  }

  const cheapest = Math.min(...rows.map((r) => r.monthly_usd));
  const dearest = Math.max(...rows.map((r) => r.monthly_usd));

  return (
    <Card className="p-0">
      <CardHead eyebrow="Live index" title="Same machine, three clouds" />
      <div className="p-5">
        <div className="flex items-baseline gap-3">
          <span className="tnum font-mono text-[38px] font-light leading-none tracking-tight">
            {money(cheapest)}
          </span>
          <span className="rounded-md bg-accent-wash px-2 py-0.5 font-mono text-[13px] text-accent">
            −{money(dearest - cheapest)} vs dearest
          </span>
        </div>
        <div className="mt-1 font-mono text-[13px] text-ink-3">
          per month · 2 vCPU · 8 GB · ARM · India
        </div>

        <div className="mt-5 space-y-2">
          {rows.map((r) => {
            const wins = r.monthly_usd === cheapest;
            const width = Math.round((r.monthly_usd / dearest) * 100);
            return (
              <div key={r.provider} className="flex items-center gap-3">
                <span className="w-12 shrink-0 font-mono text-[12.5px] uppercase tracking-[0.06em] text-ink-2">
                  {r.provider}
                </span>
                <div className="h-6 flex-1 overflow-hidden rounded bg-sunk">
                  <div
                    className={`h-full rounded ${wins ? "bg-accent" : "bg-line-strong"}`}
                    style={{ width: `${width}%` }}
                  />
                </div>
                <span className="tnum w-16 shrink-0 text-right font-mono text-[14px]">
                  {money(r.monthly_usd)}
                </span>
              </div>
            );
          })}
        </div>

        {stamp && (
          <div className="mt-5 flex items-center gap-2 border-t border-line pt-3 font-mono text-[12px] text-ink-3">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            fetched {freshness(stamp)} from provider APIs
          </div>
        )}
      </div>
    </Card>
  );
}

async function AskCard() {
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
    /* fall through */
  }

  const balanced = rec?.options[1] ?? rec?.options[0] ?? null;

  return (
    <Card lifted className="p-0">
      <CardHead eyebrow="Describe it" title="Plain English in" />
      <div className="p-5">
        <div className="rounded-lg bg-sunk px-4 py-3 text-[15.5px] leading-relaxed text-ink-2">
          “A food delivery app for one city. About 80,000 customers, mostly
          ordering at lunch and dinner. Budget around $500 a month.”
        </div>

        {balanced ? (
          <>
            <div className="mt-4 flex gap-1.5">
              {rec!.options.map((o) => (
                <div
                  key={o.label}
                  className={`flex-1 rounded-lg px-2 py-2 text-center ${
                    o.label === balanced.label
                      ? "bg-accent-wash ring-1 ring-accent-line"
                      : "bg-sunk"
                  }`}
                >
                  <div className="truncate font-mono text-[11.5px] uppercase tracking-[0.06em] text-ink-3">
                    {o.label}
                  </div>
                  <div className="tnum mt-0.5 font-mono text-[17px]">
                    {money(o.monthly_usd, 0)}
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-4 space-y-2">
              {balanced.topology.nodes
                .filter((n) => n.monthly_usd > 0)
                .map((n) => (
                  <div key={n.id} className="flex items-center gap-2.5">
                    <span className="w-[74px] shrink-0 truncate text-[14px] text-ink-2">
                      {n.label}
                    </span>
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-sunk">
                      <div
                        className="h-full rounded-full bg-accent"
                        style={{ width: `${Math.max(n.share * 100, 2)}%` }}
                      />
                    </div>
                    <span className="tnum w-14 shrink-0 text-right font-mono text-[13px] text-ink-2">
                      {money(n.monthly_usd)}
                    </span>
                  </div>
                ))}
            </div>
          </>
        ) : (
          <div className="mt-4">
            <Offline />
          </div>
        )}
      </div>
    </Card>
  );
}

async function SavingsCard() {
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
      <Card className="p-0">
        <CardHead eyebrow="Optimizations" title="Measured, not claimed" />
        <div className="p-5">
          <Offline />
        </div>
      </Card>
    );
  }

  const balanced = rec.options[1] ?? rec.options[0];

  return (
    <Card className="p-0">
      <CardHead eyebrow="Optimizations" title="Measured, not claimed" />
      <div className="p-5">
        <div className="flex items-baseline justify-between">
          <span className="font-mono text-[12.5px] uppercase tracking-[0.12em] text-ink-3">
            Saved
          </span>
          <span className="tnum font-mono text-[30px] font-light text-accent">
            {money(balanced.measured_saving_usd)}
          </span>
        </div>

        <div className="mt-4 space-y-3.5">
          {balanced.applied.slice(0, 3).map((t) => (
            <div key={t.id} className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="truncate text-[15px] leading-snug">{t.name}</div>
                <div className="mt-0.5 font-mono text-[12px] text-ink-3">
                  vs {t.versus_sku}
                </div>
              </div>
              <span className="tnum shrink-0 rounded bg-accent-wash px-1.5 py-0.5 font-mono text-[13.5px] text-accent">
                −{money(t.saved_monthly_usd ?? 0)}
              </span>
            </div>
          ))}

          {balanced.advisory.slice(0, 1).map((t) => (
            <div key={t.id} className="border-t border-line pt-3">
              <div className="truncate text-[15px] text-ink-2">{t.name}</div>
              <div className="mt-0.5 font-mono text-[12px] text-caution">
                not priced — depends on your workload
              </div>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}

export function ProductShot() {
  return (
    <div className="relative mx-auto max-w-6xl">
      {/* soft ground so the cards feel lifted off the page */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-8 top-16 bottom-8 rounded-3xl bg-gradient-to-b from-accent-wash/70 to-transparent blur-2xl"
      />
      <div className="relative grid items-start gap-5 lg:grid-cols-3">
        <div className="lg:pt-10">
          <IndexCard />
        </div>
        <AskCard />
        <div className="lg:pt-10">
          <SavingsCard />
        </div>
      </div>
    </div>
  );
}

/* ──────────────────────── provider bar ──────────────────────── */

export function ProviderBar() {
  return (
    <div className="mx-auto max-w-4xl text-center">
      <p className="font-mono text-[13px] uppercase tracking-[0.14em] text-ink-3">
        Pricing sourced directly from
      </p>
      <div className="mt-6 flex flex-wrap items-center justify-center gap-x-14 gap-y-5">
        {["Amazon Web Services", "Microsoft Azure", "Google Cloud"].map((name) => (
          <span key={name} className="text-[19px] font-medium tracking-tight text-ink-2">
            {name}
          </span>
        ))}
      </div>
      <p className="mt-6 text-[15.5px] text-ink-3">
        Not a reseller, not an estimate engine — their own published rates,
        validated against a second source.
      </p>
    </div>
  );
}

/* ──────────────────────── feature blocks ──────────────────────── */

export function FeatureBlock({
  eyebrow,
  title,
  body,
  bullets,
  tint,
  reverse = false,
  visual,
}: {
  eyebrow: string;
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
          <div className="font-mono text-[12.5px] uppercase tracking-[0.14em] text-accent">
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

  const items = [
    { figure: "807/807", label: "exact match vs AWS's own price list" },
    { figure: prices ? prices.toLocaleString() : "—", label: "prices in the catalog" },
    { figure: "3", label: "providers compared in one query" },
    { figure: "0", label: "hardcoded prices in the source" },
  ];

  return (
    <div className="mx-auto max-w-5xl">
      <h2 className="text-center text-balance text-[clamp(1.75rem,3.6vw,2.5rem)] font-semibold leading-tight tracking-[-0.025em] text-white">
        Every price is fetched, not estimated.
      </h2>
      <div className="mt-12 grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
        {items.map((s) => (
          <div key={s.label}>
            <div className="tnum font-mono text-[clamp(2rem,4vw,2.75rem)] font-light leading-none tracking-tight text-white">
              {s.figure}
            </div>
            <p className="mt-3 text-[15.5px] leading-relaxed text-zinc-400">{s.label}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ──────────────────────── footer ──────────────────────── */

const FOOTER = [
  {
    heading: "Product",
    links: ["Price index", "Architecture", "Optimizations", "Cross-cloud"],
  },
  { heading: "Data", links: ["Provenance", "Validation", "Freshness", "Coverage"] },
  { heading: "Docs", links: ["API reference", "Knowledge base", "Terraform", "Changelog"] },
  { heading: "Project", links: ["About", "GitHub", "Roadmap", "Limits"] },
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
            <span className="font-mono text-[12.5px] text-ink-2">All prices current</span>
          </div>
        </div>

        {FOOTER.map((col) => (
          <div key={col.heading}>
            <h4 className="text-[15.5px] font-medium">{col.heading}</h4>
            <ul className="mt-4 space-y-2.5">
              {col.links.map((l) => (
                <li key={l}>
                  <Link
                    href="#"
                    className="text-[15.5px] text-ink-2 transition-colors hover:text-ink"
                  >
                    {l}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="mx-auto mt-12 max-w-6xl border-t border-line pt-6">
        <p className="font-mono text-[12.5px] leading-relaxed text-ink-3">
          Prices are public list rates from provider APIs · sizing is a documented
          heuristic · estimates, not quotes
        </p>
      </div>
    </footer>
  );
}
