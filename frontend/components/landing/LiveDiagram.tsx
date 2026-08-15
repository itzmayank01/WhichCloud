import { ArchitectureDiagram } from "@/components/ArchitectureDiagram";
import { api, type Recommendation } from "@/lib/api";

/**
 * The architecture diagram on the landing page, built from a real
 * recommendation rather than drawn to look plausible.
 */
export async function LiveDiagram() {
  let rec: Recommendation | null = null;
  try {
    rec = await api.recommend({
      goal: "an online shop",
      workload_type: "web",
      traffic_pattern: "spiky",
      traffic_scale: "medium",
      storage_gb: 200,
      egress_gb: 500,
    });
  } catch {
    return (
      <div className="rounded-xl border border-dashed border-line-strong bg-canvas p-8 text-center">
        <p className="font-mono text-[14px] leading-relaxed text-ink-3 font-medium">
          Diagram renders from a live recommendation — start the API to see it.
        </p>
      </div>
    );
  }

  const balanced = rec.options[1] ?? rec.options[0];

  return (
    <ArchitectureDiagram
      topology={balanced.topology}
      caption={`${balanced.label} · ${balanced.provider} ${balanced.region}`}
    />
  );
}
