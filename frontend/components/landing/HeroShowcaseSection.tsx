import { HeroShowcase, type ShowcaseData } from "@/components/landing/HeroShowcase";
import { api } from "@/lib/api";

/**
 * Fills the hero showcase from one comparison.
 *
 * A single /compare call supplies all three panels: the per-cloud totals, the
 * cheapest complete option's line items, and the techniques it applied with
 * what each measured. Nothing in the shot is written down.
 *
 * Renders nothing when the API is unreachable. A product shot of a pricing
 * tool showing invented prices is worse than no product shot.
 */

const LABEL: Record<string, string> = {
  aws: "AWS",
  azure: "Microsoft Azure",
  gcp: "Google Cloud",
};

export async function HeroShowcaseSection() {
  try {
    const [compare, catalog, techs, health] = await Promise.all([
      api.compare({
        goal: "an online shop",
        workload_type: "web",
        traffic_pattern: "spiky",
        traffic_scale: "medium",
        storage_gb: 200,
        egress_gb: 500,
      }),
      api.catalog({ region: "india", min_vcpu: 2, min_memory_gb: 4, limit: 60 }),
      api.techniques().catch(() => ({ count: 0, techniques: [] })),
      api.health().catch(() => ({ prices: 0, providers: [] as string[] })),
    ]);

    const balanced = Object.entries(compare.clouds)
      .map(([id, options]) => ({
        id,
        option: options.find((o) => o.label === "Balanced") ?? options[0],
      }))
      .filter((r) => r.option?.complete);

    if (balanced.length < 2) return null;

    const cheapest = balanced.reduce((a, b) =>
      a.option.monthly_usd <= b.option.monthly_usd ? a : b,
    );
    const win = cheapest.option;

    /* The savings panel reads whichever option actually applied the most
       techniques, not necessarily the cheapest one. On this workload the
       cheapest cloud happens to apply one and another applies three, and a
       panel headed "ways to pay less" showing a single row undersells work
       that genuinely happened. */
    const richest = balanced.reduce((a, b) =>
      (b.option.applied?.length ?? 0) > (a.option.applied?.length ?? 0) ? b : a,
    );

    // One row per cloud, cheapest first, so the sample is not all one provider.
    const seen = new Set<string>();
    const sample = [...(catalog.rows ?? [])]
      .sort((a, b) => a.monthly_usd - b.monthly_usd)
      .filter((r) => (seen.has(r.provider) ? false : (seen.add(r.provider), true)))
      .slice(0, 5);

    const data: ShowcaseData = {
      catalog: {
        rows: sample.map((r) => ({
          provider: r.provider,
          name: r.name || r.sku,
          vcpu: r.vcpu ?? null,
          memory: r.memory_gb ?? null,
          monthly: r.monthly_usd,
        })),
        /* health.prices is the catalog; catalog.count is only how many rows
           came back, which is the limit that was asked for. Reporting 60 for
           a catalog of several thousand would be wrong in the direction that
           matters least to notice and most to fix. */
        total: health.prices || catalog.count || sample.length,
        clouds:
          health.providers?.length ||
          new Set((catalog.rows ?? []).map((r) => r.provider)).size,
      },
      techniquesTested: techs.count ?? 0,
      breakdown: [...win.items]
        .sort((a, b) => b.monthly_usd - a.monthly_usd)
        .slice(0, 5)
        .map((i) => ({
          label: i.label.replace(/ ×.*$/, ""),
          monthly: i.monthly_usd,
        })),
      total: win.monthly_usd,
      saved: richest.option.measured_saving_usd,
      applied: (richest.option.applied ?? [])
        .filter((a) => (a.saved_monthly_usd ?? 0) > 0)
        .sort((a, b) => (b.saved_monthly_usd ?? 0) - (a.saved_monthly_usd ?? 0))
        .slice(0, 4)
        .map((a) => ({
          name: a.name,
          saved: a.saved_monthly_usd ?? 0,
          versus: a.versus_sku ?? "the default",
          category: a.category ?? "compute",
        })),
    };

    return <HeroShowcase data={data} />;
  } catch {
    return null;
  }
}
