/**
 * Layout-quality harness — diagram quality measured like everything else in
 * this project, computed on the ELK geometry the browser actually renders.
 *
 *   pnpm/npm run diagram:check      (npx tsx harness/layoutQuality.ts)
 *
 * For every fixture's three tiers it asserts, on the laid-out graph:
 *   - zero node–node overlaps
 *   - zero edge–node intersections (an edge crossing through a node box)
 *   - edge crossings below a threshold proportional to the edge count
 *   - zero label overlaps
 *   - zero orphan data-plane nodes (a data node with no edge = mis-planed)
 *   - the data plane is one connected component (nothing stranded)
 *   - aspect ratio within a sane band
 *   - the three tiers differ (identical tiers = the tier-spread bug, surfaced)
 *
 * It reads the same dumped topology the diagram-lab renders, so the numbers
 * describe the exact picture, and exits non-zero on any hard failure.
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { buildGraphModel } from "../lib/graphModel.ts";
import { layout, routeStats, type LaidNode, type LaidEdge } from "../lib/elkLayout.ts";

const here = dirname(fileURLToPath(import.meta.url));
const data = JSON.parse(
  readFileSync(join(here, "..", "lib", "fixtureTopologies.json"), "utf8")
);

type Rect = { x: number; y: number; w: number; h: number };
const overlap = (a: Rect, b: Rect, pad = -1) =>
  a.x < b.x + b.w - pad &&
  a.x + a.w - pad > b.x &&
  a.y < b.y + b.h - pad &&
  a.y + a.h - pad > b.y;

type P = { x: number; y: number };
function segIntersect(a: P, b: P, c: P, d: P): boolean {
  const o = (p: P, q: P, r: P) =>
    Math.sign((q.y - p.y) * (r.x - q.x) - (q.x - p.x) * (r.y - q.y));
  const o1 = o(a, b, c), o2 = o(a, b, d), o3 = o(c, d, a), o4 = o(c, d, b);
  if (o1 !== o2 && o3 !== o4) return true;
  return false;
}
function segRect(a: P, b: P, r: Rect): boolean {
  // inside test
  const inside = (p: P) => p.x >= r.x && p.x <= r.x + r.w && p.y >= r.y && p.y <= r.y + r.h;
  if (inside(a) || inside(b)) return true;
  const c1 = { x: r.x, y: r.y }, c2 = { x: r.x + r.w, y: r.y };
  const c3 = { x: r.x + r.w, y: r.y + r.h }, c4 = { x: r.x, y: r.y + r.h };
  return (
    segIntersect(a, b, c1, c2) ||
    segIntersect(a, b, c2, c3) ||
    segIntersect(a, b, c3, c4) ||
    segIntersect(a, b, c4, c1)
  );
}
function labelRect(e: LaidEdge): Rect | null {
  if (!e.label) return null;
  let best = 0;
  let anchor: P = e.points[Math.floor(e.points.length / 2)] ?? { x: 0, y: 0 };
  for (let i = 0; i < e.points.length - 1; i++) {
    const len = Math.hypot(e.points[i].x - e.points[i + 1].x, e.points[i].y - e.points[i + 1].y);
    if (len > best) {
      best = len;
      anchor = { x: (e.points[i].x + e.points[i + 1].x) / 2, y: (e.points[i].y + e.points[i + 1].y) / 2 };
    }
  }
  const w = e.label.length * 6 + 8;
  const h = 14;
  return { x: anchor.x - w / 2, y: anchor.y - h / 2, w, h };
}

type Metrics = {
  tier: string;
  nodeOverlaps: number;
  edgeNodeHits: number;
  edgeCrossings: number;
  crossingBudget: number;
  labelOverlaps: number;
  orphans: number;
  components: number;
  reachableFromUsers: string; // "n/a" for pipelines with no user entry
  aspect: number;
  services: number;
  /** Total ink: sum of every routed edge's length. Lower is better -- it is
   *  the single number that says "are these routes short and local". */
  edgeLength: number;
  /** The longest single edge. A route far above the median is one travelling
   *  across the canvas, which is what reads as spaghetti. */
  longestEdge: number;
  /** ELK's own routing that survived, vs routes we replaced. 0 kept means the
   *  layout engine's crossing minimisation is being discarded wholesale. */
  elkKept: number;
  elkReplaced: number;
  /** Directed cycles in the data plane. ELK's layered algorithm cannot lay a
   *  cycle out; it reverses an edge to break it, and the reversed edge then
   *  travels backwards across the diagram. */
  cycles: number;
  /** Highest outgoing-edge count on any single node. A hub with six edges
   *  leaving one side is the main source of overlap. */
  maxFanOut: number;
  /** Pairs of edges sharing more than 20px of the same line. Two arrows drawn
   *  on top of each other read as one. */
  collinear: number;
  /** Widest rank gap any edge spans, ranks being distinct node columns. An
   *  edge crossing many ranks is one travelling the length of the canvas. */
  maxRankSpan: number;
  /** Nodes with no parent container. */
  orphanNodes: number;
};

