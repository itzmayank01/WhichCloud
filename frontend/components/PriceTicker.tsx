import { api, money, type CatalogRow } from "@/lib/api";
import Link from "next/link";
import { InlineIcon } from "@/components/landing/InlineIcon";
import { DEFAULT_PRICE_TICKER_ROWS } from "@/lib/defaultLandingData";

/**
 * A continuously scrolling band of live prices.
 *
 * Static pages claim their data is fresh; a moving one demonstrates it. Every
 * figure here is a real row from the catalog, and the strip is duplicated so
 * the loop is seamless without JavaScript — CSS translates one copy the width
 * of the other and starts again.
 *
 * It does not pause under the cursor. Pausing is the usual courtesy for a
 * marquee, on the assumption the reader wants to finish the line they are on;
 * here the band is scenery rather than something to read, and stopping dead
 * whenever the pointer crosses it looked like the page had hung.
 */
/** The mark stands in for the provider's name, which the wordmarks carry. */
const MARK: Record<string, string> = {
  aws: "logos:aws",
  azure: "logos:microsoft-azure",
  gcp: "logos:google-cloud",
};

export async function PriceTicker() {
  let rows: CatalogRow[] = DEFAULT_PRICE_TICKER_ROWS;
  try {
    const timeout = new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error("ticker timeout")), 1200),
    );
    const catalogPromise = api.catalog({ min_vcpu: 2, min_memory_gb: 4, limit: 18 });
    const catalog = await Promise.race([catalogPromise, timeout]);
    if (catalog.rows?.length) {
      rows = catalog.rows;
    }
  } catch {
    // Keep DEFAULT_PRICE_TICKER_ROWS seamlessly
  }

  const strip = (
    <div className="flex shrink-0 items-center gap-8 pr-8">
      {rows.map((r, i) => (
        /* Each row goes to the index it came from. The band was the one thing
           on the page already inviting the eye and the only one that led
           nowhere. */
        <Link
          key={`${r.provider}-${r.sku}-${i}`}
          href="/prices"
          className="flex shrink-0 items-baseline gap-2.5 rounded-sm transition-opacity hover:opacity-70"
        >
          <InlineIcon
            icon={MARK[r.provider] ?? MARK.aws}
            size={15}
            className="shrink-0 self-center"
          />
          <span className="font-mono text-[14px] text-ink-2 font-medium">{r.sku}</span>
          <span className="tnum font-mono text-[15px] font-medium text-ink">
            {money(r.monthly_usd)}
          </span>
          <span className="text-[13px] text-ink-3 font-medium">/mo</span>
          <span className="ml-4 h-3 w-px bg-line-strong" aria-hidden />
        </Link>
      ))}
    </div>
  );

  return (
    <div className="relative overflow-hidden border-y border-line bg-surface py-3.5">
      {/* edges fade so the loop point is never visible */}
      <div className="pointer-events-none absolute inset-y-0 left-0 z-10 w-24 bg-gradient-to-r from-canvas to-transparent" />
      <div className="pointer-events-none absolute inset-y-0 right-0 z-10 w-24 bg-gradient-to-l from-canvas to-transparent" />
      <div className="flex w-max animate-[ticker_48s_linear_infinite]">
        {strip}
        {strip}
      </div>
    </div>
  );
}
