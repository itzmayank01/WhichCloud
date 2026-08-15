import { MultiCloudArchitecture } from "@/components/MultiCloudArchitecture";
import { api, type Option } from "@/lib/api";

/**
 * Fetches one workload priced on every cloud and hands it to the switcher.
 * Uses the Balanced shape, which is the option most people actually ship.
 */
export async function CloudArchitectures() {
  let byProvider: Record<string, Option> = {};

  try {
    const compare = await api.compare({
      goal: "an online shop",
      workload_type: "web",
      traffic_pattern: "spiky",
      traffic_scale: "medium",
      storage_gb: 200,
      egress_gb: 500,
    });
    for (const [provider, options] of Object.entries(compare.clouds)) {
      const balanced = options.find((o) => o.label === "Balanced") ?? options[0];
      if (balanced) byProvider[provider] = balanced;
    }
  } catch {
    return (
      <div className="rounded-xl border border-dashed border-line-strong bg-canvas p-10 text-center">
        <p className="font-mono text-[14px] leading-relaxed text-ink-3">
          Architectures render from live pricing — start the API to see all three clouds.
        </p>
      </div>
    );
  }

  if (!Object.keys(byProvider).length) return null;
  return <MultiCloudArchitecture byProvider={byProvider} />;
}
