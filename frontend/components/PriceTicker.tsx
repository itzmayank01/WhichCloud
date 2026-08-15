import { api, money, type CatalogRow } from "@/lib/api";

/**
 * A continuously scrolling band of live prices.
 *
 * Static pages claim their data is fresh; a moving one demonstrates it. Every
 * figure here is a real row from the catalog, and the strip is duplicated so
 * the loop is seamless without JavaScript — CSS translates one copy the width
 * of the other and starts again.
 */
export async function PriceTicker() {
  let rows: CatalogRow[] = [];
  try {
    const catalog = await api.catalog({ min_vcpu: 2, min_memory_gb: 4, limit: 18 });
    rows = catalog.rows;
  } catch {
    return null;
  }
  if (!rows.length) return null;

  const strip = (
    <div className="flex shrink-0 items-center gap-8 pr-8">
      {rows.map((r, i) => (
        <span key={`${r.provider}-${r.sku}-${i}`} className="flex shrink-0 items-baseline gap-2.5">
          <span className="font-mono text-[13px] uppercase tracking-[0.08em] text-ink-3">
            {r.provider}
          </span>
          <span className="font-mono text-[14px] text-ink-2">{r.sku}</span>
          <span className="tnum font-mono text-[15px] font-medium text-ink">
            {money(r.monthly_usd)}
          </span>
          <span className="text-[13px] text-ink-3">/mo</span>
          <span className="ml-4 h-3 w-px bg-line-strong" aria-hidden />
        </span>
      ))}
    </div>
  );

  return (
    <div className="relative overflow-hidden border-y border-line bg-surface py-3.5">
      {/* edges fade so the loop point is never visible */}
      <div className="pointer-events-none absolute inset-y-0 left-0 z-10 w-24 bg-gradient-to-r from-canvas to-transparent" />
      <div className="pointer-events-none absolute inset-y-0 right-0 z-10 w-24 bg-gradient-to-l from-canvas to-transparent" />
      <div className="flex w-max animate-[ticker_48s_linear_infinite] hover:[animation-play-state:paused]">
        {strip}
        {strip}
      </div>
    </div>
  );
}