async function measureTier(nodes: any[], edges: any[], label: string): Promise<Metrics> {
  const model = buildGraphModel(nodes, edges);
  const laid = await layout(model);

  const boxes = laid.nodes; // service + control + account rects
  // node–node overlaps (ignore container boxes, which legitimately contain nodes)
  let nodeOverlaps = 0;
  for (let i = 0; i < boxes.length; i++)
    for (let j = i + 1; j < boxes.length; j++)
      if (overlap(boxes[i], boxes[j], 2)) nodeOverlaps++;

  // edge–node intersections: a routed edge passing through a box that is not
  // its own endpoint
  let edgeNodeHits = 0;
  for (const e of laid.edges) {
    for (const n of boxes) {
      if (n.id === e.source || n.id === e.target) continue;
      if (n.plane !== "data") continue; // account/control sit off the flow
      for (let k = 0; k < e.points.length - 1; k++) {
        if (segRect(e.points[k], e.points[k + 1], shrink(n, 4))) {
          edgeNodeHits++;
          break;
        }
      }
    }
  }

  // edge crossings between non-adjacent segments
  let edgeCrossings = 0;
  const segs: Array<{ a: P; b: P; id: string }> = [];
  for (const e of laid.edges)
    for (let k = 0; k < e.points.length - 1; k++)
      segs.push({ a: e.points[k], b: e.points[k + 1], id: e.id });
  for (let i = 0; i < segs.length; i++)
    for (let j = i + 1; j < segs.length; j++) {
      if (segs[i].id === segs[j].id) continue;
      if (segIntersect(segs[i].a, segs[i].b, segs[j].a, segs[j].b)) edgeCrossings++;
    }

  // label overlaps (label vs label)
  const lrects = laid.edges.map(labelRect).filter(Boolean) as Rect[];
  let labelOverlaps = 0;
  for (let i = 0; i < lrects.length; i++)
    for (let j = i + 1; j < lrects.length; j++)
      if (overlap(lrects[i], lrects[j], 0)) labelOverlaps++;

  // orphans + connectivity over the data plane (undirected)
  const dataIds = new Set(laid.nodes.filter((n) => n.plane === "data").map((n) => n.id));
  const adj = new Map<string, Set<string>>();
  for (const id of dataIds) adj.set(id, new Set());
  for (const e of laid.edges) {
    if (dataIds.has(e.source) && dataIds.has(e.target)) {
      adj.get(e.source)!.add(e.target);
      adj.get(e.target)!.add(e.source);
    }
  }
  const orphans = [...dataIds].filter((id) => adj.get(id)!.size === 0).length;
  const components = countComponents(adj);

  // reachability from users (directed), only meaningful when users has out-edges
  const directed = new Map<string, Set<string>>();
  for (const id of dataIds) directed.set(id, new Set());
  for (const e of laid.edges)
    if (dataIds.has(e.source) && dataIds.has(e.target)) directed.get(e.source)!.add(e.target);
  let reachableFromUsers = "n/a";
  if (dataIds.has("users") && directed.get("users")!.size > 0) {
    const seen = bfs("users", directed);
    const missed = [...dataIds].filter((id) => !seen.has(id) && id !== "users");
    reachableFromUsers = missed.length === 0 ? "all" : `missed ${missed.join(",")}`;
  }

  const aspect = laid.height ? laid.width / laid.height : 0;
  // ── directed cycles over the data plane ──
  const adjOut = new Map<string, string[]>();
  for (const e of laid.edges)
    if (!e.attach) adjOut.set(e.source, [...(adjOut.get(e.source) ?? []), e.target]);
  let cycles = 0;
  {
    const WHITE = 0, GREY = 1, BLACK = 2;
    const colour = new Map<string, number>();
    const visit = (id: string) => {
      colour.set(id, GREY);
      for (const nxt of adjOut.get(id) ?? []) {
        const c = colour.get(nxt) ?? WHITE;
        if (c === GREY) cycles++;          // back edge = one cycle
        else if (c === WHITE) visit(nxt);
      }
      colour.set(id, BLACK);
    };
    for (const n of laid.nodes) if ((colour.get(n.id) ?? WHITE) === WHITE) visit(n.id);
  }
  const maxFanOut = Math.max(0, ...[...adjOut.values()].map((v) => v.length));
  // Geometric, not parentId: ELK's root has no id, so its direct children
  // report no parent while sitting plainly inside the drawn cloud box.
  const orphanNodes = laid.nodes.filter(
    (n) =>
      !laid.containers.some(
        (c) =>
          n.x >= c.x - 1 && n.y >= c.y - 1 &&
          n.x + n.w <= c.x + c.w + 1 && n.y + n.h <= c.y + c.h + 1
      )
  ).length;

  // ── collinear overlap: two edges sharing >20px of the same axis line ──
  type Seg = { a: P; b: P };
  const colSegs: Seg[] = [];
  for (const e of laid.edges)
    for (let i = 1; i < e.points.length; i++)
      colSegs.push({ a: e.points[i - 1] as P, b: e.points[i] as P });
  let collinear = 0;
  for (let i = 0; i < colSegs.length; i++)
    for (let j = i + 1; j < colSegs.length; j++) {
      const s1 = colSegs[i], s2 = colSegs[j];
      const h1 = Math.abs(s1.a.y - s1.b.y) < 1, h2 = Math.abs(s2.a.y - s2.b.y) < 1;
      const v1 = Math.abs(s1.a.x - s1.b.x) < 1, v2 = Math.abs(s2.a.x - s2.b.x) < 1;
      if (h1 && h2 && Math.abs(s1.a.y - s2.a.y) < 2) {
        const lo = Math.max(Math.min(s1.a.x, s1.b.x), Math.min(s2.a.x, s2.b.x));
        const hi = Math.min(Math.max(s1.a.x, s1.b.x), Math.max(s2.a.x, s2.b.x));
        if (hi - lo > 20) collinear++;
      } else if (v1 && v2 && Math.abs(s1.a.x - s2.a.x) < 2) {
        const lo = Math.max(Math.min(s1.a.y, s1.b.y), Math.min(s2.a.y, s2.b.y));
        const hi = Math.min(Math.max(s1.a.y, s1.b.y), Math.max(s2.a.y, s2.b.y));
        if (hi - lo > 20) collinear++;
      }
    }

  // ── rank span: distinct node columns an edge crosses ──
  const cols = [...new Set(laid.nodes.map((n) => Math.round(n.x / 40)))].sort((a, b) => a - b);
  const rankOf = (x: number) => {
    const k = Math.round(x / 40);
    let best = 0;
    for (let i = 0; i < cols.length; i++) if (Math.abs(cols[i] - k) < Math.abs(cols[best] - k)) best = i;
    return best;
  };
  const byId = new Map(laid.nodes.map((n) => [n.id, n]));
  const maxRankSpan = Math.max(
    0,
    ...laid.edges.map((e) => {
      const a = byId.get(e.source), b = byId.get(e.target);
      return a && b ? Math.abs(rankOf(a.x) - rankOf(b.x)) : 0;
    })
  );

  const lengthOf = (pts: P[]) =>
    pts.reduce((sum, p, i) => (i === 0 ? 0 : sum + Math.hypot(p.x - pts[i - 1].x, p.y - pts[i - 1].y)), 0);
  const lengths = laid.edges.map((e) => lengthOf(e.points as P[]));
  const edgeLength = Math.round(lengths.reduce((a, b) => a + b, 0));
  const longestEdge = Math.round(Math.max(0, ...lengths));
  const edgeCount = laid.edges.length;
  return {
    tier: label,
    nodeOverlaps,
    edgeNodeHits,
    edgeCrossings,
    crossingBudget: Math.max(2, Math.round(edgeCount * 0.5)),
    labelOverlaps,
    orphans,
    components,
    reachableFromUsers,
    aspect: Math.round(aspect * 100) / 100,
    edgeLength,
    longestEdge,
    elkKept: routeStats.elkKept,
    elkReplaced: routeStats.replaced,
    cycles,
    maxFanOut,
    collinear,
    maxRankSpan,
    orphanNodes,
    services: dataIds.size,
  };
}

