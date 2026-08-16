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
    const compare = await api.compare({
      goal: "an online shop",
      workload_type: "web",
      traffic_pattern: "spiky",
      traffic_scale: "medium",
      storage_gb: 200,
      egress_gb: 500,
    });

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

    const data: ShowcaseData = {
      providers: balanced
        .sort((a, b) => a.option.monthly_usd - b.option.monthly_usd)
        .map((r) => ({
          id: r.id,
          label: LABEL[r.id] ?? r.id,
          monthly: r.option.monthly_usd,
          cheapest: r.id === cheapest.id,
        })),
      breakdown: [...win.items]
        .sort((a, b) => b.monthly_usd - a.monthly_usd)
        .slice(0, 5)
        .map((i) => ({
          label: i.label.replace(/ ×.*$/, ""),
          monthly: i.monthly_usd,
        })),
      total: win.monthly_usd,
      saved: win.measured_saving_usd,
      applied: (win.applied ?? [])
        .filter((a) => (a.saved_monthly_usd ?? 0) > 0)
        .sort((a, b) => (b.saved_monthly_usd ?? 0) - (a.saved_monthly_usd ?? 0))
        .slice(0, 3)
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
