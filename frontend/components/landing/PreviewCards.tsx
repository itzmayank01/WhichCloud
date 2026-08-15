import { api, freshness, money, type CatalogRow, type Recommendation } from "@/lib/api";

/**
 * The product preview under the hero.
 *
 * Three cards showing what the tool actually returns. Every figure is fetched
 * from the running API — no mocked screenshots, because a cost tool that
 * illustrates itself with invented numbers has already lost the argument.
 * When the catalog is unreachable the cards keep their shape and say so.
 */

function Card({
  eyebrow,
  title,
  children,
  className = "",
}: {
  eyebrow: string;
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-xl border border-line bg-surface shadow-[0_1px_2px_rgba(13,20,20,.04),0_12px_32px_-16px_rgba(13,20,20,.18)] ${className}`}
    >
      <div className="border-b border-line px-5 py-3.5">
        <div className="font-mono text-[12px] uppercase tracking-[0.13em] text-ink-3">
          {eyebrow}
        </div>
        <div className="mt-0.5 text-[17px] font-medium tracking-tight">{title}</div>
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

function Unavailable() {
  return (
    <p className="font-mono text-[13px] leading-relaxed text-ink-3">
      Catalog offline — start Postgres and the API to see live figures here.
    </p>
  );
}

async function Prices() {
  let rows: CatalogRow[] = [];
  let stamp: string | null = null;

  try {
    const [catalog, health] = await Promise.all([
      api.catalog({ min_vcpu: 2, min_memory_gb: 8, arch: "arm64", limit: 40 }),
      api.health(),
    ]);
    const seen = new Set<string>();
    rows = catalog.rows.filter((r) =>
      seen.has(r.provider) ? false : (seen.add(r.provider), true),
    );
    stamp = health.last_updated;
  } catch {
    return (
      <Card eyebrow="Live index" title="Same machine, three clouds">
        <Unavailable />
      </Card>
    );
  }

  const cheapest = Math.min(...rows.map((r) => r.monthly_usd));

  return (
    <Card eyebrow="Live index" title="Same machine, three clouds">
      <div className="font-mono text-[12.5px] uppercase tracking-[0.12em] text-ink-3">
        2 vCPU · 8 GB · ARM · India
      </div>

      <div className="mt-4 space-y-2.5">
        {rows.map((row) => {
          const wins = row.monthly_usd === cheapest;
          return (
            <div
              key={row.provider}
              className={`flex items-baseline justify-between rounded-lg px-3 py-2.5 ${
                wins ? "bg-accent-wash" : "bg-sunk"
              }`}
            >
              <div className="flex items-baseline gap-2">
                <span className="font-mono text-[13px] uppercase tracking-[0.08em] text-ink-2">
                  {row.provider}
                </span>
                {wins && (
                  <span className="font-mono text-[12px] uppercase tracking-[0.1em] text-accent">
                    cheapest
                  </span>
                )}
              </div>
              <div className="flex items-baseline gap-2.5">
                <span className="font-mono text-[12.5px] text-ink-3">{row.sku}</span>
                <span
                  className={`tnum font-mono text-[19px] ${wins ? "text-accent" : "text-ink"}`}
                >
                  {money(row.monthly_usd)}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {stamp && (
        <div className="mt-4 flex items-center gap-2 font-mono text-[12px] text-ink-3">
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
          fetched {freshness(stamp)}
        </div>
      )}
    </Card>
  );
}

async function Optimizations() {
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
      <Card eyebrow="Optimizations" title="Measured, not claimed">
        <Unavailable />
      </Card>
    );
  }

  const balanced = rec.options[1] ?? rec.options[0];

  return (
    <Card eyebrow="Optimizations" title="Measured, not claimed">
      <div className="flex items-baseline justify-between">
        <span className="font-mono text-[12.5px] uppercase tracking-[0.12em] text-ink-3">
          Saved on {balanced.label.toLowerCase()}
        </span>
        <span className="tnum font-mono text-[24px] text-accent">
          {money(balanced.measured_saving_usd)}
        </span>
      </div>

      <div className="mt-4 space-y-3">
        {balanced.applied.slice(0, 3).map((t) => (
          <div key={t.id} className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="truncate text-[15.5px] leading-snug">{t.name}</div>
              <div className="mt-0.5 font-mono text-[12.5px] text-ink-3">
                vs {t.versus_sku}
              </div>
            </div>
            <span className="tnum shrink-0 font-mono text-[15px] text-accent">
              −{money(t.saved_monthly_usd ?? 0)}
            </span>
          </div>
        ))}

        {balanced.advisory.slice(0, 1).map((t) => (
          <div key={t.id} className="flex items-start justify-between gap-3 border-t border-line pt-3">
            <div className="min-w-0">
              <div className="truncate text-[15.5px] leading-snug text-ink-2">{t.name}</div>
              <div className="mt-0.5 font-mono text-[12.5px] text-caution">
                not priced — depends on your workload
              </div>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

async function Breakdown() {
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
      <Card eyebrow="Architecture" title="Three ways to run it" className="lg:-mt-8">
        <Unavailable />
      </Card>
    );
  }

  const balanced = rec.options[1] ?? rec.options[0];
  const nodes = balanced.topology.nodes.filter((n) => n.monthly_usd > 0);

  return (
    <Card eyebrow="Architecture" title="Three ways to run it" className="lg:-mt-8 lg:shadow-[0_2px_4px_rgba(13,20,20,.05),0_28px_60px_-24px_rgba(13,20,20,.28)]">
      <div className="flex gap-1.5">
        {rec.options.map((o) => (
          <div
            key={o.label}
            className={`flex-1 rounded-lg px-2.5 py-2 text-center ${
              o.label === balanced.label
                ? "bg-accent-wash ring-1 ring-accent-line"
                : "bg-sunk"
            }`}
          >
            <div className="truncate font-mono text-[12px] uppercase tracking-[0.08em] text-ink-3">
              {o.label}
            </div>
            <div className="tnum mt-0.5 font-mono text-[15.5px]">
              {money(o.monthly_usd, 0)}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 space-y-2">
        {nodes.map((n) => (
          <div key={n.id} className="flex items-center gap-3">
            <span className="w-[86px] shrink-0 truncate text-[14.5px] text-ink-2">
              {n.label}
            </span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-sunk">
              <div
                className="h-full rounded-full bg-accent"
                style={{ width: `${Math.max(n.share * 100, 2)}%` }}
              />
            </div>
            <span className="tnum w-[62px] shrink-0 text-right font-mono text-[13.5px] text-ink-2">
              {money(n.monthly_usd)}
            </span>
          </div>
        ))}
      </div>

      <div className="mt-4 border-t border-line pt-3 font-mono text-[12.5px] text-ink-3">
        {balanced.shape}
      </div>
    </Card>
  );
}

export function PreviewCards() {
  return (
    <div className="grid gap-5 lg:grid-cols-3">
      <Prices />
      <Breakdown />
      <Optimizations />
    </div>
  );
}
