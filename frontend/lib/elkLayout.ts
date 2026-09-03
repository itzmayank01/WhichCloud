/**
 * Lay the data plane out with ELK (layered, orthogonal), then place the
 * control and account planes around it. ELK is the one open layout engine
 * that routes edges correctly across NESTED containers, which a VPC → AZ →
 * subnet hierarchy needs and dagre cannot do.
 *
 * Only the data plane goes through ELK — it is the only plane with edges, so
 * it is the only plane layering applies to. Control nodes are pinned beside
 * the single node each serves (a dotted attachment, not a layered hop), and
 * the account plane is a band below the canvas with no geometry to solve.
 * Feeding those planes to ELK would bend the request path around boxes that
 * are not in it, which is the crossing-and-collision mess we are replacing.
 *
 * Pure and isomorphic: the same import runs in the browser renderer and in
 * the Node quality harness, so the harness measures the exact geometry the
 * user sees.
 */

import ELK from "elkjs/lib/elk.bundled.js";
import type { GraphModel, PlanedNode, ContainerId } from "@/lib/graphModel";

const elk = new ELK();

export const NODE_W = 200;
export const NODE_H = 92;
const CONTROL_W = 150;
const CONTROL_H = 58;
const ACCOUNT_H = 64;

export type LaidNode = {
  id: string;
  kind: string;
  plane: "data" | "control" | "account";
  label: string;
  detail: string;
  sku: string;
  monthly_usd: number;
  share: number;
  priced: boolean;
  seq: number | null;
  /** absolute canvas coordinates (top-left) */
  x: number;
  y: number;
  w: number;
  h: number;
  parentId?: string;
  attachedTo?: string;
};

export type LaidContainer = {
  id: string;
  kind: ContainerId;
  label: string;
  x: number;
  y: number;
  w: number;
  h: number;
  parentId?: string;
};

export type LaidEdge = {
  id: string;
  source: string;
  target: string;
  label: string;
  onPath: boolean;
  seq: number | null;
  /** a dotted control-plane attachment (KMS → database), not a flow edge */
  attach: boolean;
  /** absolute polyline points from ELK's orthogonal routing */
  points: Array<{ x: number; y: number }>;
};

export type Layout = {
  nodes: LaidNode[];
  containers: LaidContainer[];
  edges: LaidEdge[];
  attachments: Array<{ source: string; target: string }>;
  width: number;
  height: number;
};

const CONTAINER_LABEL: Record<string, string> = {
  cloud: "AWS Cloud",
  edge: "Edge / global services",
  region: "Region",
  regional: "Regional services (outside the VPC)",
  vpc: "VPC",
  az: "Availability Zone",
  "az-a": "Availability Zone ap-south-1a",
  "az-b": "Availability Zone ap-south-1b",
  "subnet-public": "Public subnet",
  "subnet-app": "App subnet",
  "subnet-data": "Data subnet",
};

type ElkChild = {
  id: string;
  width?: number;
  height?: number;
  children?: ElkChild[];
  layoutOptions?: Record<string, string>;
  labels?: Array<{ text: string }>;
};

/** Which container each data node lives in, resolved to a concrete parent id.
 *  Non-VPC nodes hang directly under the region; VPC-resident ones nest into
 *  the public or private subnet inside the single AZ. */
function parentOf(node: PlanedNode, hasVpc: boolean): string {
  if (node.container === "outside") return "outside";
  if (node.container === "edge") return "edge";
  // Managed services outside the VPC get their own strip rather than floating
  // loose in the region -- see REGIONAL_SERVICE in graphModel.
  if (node.container === "regional") return "regional";
  if (!hasVpc || node.container === "region") return "region";
  const z = node.zone === "b" ? "-b" : "-a";
  if (node.container === "subnet-public") return `subnet-public${z}`;
  if (node.container === "subnet-app") return `subnet-app${z}`;
  return `subnet-data${z}`;
}

