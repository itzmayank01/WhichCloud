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
export const NODE_H = 88;
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
  "subnet-public": "Public subnet",
  "subnet-private": "Private subnet",
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
  if (node.container === "edge") return "edge";
  // Managed services outside the VPC get their own strip rather than floating
  // loose in the region -- see REGIONAL_SERVICE in graphModel.
  if (node.container === "regional") return "regional";
  if (!hasVpc || node.container === "region") return "region";
  if (node.container === "subnet-public") return "subnet-public";
  return "subnet-private";
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
    const publicNodes = byParent.get("subnet-public") ?? [];
    const privateNodes = byParent.get("subnet-private") ?? [];
    const subnets: ElkChild[] = [];
    if (publicNodes.length) {
      subnets.push({
        id: "subnet-public",
        layoutOptions: { "elk.padding": "[top=34,left=16,bottom=16,right=16]" },
        labels: [{ text: CONTAINER_LABEL["subnet-public"] }],
        children: publicNodes.map(serviceChild),
      });
    }
    if (privateNodes.length) {
      subnets.push({
        id: "subnet-private",
        layoutOptions: { "elk.padding": "[top=34,left=16,bottom=16,right=16]" },
        labels: [{ text: CONTAINER_LABEL["subnet-private"] }],
        children: privateNodes.map(serviceChild),
      });
    }
    if (subnets.length) {
      regionChildren.push({
        id: "vpc",
        layoutOptions: { "elk.padding": "[top=34,left=18,bottom=18,right=18]" },
        labels: [{ text: CONTAINER_LABEL["vpc"] }],
        children: [
          {
            id: "az",
            layoutOptions: { "elk.padding": "[top=34,left=16,bottom=16,right=16]" },
            labels: [{ text: CONTAINER_LABEL["az"] }],
            children: subnets,
          },
        ],
      });
    }
  }

  const graph = {
    id: "cloud",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "DOWN",
      "elk.edgeRouting": "ORTHOGONAL",
      "elk.hierarchyHandling": "INCLUDE_CHILDREN",
      "elk.layered.nodePlacement.strategy": "NETWORK_SIMPLEX",
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

  const res: any = await elk.layout(graph as any);

  // ── flatten ELK's relative coordinates to absolute canvas coordinates ──
  const containers: LaidContainer[] = [];
  const nodes: LaidNode[] = [];
  const nodeById = new Map<string, PlanedNode>(
    [...model.data, ...model.control].map((n) => [n.id, n])
  );
  const abs = new Map<string, { x: number; y: number }>();

  const walk = (elkNode: any, ox: number, oy: number, parentId?: string) => {
    const x = ox + (elkNode.x ?? 0);
    const y = oy + (elkNode.y ?? 0);
    abs.set(elkNode.id, { x, y });
    const isContainer = Array.isArray(elkNode.children) && elkNode.children.length > 0
      && !nodeById.has(elkNode.id);
    if (isContainer && elkNode.id in CONTAINER_LABEL) {
      containers.push({
        id: elkNode.id,
        kind: elkNode.id as ContainerId,
        label: CONTAINER_LABEL[elkNode.id],
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
