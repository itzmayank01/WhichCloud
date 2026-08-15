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
      title: "Tell it what you are building",
      detail:
        "One sentence is enough, like \u201Can online shop for India\u201D. No cloud account, nothing to install.",
      icon: "sentence",
    },
    {
      key: "parse",
      title: "It works out what you need",
      detail:
        "How busy the app will be, how much it stores, which country it runs in. It tells you anything it had to guess.",
      metric: regions ? `${regions} regions` : undefined,
      icon: "parse",
    },
    {
      key: "catalog",
      title: "It checks what every cloud charges",
      detail:
        "The real published price of every machine that would do the job, on all three clouds.",
      metric: prices
        ? `${prices.toLocaleString()} prices · ${providers} clouds`
        : undefined,
      icon: "catalog",
    },
    {
      key: "optimize",
      title: "It looks for ways to pay less",
      detail:
        "It tries each known trick, works out what it would actually save you, and keeps only the ones that do.",
      metric: techniques ? `${techniques} techniques tried` : undefined,
      icon: "optimize",
    },
    {
      key: "output",
      title: "You get three plans to pick from",
      detail:
        "Cheapest, balanced, and the most reliable. Each one drawn as a diagram, with the cost of every part.",
      icon: "output",
    },
  ];

  return <Pipeline stages={stages} />;
}
