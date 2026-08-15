import { api, freshness, money, type CatalogRow } from "@/lib/api";

export const revalidate = 300;

/**
 * The live index — three clouds priced for one benchmark machine.
 *
 * This is the only element on the page that exists purely to be believed, so
 * it carries a real fetched-at stamp rather than implying the price is live.
 */
async function LiveIndex() {
  let rows: CatalogRow[] = [];
  let stamp: string | null = null;

  try {
    const [catalog, health] = await Promise.all([
      api.catalog({ min_vcpu: 2, min_memory_gb: 8, arch: "arm64", limit: 40 }),
      api.health(),
    ]);
    // Cheapest row per provider — the catalog is already sorted by price.
    const seen = new Set<string>();
    rows = catalog.rows.filter((r) =>
      seen.has(r.provider) ? false : (seen.add(r.provider), true),
    );
    stamp = health.last_updated;
  } catch {
    return (
      <div className="rounded-lg border border-caution/25 bg-caution-wash px-5 py-4">
        <p className="text-sm text-ink-2">
          Price catalog unreachable. Start Postgres and the API:
        </p>
        <code className="mt-2 block font-mono text-[12px] text-ink">
          docker compose -f infra/docker-compose.yml up -d
          <br />
          uvicorn whichcloud.api:app --port 8000
        </code>
      </div>
    );
  }

  const cheapest = Math.min(...rows.map((r) => r.monthly_usd));

  return (
    <div className="w-full max-w-3xl">
      <div className="mb-3 font-mono text-[10.5px] uppercase tracking-[0.14em] text-ink-3">
        Same machine · 2 vCPU · 8 GB · ARM · India
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        {rows.map((row) => {
          const wins = row.monthly_usd === cheapest;
          return (
            <div
              key={row.provider}
              className={`rounded-lg border p-5 ${
                wins
                  ? "border-accent-line bg-accent-wash"
                  : "border-line bg-surface"
              }`}
            >
              <div className="flex items-center gap-2">
                <span className="font-mono text-[10.5px] uppercase tracking-[0.1em] text-ink-3">
                  {row.provider}
                </span>
                {wins && (
                  <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-label="cheapest" />
                )}
              </div>
              <div className="tnum mt-2 font-mono text-[28px] font-light tracking-tight">
                {money(row.monthly_usd)}
              </div>
              <div className="mt-1 font-mono text-[11px] text-ink-3">{row.sku}</div>
            </div>
          );
        })}
      </div>

      {stamp && (
        <div className="mt-3 flex items-center gap-2 font-mono text-[10.5px] text-ink-3">
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
          fetched {freshness(stamp)} from provider APIs
        </div>
      )}
    </div>
  );
}

export default function Home() {
  return (
    <div className="mx-auto max-w-5xl px-6 py-24 sm:py-32">
      <h1 className="max-w-2xl text-[clamp(2.25rem,5.5vw,3.75rem)] font-light leading-[1.04] tracking-[-0.03em] text-balance">
        Know what it costs
        <br />
        before you build it.
      </h1>

      <p className="mt-6 max-w-xl text-[17px] leading-relaxed text-ink-2">
        Describe your app in a sentence. Get three priced architectures across AWS,
        Azure and Google — with the optimizations that lower the bill.
      </p>

      <div className="mt-16">
        <LiveIndex />
      </div>
    </div>
  );
}
