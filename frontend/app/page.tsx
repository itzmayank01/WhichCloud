import { api, freshness, money, type CatalogRow } from "@/lib/api";

export const revalidate = 300;

/**
 * The live index — three clouds priced for one benchmark machine.
 *
 * This is the only element on the page that has to be believed, so it carries
 * a real fetched-at stamp rather than implying the price is live.
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
      <p className="font-mono text-xs text-zinc-500">
        Price catalog unreachable — start the API with{" "}
        <code className="text-zinc-700 dark:text-zinc-300">
          uvicorn whichcloud.api:app
        </code>
      </p>
    );
  }

  const cheapest = Math.min(...rows.map((r) => r.monthly_usd));

  return (
    <div className="w-full max-w-3xl">
      <div className="mb-3 font-mono text-[10.5px] uppercase tracking-[0.14em] text-zinc-500">
        2 vCPU · 8 GB · ARM · India
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        {rows.map((row) => {
          const wins = row.monthly_usd === cheapest;
          return (
            <div
              key={row.provider}
              className={`rounded-lg border p-4 ${
                wins
                  ? "border-teal-700/40 bg-teal-50/60 dark:border-teal-400/30 dark:bg-teal-950/30"
                  : "border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900"
              }`}
            >
              <div className="font-mono text-[10.5px] uppercase tracking-[0.1em] text-zinc-500">
                {row.provider}
              </div>
              <div className="mt-1.5 font-mono text-[27px] font-light tabular-nums tracking-tight">
                {money(row.monthly_usd)}
              </div>
              <div className="mt-0.5 font-mono text-[11px] text-zinc-500">{row.sku}</div>
            </div>
          );
        })}
      </div>

      {stamp && (
        <div className="mt-3 flex items-center gap-2 font-mono text-[10.5px] text-zinc-500">
          <span className="h-1.5 w-1.5 rounded-full bg-teal-600 dark:bg-teal-400" />
          fetched {freshness(stamp)} from provider APIs
        </div>
      )}
    </div>
  );
}

export default function Home() {
  return (
    <div className="mx-auto max-w-5xl px-6 py-24 sm:py-32">
      <h1 className="max-w-2xl text-[clamp(2.25rem,5vw,3.5rem)] font-light leading-[1.05] tracking-[-0.03em]">
        Know what it costs
        <br />
        before you build it.
      </h1>

      <p className="mt-6 max-w-xl text-lg leading-relaxed text-zinc-600 dark:text-zinc-400">
        Describe your app in a sentence. Get three priced architectures across AWS,
        Azure and Google — with the optimizations that lower the bill.
      </p>

      <div className="mt-14">
        <LiveIndex />
      </div>
    </div>
  );
}
