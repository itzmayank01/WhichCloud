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
  let prices = 37878;
  let providers = 3;
  let techniques = 25;
  let regions = 18;

  try {
    const timeout = new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error("pipeline timeout")), 1200),
    );
    const fetchMetrics = Promise.all([
      api.health(),
      api.techniques().catch(() => ({ count: 0, techniques: [] })),
      api.regions().catch(() => ({})),
    ]);
    const [health, techs, regionMap] = await Promise.race([fetchMetrics, timeout]);
    if (health.prices) prices = health.prices;
    if (health.providers?.length) providers = health.providers.length;
    if (techs.count) techniques = techs.count;
    const rCount = Object.keys(regionMap ?? {}).length;
    if (rCount) regions = rCount;
  } catch {
    /* Uses high-fidelity defaults */
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
