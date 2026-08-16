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
    const [compare, techs] = await Promise.all([
      api.compare({
        goal: "an online shop",
        workload_type: "web",
        traffic_pattern: "spiky",
        traffic_scale: "medium",
        storage_gb: 200,
        egress_gb: 500,
      }),
      api.techniques().catch(() => ({ count: 0, techniques: [] })),
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

    /* Only services every cloud prices go into the chart, so the bars compare
       like with like. A segment present on one cloud and absent on another
       would make the shorter bar look cheaper when it is only less complete. */
    const shared = balanced
      .map((r) => new Set(r.option.items.map((i) => i.label.replace(/ ×.*$/, ""))))
      .reduce((a, b) => new Set([...a].filter((x) => b.has(x))));

    const categories = [...shared].sort();

    const data: ShowcaseData = {
      chart: {
        categories,
        clouds: balanced
          .sort((a, b) => a.option.monthly_usd - b.option.monthly_usd)
          .map((r) => {
            const segments = categories.map((label) => ({
              label,
              value: r.option.items
                .filter((i) => i.label.replace(/ ×.*$/, "") === label)
                .reduce((sum, i) => sum + i.monthly_usd, 0),
            }));
            return {
              id: r.id,
              label: LABEL[r.id] ?? r.id,
              total: segments.reduce((sum, s) => sum + s.value, 0),
              segments,
            };
          }),
      },
      quote: "an online shop for India, traffic comes in spikes",
      breakdown: [...win.items]
        .sort((a, b) => b.monthly_usd - a.monthly_usd)
        .slice(0, 5)
        .map((i) => ({
          label: i.label.replace(/ ×.*$/, ""),
          sku: i.sku ?? "—",
          monthly: i.monthly_usd,
        })),
      total: win.monthly_usd,
      saved: richest.option.measured_saving_usd,
      techniquesTested: techs.count ?? 0,
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
