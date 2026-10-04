import { MultiCloudArchitecture } from "@/components/MultiCloudArchitecture";
import { api, type Option } from "@/lib/api";
import { shopComparison } from "@/lib/landingData";
import { DEFAULT_BY_PROVIDER, DEFAULT_REGIONS } from "@/lib/defaultLandingData";

/**
 * Fetches one workload priced on every cloud and hands it to the switcher.
 * Uses the Balanced shape, which is the option most people actually ship.
 * Falls back to high-fidelity pre-computed data if the engine is sleeping or slow,
 * guaranteeing instant, zero-latency rendering.
 */
export async function CloudArchitectures() {
  let byProvider: Record<string, Option> = { ...DEFAULT_BY_PROVIDER };
  let regions: string[] = [...DEFAULT_REGIONS];

  try {
    const timeout = new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error("fetch timeout")), 1500),
    );

    const fetchData = async () => {
      const regionMap = await api.regions().catch(() => ({}));
      const fetchedRegions = Object.keys(regionMap ?? {});
      const compare = await shopComparison();
      const liveByProvider: Record<string, Option> = {};
      for (const [provider, options] of Object.entries(compare.clouds)) {
        const balanced = options.find((o) => o.label === "Most reliable") ?? options[0];
        if (balanced) liveByProvider[provider] = balanced;
      }
      return { liveByProvider, fetchedRegions };
    };

    const res = await Promise.race([fetchData(), timeout]);
    if (Object.keys(res.liveByProvider).length >= 2) {
      byProvider = res.liveByProvider;
      if (res.fetchedRegions.length) regions = res.fetchedRegions;
    }
  } catch {
    // If backend is waking or slow, default data is already in place
  }

  return (
    <MultiCloudArchitecture
      byProvider={byProvider}
      initialRegion="india"
      regions={regions}
    />
  );
}

