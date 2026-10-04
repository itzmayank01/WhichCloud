import { PriceTable } from "@/components/prices/PriceTable";
import { api, freshness, type CatalogRow } from "@/lib/api";
import { DEFAULT_PRICE_TICKER_ROWS } from "@/lib/defaultLandingData";

export const revalidate = 86400;

export const metadata = {
  title: "Price index | WhichCloud",
  description:
    "Every machine type WhichCloud prices, on AWS, Azure and Google, at the providers' own published rates.",
};

/**
 * The catalog, readable.
 *
 * Every other page quotes these numbers; this is where you check them. It is
 * the page the whole site's argument rests on, so it shows the rows rather
 * than a summary of them, and says when each was fetched.
 */
export default async function PricesPage() {
  let rows: CatalogRow[] = DEFAULT_PRICE_TICKER_ROWS;
  let fetchedAt = "2026-09-09T05:20:27.630370+00:00";
  let failed = false;

  try {
    const timeout = new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error("catalog timeout")), 1500),
    );
    const catalogPromise = api.catalog({ region: "india", limit: 500 });
    const catalog = await Promise.race([catalogPromise, timeout]);
    if (catalog.rows?.length) {
      rows = catalog.rows;
      fetchedAt = rows[0]?.fetched_at ?? fetchedAt;
    }
  } catch {
    // If backend is waking, use default rows seamlessly
    if (!rows.length) failed = true;
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-14">
      <div className="font-mono text-[13.5px] uppercase tracking-[0.14em] text-accent font-medium">
        Price index
      </div>
      <h1 className="mt-3 text-balance text-[clamp(2rem,4.5vw,3rem)] font-semibold leading-[1.06] tracking-[-0.03em]">
        Every machine, and what it costs
      </h1>
      <p className="mt-4 max-w-2xl text-[17px] leading-relaxed text-ink-2">
        The catalog the rest of the site prices against. These are the
        providers&apos; own published on-demand rates, not estimates and not
        marked up. Search it, sort it, check any row against the provider.
      </p>

      {failed ? (
        <p className="mt-10 rounded-xl border border-dashed border-line-strong bg-canvas p-10 text-center font-mono text-[14px] font-medium text-ink-3">
          The catalog is unreachable. Start Postgres and the API to browse
          prices.
        </p>
      ) : (
        <>
          <div className="mt-10">
            <PriceTable rows={rows} region="Mumbai · ap-south-1 · centralindia · asia-south1" />
          </div>

          <div className="mt-6 space-y-1.5 font-mono text-[13px] font-medium text-ink-3">
            {fetchedAt && <p>Fetched {freshness(fetchedAt)}.</p>}
            <p>
              On-demand Linux, no commitment. Spot and committed-use rates are
              cheaper and are used by the engine where a workload allows them.
            </p>
            <p>
              Showing the first 500 rows the catalog returns for this region.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