const shrink = (r: Rect, by: number): Rect => ({ x: r.x + by, y: r.y + by, w: r.w - 2 * by, h: r.h - 2 * by });
function countComponents(adj: Map<string, Set<string>>): number {
  const seen = new Set<string>();
  let c = 0;
  for (const start of adj.keys()) {
    if (seen.has(start)) continue;
    c++;
    const stack = [start];
    while (stack.length) {
      const n = stack.pop()!;
      if (seen.has(n)) continue;
      seen.add(n);
      for (const m of adj.get(n) ?? []) stack.push(m);
    }
  }
  return c;
}
function bfs(start: string, adj: Map<string, Set<string>>): Set<string> {
  const seen = new Set<string>([start]);
  const q = [start];
  while (q.length) {
    const n = q.shift()!;
    for (const m of adj.get(n) ?? []) if (!seen.has(m)) { seen.add(m); q.push(m); }
  }
  return seen;
}

async function main() {
  const fixtures = data.fixtures as Record<string, any>;
  let failures = 0;
  const lines: string[] = [];
  lines.push("# Diagram layout quality\n");
  lines.push(
    "| fixture | tier | svc | nodeOvl | edge→node | crossings (budget) | labelOvl | orphans | comps | reach | aspect | edgeLen | longest | elk kept/repl | cyc | fanOut | collin | rankSpan | orphan |"
  );
  lines.push("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|");

  for (const [name, fx] of Object.entries(fixtures)) {
    const sigs: string[] = [];
    for (const tier of fx.tiers) {
      const m = await measureTier(tier.nodes, tier.edges, tier.label);
      sigs.push(tier.fingerprint.join(","));
      const hardFail =
        m.nodeOverlaps > 0 ||
        m.edgeNodeHits > 0 ||
        m.labelOverlaps > 0 ||
        m.orphans > 0 ||
        m.components > 1 ||
        m.edgeCrossings > m.crossingBudget ||
        m.aspect < 0.25 ||
        m.aspect > 5;
      if (hardFail) failures++;
      const flag = hardFail ? " ⚠️" : "";
      lines.push(
        `| ${name} | ${m.tier} | ${m.services} | ${m.nodeOverlaps} | ${m.edgeNodeHits} | ${m.edgeCrossings} (${m.crossingBudget}) | ${m.labelOverlaps} | ${m.orphans} | ${m.components} | ${m.reachableFromUsers} | ${m.aspect}${flag} | ${m.edgeLength} | ${m.longestEdge} | ${m.elkKept}/${m.elkReplaced} | ${m.cycles} | ${m.maxFanOut} | ${m.collinear} | ${m.maxRankSpan} | ${m.orphanNodes} |`
      );
    }
    // three tiers must differ
    const distinct = new Set(sigs).size;
    if (distinct < sigs.length) {
      failures++;
      lines.push(`| ${name} | **TIERS NOT DISTINCT** | ${distinct}/${sigs.length} unique | | | | | | | | ⚠️ |`);
    }
  }

  const report = lines.join("\n") + "\n";
  console.log(report);
  const outPath = join(here, "layout_quality_report.md");
  const { writeFileSync } = await import("node:fs");
  writeFileSync(outPath, report);
  console.log(`\nwrote ${outPath}`);
  console.log(failures === 0 ? "\n✅ all diagram-quality checks passed" : `\n❌ ${failures} check(s) failed`);
  process.exit(failures === 0 ? 0 : 1);
}

main().catch((e) => {
  console.error(e);
  process.exit(2);
});
