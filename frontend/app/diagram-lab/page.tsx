"use client";

/**
 * Diagram lab — renders each divergence fixture's three tiers straight from
 * the dumped topology, bypassing extraction. It is how the renderer is proven
 * per-workload and per-tier: pick a fixture, pick a tier, see the graph the
 * engine actually produced. The layout-quality harness measures the same JSON.
 */

import { useMemo, useState } from "react";
import { ArchitectureGraph } from "@/components/architecture/ArchitectureGraph";
import fixturesData from "@/lib/fixtureTopologies.json";
import type { Node as TopoNode, Edge as TopoEdge } from "@/lib/api";

type Tier = {
  label: string;
  monthly_usd: number;
  fingerprint: string[];
  nodes: TopoNode[];
  edges: TopoEdge[];
};
type Fixture = {
  goal: string;
  workload_type: string;
  tier_spread: number[];
  tiers: Tier[];
};
const fixtures = (fixturesData as { fixtures: Record<string, Fixture> }).fixtures;
const NAMES = Object.keys(fixtures);

export default function DiagramLab() {
  const [name, setName] = useState(NAMES[0]);
  const [tierIdx, setTierIdx] = useState(1); // tier-2 (balanced) by default
  const [playing, setPlaying] = useState(true);

  const fixture = fixtures[name];
  const tier = fixture.tiers[tierIdx];
  const key = `${name}-${tier.label}-${playing}`;

  const spread = useMemo(() => fixture.tier_spread.join(" · "), [fixture]);

  return (
    <div className="flex h-screen flex-col bg-sunk text-ink">
      <header className="flex flex-wrap items-center gap-3 border-b border-line bg-surface px-4 py-2.5">
        <span className="text-[13px] font-semibold">Diagram lab</span>
        <select
          data-testid="fixture"
          value={name}
          onChange={(e) => {
            setName(e.target.value);
            setTierIdx(1);
          }}
          className="rounded-lg border border-line-strong bg-surface px-2.5 py-1 text-[12.5px]"
        >
          {NAMES.map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
        <div className="flex overflow-hidden rounded-lg border border-line-strong">
          {fixture.tiers.map((t, i) => (
            <button
              key={t.label}
              data-testid={`tier-${i}`}
              onClick={() => setTierIdx(i)}
              className={`px-3 py-1 text-[12px] ${
                i === tierIdx ? "bg-accent text-white" : "bg-surface text-ink-2 hover:bg-sunk"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <button
          onClick={() => setPlaying((p) => !p)}
          className="rounded-lg border border-line-strong bg-surface px-3 py-1 text-[12px] text-ink-2 hover:bg-sunk"
        >
          {playing ? "Pause" : "Replay"}
        </button>
        <span className="ml-auto font-mono text-[11.5px] text-ink-3">
          {fixture.goal} · {tier.nodes.length} services · ${tier.monthly_usd.toFixed(0)}/mo · spread [{spread}]
        </span>
      </header>
      <main className="min-h-0 flex-1" data-testid="canvas">
        <ArchitectureGraph key={key} nodes={tier.nodes} edges={tier.edges} playing={playing} />
      </main>
    </div>
  );
}