export async function layout(model: GraphModel): Promise<Layout> {
  const hasVpc = model.hasVpc;

  // Control nodes join the layout INSIDE the same container as the node they
  // serve, wired by their attachment edge, so ELK positions and routes them
  // with the same no-overlap guarantee as the data plane. (Pinning them by
  // hand afterwards dropped boxes on top of their neighbours — the overlaps
  // and edge-through-node hits the quality harness caught.) Only the account
  // plane stays outside ELK, as a band with no geometry to solve.
  const controlParent = new Map<string, string>(); // control id → its target's container
  const dataById = new Map(model.data.map((n) => [n.id, n]));
  for (const c of model.control) {
    const tgt = c.attachedTo ? dataById.get(c.attachedTo) : undefined;
    controlParent.set(c.id, tgt ? parentOf(tgt, hasVpc) : "region");
  }

  // Group data + control nodes by their concrete parent container.
  const byParent = new Map<string, PlanedNode[]>();
  const push = (p: string, n: PlanedNode) =>
    (byParent.get(p) ?? byParent.set(p, []).get(p)!).push(n);
  for (const n of model.data) push(parentOf(n, hasVpc), n);
  for (const c of model.control) push(controlParent.get(c.id)!, c);

  const serviceChild = (n: PlanedNode): ElkChild => ({
    id: n.id,
    width: n.plane === "control" ? CONTROL_W : NODE_W,
    height: n.plane === "control" ? CONTROL_H : NODE_H,
  });

  // Build the container hierarchy, omitting any container that would be empty
  // (an AZ or subnet with nothing in it must not be drawn).
  const regionChildren: ElkChild[] = (byParent.get("region") ?? []).map(serviceChild);

  const outsideNodes = byParent.get("outside") ?? [];
  const edgeNodes = byParent.get("edge") ?? [];
  const regionalNodes = byParent.get("regional") ?? [];
  if (regionalNodes.length) {
    regionChildren.push({
      id: "regional",
      layoutOptions: {
        "elk.padding": "[top=34,left=18,bottom=18,right=18]",
        // Lay this strip out as a ROW. Left to itself ELK stacks it along the
        // parent's DOWN axis, which turned six managed services into a tall
        // column beside a wide VPC and doubled the canvas height.
        "elk.direction": "RIGHT",
        "elk.spacing.nodeNode": "34",
      },
      labels: [{ text: CONTAINER_LABEL["regional"] }],
      children: regionalNodes.map(serviceChild),
    });
  }

  if (hasVpc) {
    // One AZ block per zone, each with the SAME internal order (private app +
    // data, then public) so the two render as mirrors. Zone b only exists when
    // the bill paid for a standby -- see the Multi-AZ detection in graphModel.
    const azBlock = (z: "a" | "b"): ElkChild | null => {
      // Rows in tier order: public at the top, then app, then data -- the way
      // both AWS reference diagrams stack them, so the rows read as tiers and
      // line up across the two zones.
      const rows: Array<[string, string]> = [
        [`subnet-public-${z}`, "subnet-public"],
        [`subnet-app-${z}`, "subnet-app"],
        [`subnet-data-${z}`, "subnet-data"],
      ];
      const subnets: ElkChild[] = [];
      for (const [id, labelKey] of rows) {
        const members = byParent.get(id) ?? [];
        if (!members.length) continue;
        subnets.push({
          id,
          layoutOptions: {
            "elk.padding": "[top=34,left=16,bottom=16,right=16]",
            // Members of a tier sit side by side, not stacked.
            "elk.direction": "RIGHT",
            "elk.spacing.nodeNode": "28",
          },
          labels: [{ text: CONTAINER_LABEL[labelKey] }],
          children: members.map(serviceChild),
        });
      }
      if (!subnets.length) return null;
      return {
        id: `az-${z}`,
        layoutOptions: {
          "elk.padding": "[top=34,left=16,bottom=16,right=16]",
          // Tiers run ACROSS inside a zone (public | app | data), and the two
          // zones stack. Side-by-side zones each three subnets wide is what
          // made the graph 3.4:1 -- half the canvas height went unused. This
          // orientation is also what the AWS reference grid uses: subnet rows
          // reading left to right, zones stacked so they compare directly.
          "elk.direction": "RIGHT",
        },
        labels: [{ text: CONTAINER_LABEL[`az-${z}`] }],
        children: subnets,
      };
    };
    const azs = [azBlock("a"), azBlock("b")].filter(Boolean) as ElkChild[];
    if (azs.length) {
      regionChildren.push({
        id: "vpc",
        layoutOptions: {
          "elk.padding": "[top=34,left=18,bottom=18,right=18]",
          "elk.direction": "DOWN",
        },
        labels: [{ text: CONTAINER_LABEL["vpc"] }],
        children: azs,
      });
    }
  }

  // SAFETY NET. Every data node must land in exactly one ELK container. A node
  // whose parent group is never built -- a zone that has no app tier, a
  // container added to the model but not to the tree -- is silently left out of
  // the layout, yet its EDGES are still emitted. ELK routes those from the
  // graph origin, which is what drew blue arrows starting and ending in open
  // canvas above the edge cluster with no box at either end. Anything not
  // already placed is put in the region rather than dropped.
  const placedIds = new Set<string>();
  const collectPlaced = (children: ElkChild[]) => {
    for (const c of children) {
      placedIds.add(c.id);
      if (c.children) collectPlaced(c.children);
    }
  };
  collectPlaced(regionChildren);
  collectPlaced(edgeNodes.map(serviceChild));
  collectPlaced(outsideNodes.map(serviceChild));
  for (const n of [...model.data, ...model.control]) {
    if (!placedIds.has(n.id)) regionChildren.push(serviceChild(n));
  }

  const graph = {
    id: "cloud",
    layoutOptions: {
      "elk.algorithm": "layered",
      // Shaped like a viewport, not a ribbon. Without this ELK happily
      // returns a 6:1 band, and fitting that to a 16:9 canvas shrinks it to
      // an illegible strip with dead margins above and below -- which is the
      // whole "empty canvas" complaint.
      "elk.aspectRatio": "1.6",
      // A request path is a CHAIN, and a chain laid out in one direction is a
      // ribbon however much spacing you give it -- 4.7:1 here, so fitting to
      // width left the diagram a third of the canvas tall. Wrapping lets the
      // layered algorithm break that chain across rows and use the height,
      // which is the only lever that changes the SHAPE rather than the scale.
      "elk.layered.wrapping.strategy": "MULTI_EDGE",
      "elk.layered.wrapping.additionalEdgeSpacing": "40",
      "elk.direction": "RIGHT",
      "elk.edgeRouting": "ORTHOGONAL",
      "elk.hierarchyHandling": "INCLUDE_CHILDREN",
      // BRANDES_KOEPF centres each rank instead of top-aligning it. With
      // NETWORK_SIMPLEX the edge cluster sank to the bottom of its column and
      // left a tall empty band above it, with long edges climbing back up into
      // the VPC.
      "elk.layered.nodePlacement.strategy": "BRANDES_KOEPF",
      "elk.layered.nodePlacement.bk.fixedAlignment": "BALANCED",
      "elk.alignment": "CENTER",
      "elk.layered.spacing.nodeNodeBetweenLayers": "64",
      "elk.layered.spacing.edgeNodeBetweenLayers": "28",
      "elk.spacing.nodeNode": "40",
      "elk.spacing.edgeNode": "28",
      "elk.spacing.edgeEdge": "22",
      "elk.padding": "[top=40,left=24,bottom=24,right=24]",
      // Keep skip-layer edges (e.g. CDN → S3 past the app tier) clear of the
      // boxes they route past, and cut crossings — the two things the layout
      // quality harness measures on the routed geometry.
      "elk.layered.crossingMinimization.strategy": "LAYER_SWEEP",
      "elk.layered.crossingMinimization.semiInteractive": "true",
      "elk.layered.mergeEdges": "false",
    },
    labels: [{ text: CONTAINER_LABEL["cloud"] }],
    children: [
      // The caller, at graph root and first in declaration order so the request
      // path reads left to right: users -> edge -> region.
      ...outsideNodes.map(serviceChild),
      ...(edgeNodes.length
        ? [{
            id: "edge",
            layoutOptions: {
              "elk.padding": "[top=34,left=18,bottom=18,right=18]",
              "elk.direction": "RIGHT",
              "elk.spacing.nodeNode": "34",
            },
            labels: [{ text: CONTAINER_LABEL["edge"] }],
            children: edgeNodes.map(serviceChild),
          }]
        : []),
      {
        id: "region",
        layoutOptions: { "elk.padding": "[top=34,left=18,bottom=18,right=18]" },
        labels: [{ text: CONTAINER_LABEL["region"] }],
        children: regionChildren,
      },
    ],
    edges: [
      // TIER ORDER. ELK ranks a container's children by the edges between them,
      // and the priced estimate has no edge that says "public sits above app".
      // Left to itself it ordered the rows differently in each zone -- 1b came
      // out data/public/app while 1a came out public/data/app, so the two zones
      // did not read as mirrors. One invisible chain per zone pins the order to
      // public -> app -> data, the way both reference diagrams stack them.
      ...(["a", "b"] as const).flatMap((z) => {
        const chain = [`subnet-public-${z}`, `subnet-app-${z}`, `subnet-data-${z}`]
          .filter((id) => (byParent.get(id) ?? []).length);
        return chain.slice(1).map((target, i) => ({
          id: `tier-${z}-${i}`,
          sources: [chain[i]],
          targets: [target],
        }));
      }),
      ...model.dataEdges.map((e, i) => ({
        id: `e${i}`,
        sources: [e.source],
        targets: [e.target],
      })),
      // attachment edges: target(data) → control, so ELK places the control
      // node as a leaf beside its resource and routes the dotted line.
      ...model.attachments.map((a, i) => ({
        id: `a${i}`,
        sources: [a.target],
        targets: [a.source],
      })),
    ],
  };

  // Measure both directions rather than guessing. RIGHT suits wide, shallow
  // graphs; DOWN suits deep ones. Whichever comes back closer to the target
  // ratio is the one the reader gets.
  const TARGET_RATIO = 1.6;
  const attempt = async (direction: string) => {
    const g = JSON.parse(JSON.stringify(graph));
    g.layoutOptions["elk.direction"] = direction;
    const out: any = await new ELK().layout(g);
    const ratio = (out.width ?? 1) / (out.height ?? 1);
    // Score by how much of the viewport the result will actually COVER once
    // fitted, not by |ratio - target|. That difference is asymmetric and picks
    // the wrong winner: a graph 2.5x too tall scores better than one 2x too
    // wide, yet on a 16:9 canvas the tall one fits to a narrow column and
    // wastes most of the width -- which is exactly what it did, filling about
    // a fifth of the canvas. Coverage is the honest measure because fitting
    // scales by whichever axis binds first.
    const coverage =
      Math.min(ratio, TARGET_RATIO) / Math.max(ratio, TARGET_RATIO);
    return { out, ratio, coverage };
  };
  const [right, down] = await Promise.all([attempt("RIGHT"), attempt("DOWN")]);
  const res: any = (right.coverage >= down.coverage ? right : down).out;

  // ── flatten ELK's relative coordinates to absolute canvas coordinates ──
  const containers: LaidContainer[] = [];
  const nodes: LaidNode[] = [];
  const nodeById = new Map<string, PlanedNode>(
    [...model.data, ...model.control].map((n) => [n.id, n])
  );
  const abs = new Map<string, { x: number; y: number }>();
  const box = new Map<string, { x: number; y: number; w: number; h: number }>();

  const walk = (elkNode: any, ox: number, oy: number, parentId?: string) => {
    const x = ox + (elkNode.x ?? 0);
    const y = oy + (elkNode.y ?? 0);
    abs.set(elkNode.id, { x, y });
    box.set(elkNode.id, { x, y, w: elkNode.width ?? 0, h: elkNode.height ?? 0 });
    box.set(elkNode.id, {
      x, y, w: elkNode.width ?? 0, h: elkNode.height ?? 0,
    });
    const isContainer = Array.isArray(elkNode.children) && elkNode.children.length > 0
      && !nodeById.has(elkNode.id);
    // Subnet ids carry a zone suffix (subnet-app-a, subnet-data-b) but the
    // label table is keyed unsuffixed -- looked up raw, every subnet box failed
    // the lookup and was silently dropped from the render, which is why the
    // tier rows never appeared even though ELK had laid them out.
    const labelKey =
      elkNode.id in CONTAINER_LABEL
        ? elkNode.id
        : elkNode.id.replace(/-[ab]$/, "");
    if (isContainer && labelKey in CONTAINER_LABEL) {
      containers.push({
        id: elkNode.id,
        kind: elkNode.id as ContainerId,
        label: CONTAINER_LABEL[labelKey],
        x, y, w: elkNode.width ?? 0, h: elkNode.height ?? 0,
        parentId,
      });
    }
    const topo = nodeById.get(elkNode.id);
    if (topo) {
      nodes.push({
        id: topo.id, kind: topo.kind, plane: topo.plane as "data" | "control",
        label: topo.label, detail: topo.detail, sku: topo.sku,
        monthly_usd: topo.monthly_usd, share: topo.share, priced: topo.priced,
        seq: topo.seq,
        x, y, w: elkNode.width ?? NODE_W, h: elkNode.height ?? NODE_H,
        parentId, attachedTo: topo.attachedTo,
      });
    }
    for (const c of elkNode.children ?? []) {
      walk(c, x, y, elkNode.id);
    }
  };
  walk(res, 0, 0, undefined);

  // ELK edge sections are relative to the edge's container; INCLUDE_CHILDREN
  // puts cross-container edges on the root, so their sections are already
  // absolute. Resolve each edge's container offset to be safe.
  const edges: LaidEdge[] = [];
  const collectEdges = (elkNode: any, ox: number, oy: number) => {
    const base = abs.get(elkNode.id) ?? { x: ox, y: oy };
    for (const e of elkNode.edges ?? []) {
      // The tier-ordering chain is a LAYOUT CONSTRAINT, not a relationship. It
      // connects subnet CONTAINERS to pin public above app above data, and it
      // must never reach the renderer -- collected like a real edge it drew as
      // an arrow springing from one container boundary to another, which reads
      // as an arrowhead floating in open canvas. It also counted as an
      // attachment (no match in dataEdges), so it slipped past the filter that
      // drops long branch edges.
      if (typeof e.id === "string" && e.id.startsWith("tier-")) continue;
      const src = e.sources?.[0];
      const tgt = e.targets?.[0];
      const model_e = model.dataEdges.find(
        (d) => d.source === src && d.target === tgt
      );
      const isAttach = !model_e; // attachment edges are the ones not in dataEdges
      const pts: Array<{ x: number; y: number }> = [];
      for (const sec of e.sections ?? []) {
        pts.push({ x: base.x + sec.startPoint.x, y: base.y + sec.startPoint.y });
        for (const bp of sec.bendPoints ?? []) {
          pts.push({ x: base.x + bp.x, y: base.y + bp.y });
        }
        pts.push({ x: base.x + sec.endPoint.x, y: base.y + sec.endPoint.y });
      }
      // CORRECT THE ORIGIN, DO NOT DISCARD THE ROUTE.
      // ELK gives an edge's sections in the coordinate space of whichever node
      // holds the edge. Under INCLUDE_CHILDREN a cross-container edge can be
      // stored against a different ancestor than the offset we add for it, and
      // the whole polyline lands somewhere it does not belong -- arrows in open
      // canvas, and (once those were filtered out) missing arrows between the
      // numbered spine steps.
      //
      // The route SHAPE is right; only its origin is wrong. So measure how far
      // both ends have drifted from their own boxes and translate the polyline
      // back by that amount. Averaging the two ends makes the correction robust
      // when one end is legitimately on a box border. Snapping endpoints
      // individually was tried first and was worse -- it bent the orthogonal
      // routes into long diagonals.
      const sBox = src ? box.get(src) : undefined;
      const tBox = tgt ? box.get(tgt) : undefined;
      if (pts.length >= 2 && sBox && tBox) {
        const near = (pt: { x: number; y: number }, b: typeof sBox) => {
          const dx = Math.max(b!.x - pt.x, 0, pt.x - (b!.x + b!.w));
          const dy = Math.max(b!.y - pt.y, 0, pt.y - (b!.y + b!.h));
          return Math.hypot(dx, dy) <= 64;
        };
        const first = pts[0];
        const last = pts[pts.length - 1];
        if (!near(first, sBox) && !near(last, tBox)) {
          const dx =
            (sBox.x + sBox.w / 2 - first.x + (tBox.x + tBox.w / 2 - last.x)) / 2;
          const dy =
            (sBox.y + sBox.h / 2 - first.y + (tBox.y + tBox.h / 2 - last.y)) / 2;
          for (const pt of pts) {
            pt.x += dx;
            pt.y += dy;
          }
        }
      }
      edges.push({
        id: e.id,
        source: src,
        target: tgt,
        label: model_e?.label ?? "",
        onPath: model_e?.onPath ?? false,
        seq: model_e?.seq ?? null,
        attach: isAttach,
        points: pts,
      });
    }
    for (const c of elkNode.children ?? []) collectEdges(c, base.x, base.y);
  };
  collectEdges(res, 0, 0);

  let width = res.width ?? 0;
  let height = res.height ?? 0;

  // Control nodes were laid out inside ELK above, beside the resource each
  // serves — no hand-placement, no overlaps.

  // ── account plane: a band below everything, evenly spaced, no edges ──
  const bandY = height + 40;
  const bandPad = 24;
  const gap = 16;
  let ax = bandPad;
  for (const a of model.account) {
    nodes.push({
      id: a.id, kind: a.kind, plane: "account", label: a.label, detail: a.detail,
      sku: a.sku, monthly_usd: a.monthly_usd, share: a.share, priced: a.priced,
      seq: null, x: ax, y: bandY, w: CONTROL_W, h: ACCOUNT_H,
    });
    ax += CONTROL_W + gap;
  }
  if (model.account.length) {
    width = Math.max(width, ax);
    height = bandY + ACCOUNT_H + bandPad;
  }

  return {
    nodes,
    containers,
    edges,
    attachments: model.attachments,
    width: Math.ceil(width),
    height: Math.ceil(height),
  };
}
