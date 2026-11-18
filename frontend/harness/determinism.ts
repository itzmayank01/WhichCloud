/**
 * Determinism gate — the same topology must lay out identically every time.
 *
 *   npx tsx harness/determinism.ts
 *
 * A layout that moves between runs makes every other measurement in this
 * directory meaningless: you cannot tell whether a change helped or whether
 * you drew a different sample. This runs each fixture's tiers N times and
 * hashes the node positions; anything but one distinct hash per tier is a
 * hard failure.
 */
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { buildGraphModel } from "../lib/graphModel.ts";
import { layout } from "../lib/elkLayout.ts";

const RUNS = 10;

/** The fixture file's shape, derived from what buildGraphModel accepts so it
 *  cannot drift from the real node/edge types. */
type Tier = {
  label: string;
  nodes: Parameters<typeof buildGraphModel>[0];
  edges: Parameters<typeof buildGraphModel>[1];
};
type Fixtures = Record<string, { tiers: Tier[] }>;

const data: unknown = JSON.parse(
  readFileSync(new URL("../lib/fixtureTopologies.json", import.meta.url), "utf8")
);
/* The file has been written both as {fixtures: {...}} and as a bare map. */
const fixtures = ((data as { fixtures?: Fixtures }).fixtures ?? data) as Fixtures;

const hashOf = (laid: Awaited<ReturnType<typeof layout>>) =>
  createHash("sha1")
    .update(
      [...laid.nodes]
        .sort((a, b) => a.id.localeCompare(b.id))
        .map((n) => `${n.id}:${Math.round(n.x)},${Math.round(n.y)}`)
        .join("|") +
        "#" +
        [...laid.containers]
          .sort((a, b) => a.id.localeCompare(b.id))
          .map((c) => `${c.id}:${Math.round(c.x)},${Math.round(c.y)}`)
          .join("|")
    )
    .digest("hex")
    .slice(0, 10);

async function main() {
  let failures = 0;
  let checked = 0;
  for (const [name, fx] of Object.entries(fixtures)) {
    for (const tier of fx.tiers) {
      const hashes = new Set<string>();
      for (let i = 0; i < RUNS; i++) {
        const model = buildGraphModel(tier.nodes, tier.edges);
        hashes.add(hashOf(await layout(model)));
      }
      checked++;
      if (hashes.size !== 1) {
        failures++;
        console.log(
          `UNSTABLE  ${name} / ${tier.label}: ${hashes.size} distinct layouts in ${RUNS} runs`
        );
      }
    }
  }
  console.log(
    failures === 0
      ? `determinism OK — ${checked} tiers, ${RUNS} runs each, one layout apiece`
      : `❌ ${failures} of ${checked} tiers are non-deterministic`
  );
  process.exit(failures === 0 ? 0 : 1);
}
main();
