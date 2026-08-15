import { Pipeline, type Stage } from "@/components/landing/Pipeline";
import { api } from "@/lib/api";

/**
 * Feeds the pipeline the counts of what each stage actually works with.
 *
 * The catalog size, the number of techniques and the providers covered are
 * read from the running service, so the figures on the cards move when the
 * catalog does. Everything falls back to a description rather than a made-up
 * number if the API is unreachable: a stage that says "every published rate"
 * is honest when offline, and one that says "4,615 prices" would not be.
 */
export async function PipelineSection() {
  let prices = 0;
  let providers = 0;
  let techniques = 0;
  let regions = 0;

  try {
    const [health, techs, regionMap] = await Promise.all([
      api.health(),
      api.techniques().catch(() => ({ count: 0, techniques: [] })),
      api.regions().catch(() => ({})),
    ]);
    prices = health.prices ?? 0;
    providers = health.providers?.length ?? 0;
    techniques = techs.count ?? techs.techniques?.length ?? 0;
    regions = Object.keys(regionMap ?? {}).length;
  } catch {
    /* fall through to the descriptive labels below */
  }

  const stages: Stage[] = [
    {
      key: "sentence",
      title: "You describe it",
      detail:
        "One sentence, or a short form. No cloud account, no agent, nothing to install.",
      metric: "plain English in",
      icon: "sentence",
    },
    {
      key: "parse",
      title: "It becomes a requirement",
      detail:
        "Workload, traffic shape, scale and region, with anything assumed reported back to you.",
      metric: regions ? `${regions} regions supported` : "structured output",
      icon: "parse",
    },
    {
      key: "catalog",
      title: "The catalog is searched",
      detail:
        "Every machine that meets the spec, on each cloud, at that provider's published rate.",
      metric: prices
        ? `${prices.toLocaleString()} prices · ${providers} clouds`
        : "every published rate",
      icon: "catalog",
    },
    {
      key: "optimize",
      title: "Optimizations are measured",
      detail:
        "Each technique is priced against the option it replaces. Only what is cheaper survives.",
      metric: techniques
        ? `${techniques} techniques tested`
        : "measured, not claimed",
      icon: "optimize",
    },
    {
      key: "output",
      title: "You get three options",
      detail:
        "Cheapest, balanced and most reliable, each drawn as an architecture and written as Terraform.",
      metric: "3 options · 1 diagram · main.tf",
      icon: "output",
    },
  ];

  return <Pipeline stages={stages} />;
}
