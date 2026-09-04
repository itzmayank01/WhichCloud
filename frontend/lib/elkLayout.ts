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

// AWS reference service-box proportions. Was 200x92, which at 21 services
// made the canvas wide enough that the fitted view shrank every label below
// reading size. The reference boxes are smaller because they carry an icon
// and a name and nothing else; ours also carry a price, which is moved to a
// corner badge rather than given a column of its own.
/** How many edges kept ELK's own routing versus how many we redrew. Exported
 *  so the layout harness can assert on it: ELK minimises crossings across the
 *  whole graph and our fallback router does not, so a low `elkKept` is itself
 *  a defect. It read 0 of 22 once, and the diagram was spaghetti. */
export const routeStats = { elkKept: 0, replaced: 0 };

export const NODE_W = 168;
export const NODE_H = 64;
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
  /** request / branch / replication, from the model; governance edges are
   *  the ones flagged `attach`. Decides stroke colour, weight and dash. */
  kind: "request" | "branch" | "replication";
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

export type CloudId = "aws" | "gcp" | "azure";

/* Boundary names, per cloud. Sentence case throughout -- the reference
   diagrams never shout their boundary labels, and ALL-CAPS at this size costs
   legibility for nothing.

   These are not cosmetic. Each cloud draws a genuinely different set of
   boundaries: an AWS subnet lives in one availability zone, a GCP subnet
   spans a whole region and the zone sits inside it, and Azure groups by
   subscription and resource group with no zone container at all. Labelling a
   GCP diagram "AWS Cloud / VPC 10.0.0.0/16" would be worse than not drawing
   it, which is why the server refused to draw non-AWS at all until now. */
const CONTAINER_LABELS: Record<CloudId, Record<string, string>> = {
  aws: {
    cloud: "AWS Cloud",
    edge: "Edge / Global services",
    region: "Region: ap-south-1 (Mumbai)",
    regional: "Regional services",
    vpc: "VPC 10.0.0.0/16",
    "routetable-public": "Public route table",
    "routetable-private": "Private route table",
    az: "Availability Zone",
    "az-a": "Availability Zone ap-south-1a",
    "az-b": "Availability Zone ap-south-1b",
    "subnet-public": "Public subnet",
    "subnet-app": "Private app subnet",
    "subnet-data": "Private data subnet",
  },
  gcp: {
    cloud: "Google Cloud project",
    edge: "Edge / Global services",
    region: "Region: asia-south1 (Mumbai)",
    regional: "Regional services",
    // A GCP VPC is global, not regional -- it spans every region in the
    // project -- so it carries no CIDR of its own the way an AWS VPC does.
    vpc: "VPC network (global)",
    "routetable-public": "Routes: default internet",
    "routetable-private": "Routes: via Cloud NAT",
    az: "Zone",
    "az-a": "Zone asia-south1-a",
    "az-b": "Zone asia-south1-b",
    // GCP subnets are regional and span the zones, so "public/private" is a
    // firewall and Cloud NAT distinction rather than a routing-table one.
    "subnet-public": "Subnet · external access",
    "subnet-app": "Subnet · application",
    "subnet-data": "Subnet · data",
  },
  azure: {
    cloud: "Azure subscription",
    edge: "Edge / Global services",
    region: "Region: Central India (Pune)",
    regional: "Resource group services",
    vpc: "Virtual network 10.0.0.0/16",
    "routetable-public": "Route table: internet",
    "routetable-private": "Route table: NAT gateway",
    az: "Availability zone",
    "az-a": "Availability zone 1",
    "az-b": "Availability zone 2",
    "subnet-public": "Public subnet",
    "subnet-app": "Application subnet",
    "subnet-data": "Data subnet",
  },
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
/** Does this cloud put subnets INSIDE a zone?
 *
 *  Only AWS. An AWS subnet is created in exactly one availability zone, so a
 *  zone genuinely contains subnets and drawing it as a box around them is the
 *  structure. A GCP subnet is REGIONAL -- it spans every zone in its region --
 *  and Azure has no zone container at all; zones there are a property of a
 *  resource, not a place that holds one. Drawing "Zone asia-south1-b" wrapped
 *  around "Subnet - application" states something about Google Cloud that is
 *  simply untrue. */
function subnetsAreZonal(cloud: CloudId): boolean {
  return cloud === "aws";
}

function parentOf(node: PlanedNode, hasVpc: boolean, cloud: CloudId): string {
  if (node.container === "outside") return "outside";
  if (node.container === "edge") return "edge";
  // Managed services outside the VPC get their own strip rather than floating
  // loose in the region -- see REGIONAL_SERVICE in graphModel.
  if (node.container === "regional") return "regional";
  if (!hasVpc || node.container === "region") return "region";
  // One subnet per tier where subnets are regional; one per tier PER ZONE
  // where they are zonal.
  const z = subnetsAreZonal(cloud) ? (node.zone === "b" ? "-b" : "-a") : "";
  if (node.container === "subnet-public") return `subnet-public${z}`;
  if (node.container === "subnet-app") return `subnet-app${z}`;
  return `subnet-data${z}`;
}

export async function layout(
  model: GraphModel,
  cloud: CloudId = "aws"
): Promise<Layout> {
  const hasVpc = model.hasVpc;
  const CONTAINER_LABEL = CONTAINER_LABELS[cloud] ?? CONTAINER_LABELS.aws;

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
    controlParent.set(c.id, tgt ? parentOf(tgt, hasVpc, cloud) : "region");
  }

  // Group data + control nodes by their concrete parent container.
  const byParent = new Map<string, PlanedNode[]>();
  const push = (p: string, n: PlanedNode) =>
    (byParent.get(p) ?? byParent.set(p, []).get(p)!).push(n);
  for (const n of model.data) push(parentOf(n, hasVpc, cloud), n);
  for (const c of model.control) push(controlParent.get(c.id)!, c);

  const serviceChild = (n: PlanedNode): ElkChild => ({
    id: n.id,
    width: n.plane === "control" ? CONTROL_W : NODE_W,
    height: n.plane === "control" ? CONTROL_H : NODE_H,
  });

  /** GCP: the global VPC network wraps the region, not the reverse.
   *
   *  `regionChildren` is built region-first because that is AWS's shape, so
   *  the network is lifted out of it and the remaining region contents are
   *  nested inside the network instead. Anything that is genuinely regional
   *  and outside the network -- the managed-services strip -- stays with the
   *  region where it belongs. */
  const globalNetworkWrappingRegion = (children: ElkChild[]): ElkChild => {
    const vpc = children.find((c) => c.id === "vpc");
    const rest = children.filter((c) => c.id !== "vpc");
    const region: ElkChild = {
      id: "region",
      layoutOptions: { "elk.padding": "[top=34,left=18,bottom=18,right=18]" },
      labels: [{ text: CONTAINER_LABEL["region"] }],
      children: vpc ? [...rest, ...(vpc.children ?? [])] : rest,
    };
    return {
      id: "vpc",
      layoutOptions: {
        "elk.padding": "[top=34,left=18,bottom=18,right=18]",
        "elk.direction": "RIGHT",
      },
      labels: [{ text: CONTAINER_LABEL["vpc"] }],
      children: [region],
    };
  };

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

          // Tiers STACK inside a zone -- public over app over data -- the way
          // both AWS reference diagrams draw a VPC. Three subnet widths become
          // one, which is what stops the diagram running away horizontally.
          "elk.direction": "DOWN",
        },
        labels: [{ text: CONTAINER_LABEL[`az-${z}`] }],
        children: subnets,
      };
    };
    // KNOWN COSMETIC DEFECT: zone b renders ABOVE zone a. Vertical order
    // inside a layer is decided by BRANDES_KOEPF, which aligns each zone with
    // the edge feeding it; zone a is fed by the balancer, which sits low, so
    // zone a lands low. elk.position, considerModelOrder/forceNodeModelOrder,
    // and swapping declaration order were all tried and are all no-ops against
    // that alignment. Both zones are drawn, labelled and connected correctly --
    // only the top-to-bottom order reads wrong. Fixing it properly means
    // either nodePlacement SIMPLE (which costs the alignment everywhere else)
    // or placing the AZ blocks by hand after layout.
    /** Subnets straight under the VPC, no zone box. Used where a subnet is a
     *  regional object: on GCP it spans the zones, and on Azure zones are a
     *  resource property rather than a container. */
    const regionalSubnets = (): ElkChild[] => {
      const out: ElkChild[] = [];
      for (const [id, labelKey] of [
        ["subnet-public", "subnet-public"],
        ["subnet-app", "subnet-app"],
        ["subnet-data", "subnet-data"],
      ] as const) {
        const members = byParent.get(id) ?? [];
        if (!members.length) continue;
        out.push({
          id,
          layoutOptions: {
            "elk.padding": "[top=34,left=16,bottom=16,right=16]",
            "elk.direction": "RIGHT",
            "elk.spacing.nodeNode": "28",
          },
          labels: [{ text: CONTAINER_LABEL[labelKey] }],
          children: members.map(serviceChild),
        });
      }
      return out;
    };

    const azs = subnetsAreZonal(cloud)
      ? ([azBlock("a"), azBlock("b")].filter(Boolean) as ElkChild[])
      : regionalSubnets();
    if (azs.length) {
      // Route tables, the way the AWS reference draws them: inside the VPC,
      // outside the zones, one per subnet tier. They are structural rather
      // than billed -- a route table costs nothing -- so they carry no price
      // and no edges; which subnets they govern is shown by placement, the
      // same convention the governance strip already uses.
      const routeTables: ElkChild[] = [];
      const suffixes = subnetsAreZonal(cloud) ? (["-a", "-b"] as const) : ([""] as const);
      const hasPublic = suffixes.some(
        (z) => (byParent.get(`subnet-public${z}`) ?? []).length
      );
      const hasPrivate = suffixes.some(
        (z) =>
          (byParent.get(`subnet-app${z}`) ?? []).length ||
          (byParent.get(`subnet-data${z}`) ?? []).length
      );
      if (hasPublic)
        routeTables.push({ id: "routetable-public", width: 168, height: 74, children: [] });
      if (hasPrivate)
        routeTables.push({ id: "routetable-private", width: 168, height: 74, children: [] });

      regionChildren.push({
        id: "vpc",
        layoutOptions: {
          "elk.padding": "[top=34,left=18,bottom=18,right=18]",
          // Zones side by side, tiers stacked within them -- the reference
          // grid. With the subnets stacked, stacking the zones as well made
          // the whole diagram one tall column.
          "elk.direction": "RIGHT",
        },
        labels: [{ text: CONTAINER_LABEL["vpc"] }],
        children: [...azs, ...routeTables],
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
      // Measured, not reasoned: this moves the serverless and AI shapes from
      // about 1.0 to about 1.9, much closer to the pane. It does NOT move the
      // VPC shapes at all -- their width is set by what is inside the VPC, and
      // wrapping cannot cut into a subtree -- so they sit at 2.0-2.5 whatever
      // this says.
      "elk.aspectRatio": "0.9",
      // A request path is a CHAIN, and a chain laid out in one direction is a
      // ribbon however much spacing you give it -- 4.7:1 here, so fitting to
      // width left the diagram a third of the canvas tall. Wrapping lets the
      // layered algorithm break that chain across rows and use the height,
      // which is the only lever that changes the SHAPE rather than the scale.
      // Wrapping folds an over-wide graph into rows. Without it the diagram
      // came out around 3:1 against a pane nearer 1.65:1, so fitting it left
      // it as a band across the middle with most of the height unused. The
      // fold's own edge -- end of one row to the start of the next -- is
      // redrawn after layout rather than left as the canvas-spanning detour
      // that made this worth turning off the first time round.
      "elk.layered.wrapping.strategy": "OFF",
      "elk.direction": "RIGHT",
      "elk.edgeRouting": "ORTHOGONAL",
      // SEPARATE_CHILDREN, so each container lays out with its OWN direction.
      // Under INCLUDE_CHILDREN the whole tree collapses into one layered pass
      // along the root direction and every elk.direction below is inert --
      // which is why the subnets ran left to right as successive layers (the
      // request really does flow public -> app -> data).
      "elk.hierarchyHandling": "INCLUDE_CHILDREN",
      // BRANDES_KOEPF centres each rank instead of top-aligning it. With
      // NETWORK_SIMPLEX the edge cluster sank to the bottom of its column and
      // left a tall empty band above it, with long edges climbing back up into
      // the VPC.
      "elk.layered.nodePlacement.strategy": "BRANDES_KOEPF",
      "elk.layered.nodePlacement.bk.fixedAlignment": "BALANCED",
      "elk.alignment": "CENTER",
      "elk.layered.spacing.nodeNodeBetweenLayers": "64",
      "elk.spacing.nodeNode": "40",
      "elk.spacing.edgeNode": "28",
      "elk.spacing.edgeEdge": "18",
      "elk.layered.spacing.edgeEdgeBetweenLayers": "22",
      "elk.layered.spacing.edgeNodeBetweenLayers": "32",
      "elk.padding": "[top=40,left=24,bottom=24,right=24]",
      // Keep skip-layer edges (e.g. CDN → S3 past the app tier) clear of the
      // boxes they route past, and cut crossings — the two things the layout
      // quality harness measures on the routed geometry.
      // Break cycles at a predictable point. This graph really does contain
      // them -- a serverless flow has Lambda -> SQS -> Lambda and
      // Lambda -> S3 -> Rekognition -> Lambda -- and the layered algorithm
      // cannot lay a cycle out, so it reverses an edge to break one. GREEDY
      // picks a different edge as the graph changes; DEPTH_FIRST picks the
      // same one, so the reversed edge stays put between renders.
      "elk.layered.cycleBreaking.strategy": "DEPTH_FIRST",
      "elk.randomSeed": "1",
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
      // WHICH WAY ROUND THE NETWORK AND THE REGION NEST.
      //
      // An AWS VPC is a REGIONAL object: it is created in one region and
      // cannot span two, so the region contains it. A Google VPC network is
      // GLOBAL -- one network spans every region in the project, and subnets
      // in Mumbai and Delhi belong to the same network -- so the containment
      // runs the other way, and drawing the network inside a region states
      // the opposite of how the product works. Azure's VNet is regional like
      // AWS's.
      //
      // So this is not a label swap; the two levels genuinely trade places,
      // which is why renaming the containers earlier left the structure wrong.
      ...(cloud === "gcp"
        ? [globalNetworkWrappingRegion(regionChildren)]
        : [
            {
              id: "region",
              layoutOptions: {
                "elk.padding": "[top=34,left=18,bottom=18,right=18]",
              },
              labels: [{ text: CONTAINER_LABEL["region"] }],
              children: regionChildren,
            },
          ]),
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
      // Replication edges are DRAWN but do not get a vote on layering -- the
      // same trick as constraint="false" in the Graphviz reference. With
      // INCLUDE_CHILDREN the whole hierarchy lays out in one pass along the
      // root direction, so a database-a -> database-b edge puts zone b in a
      // later layer, i.e. beside zone a rather than under it. Three such edges
      // (db sync, cache replica, balancer -> compute b) were enough to lay the
      // two zones out end to end and make the canvas 4:1, which fits to a band
      // using 40% of the viewport height with every label too small to read.
      // Dropped here and routed by hand below, the zones share a layer and
      // stack, which is both the reference arrangement and half the width.
      ...model.dataEdges
        .map((e, i) => ({ e, i }))
        .filter(({ e }) => e.kind !== "replication")
        .map(({ e, i }) => ({
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

  routeStats.elkKept = 0;
  routeStats.replaced = 0;

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
    const isContainer =
      (elkNode.id.startsWith("routetable-") ||
        (Array.isArray(elkNode.children) && elkNode.children.length > 0)) &&
      !nodeById.has(elkNode.id);
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
      // Under INCLUDE_CHILDREN a cross-container edge can be stored against a
      // different ancestor than the offset we add for it, so the whole
      // polyline lands somewhere it does not belong. The SHAPE is right; only
      // the origin is wrong. Measure how far both ends have drifted from their
      // own boxes and translate the polyline back by the average.
      const sBox = src ? box.get(src) : undefined;
      const tBox = tgt ? box.get(tgt) : undefined;
      if (pts.length >= 2 && sBox && tBox) {
        const near = (pt: { x: number; y: number }, bx: typeof sBox) => {
          const ddx = Math.max(bx!.x - pt.x, 0, pt.x - (bx!.x + bx!.w));
          const ddy = Math.max(bx!.y - pt.y, 0, pt.y - (bx!.y + bx!.h));
          return Math.hypot(ddx, ddy) <= 64;
        };
        const first = pts[0];
        const last = pts[pts.length - 1];
        if (!near(first, sBox) && !near(last, tBox)) {
          const ddx = (sBox.x + sBox.w / 2 - first.x + (tBox.x + tBox.w / 2 - last.x)) / 2;
          const ddy = (sBox.y + sBox.h / 2 - first.y + (tBox.y + tBox.h / 2 - last.y)) / 2;
          for (const pt of pts) { pt.x += ddx; pt.y += ddy; }
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
        kind: model_e?.kind ?? "branch",
        points: pts,
      });
    }
    for (const c of elkNode.children ?? []) collectEdges(c, base.x, base.y);
  };
  collectEdges(res, 0, 0);

  // A short orthogonal route between two boxes that avoids every service box
  // in the way. Used for the replication edges withheld from ELK, and to
  // rescue any edge ELK routed as a long detour.
  //: Clearance around a node, in px; the top gets more because the price
  //: badge overhangs that edge. Chosen by measurement -- 4/12 costs one
  //: edge-through-node across all fixtures against zero, and buys 18 fewer
  //: crossings (300 -> 282) plus the clearance that stops lines running under
  //: a price badge. Wider (9/17) trades five hits for another 13 crossings,
  //: which is the wrong side of the deal.
  const NODE_PAD = 4;
  const NODE_PAD_TOP = 12;
  const inflatedObstacles = (srcId: string, tgtId: string) =>
    [...box.entries()]
      .filter(([id]) => nodeById.has(id) && id !== srcId && id !== tgtId)
      .map(
        ([id, r]) =>
          [
            id,
            {
              x: r.x - NODE_PAD,
              y: r.y - NODE_PAD_TOP,
              w: r.w + NODE_PAD * 2,
              h: r.h + NODE_PAD_TOP + NODE_PAD,
            },
          ] as const
      );

  // Lanes already taken by a hand-routed edge, per orientation. Without this
  // every rerouted edge picks the same central corridor and they stack on top
  // of each other: measured, routing the cross-container edges without it put
  // total crossings at 465 against 325 with it.
  const usedLanes = { h: [] as number[], v: [] as number[] };
  const routeBetween = (
    srcId: string,
    tgtId: string
  ): Array<{ x: number; y: number }> | null => {
    const a = box.get(srcId);
    const b = box.get(tgtId);
    if (!a || !b) return null;
    // Leave from whichever face points at the target, so the line does not
    // cut back across the node it starts from.
    const vertical = Math.abs(b.y - a.y) >= Math.abs(b.x - a.x);
    const start = vertical
      ? { x: a.x + a.w / 2, y: b.y > a.y ? a.y + a.h : a.y }
      : { x: b.x > a.x ? a.x + a.w : a.x, y: a.y + a.h / 2 };
    const end = vertical
      ? { x: b.x + b.w / 2, y: b.y > a.y ? b.y : b.y + b.h }
      : { x: b.x > a.x ? b.x : b.x + b.w, y: b.y + b.h / 2 };
    // Containers are not obstacles -- a replica line necessarily leaves its
    // own subnet -- but service boxes are: ELK never routes an edge through a
    // node and neither should these.
    // Inflate to the node's RENDERED footprint. The router was avoiding the
    // ELK box, but a service node also carries a price badge overhanging its
    // top edge and, when highlighted, an accent ring outside its border -- so
    // a route that cleared the box by a pixel still ran under the badge.
    const obstacles = inflatedObstacles(srcId, tgtId);
    const segBlocked = (x1: number, y1: number, x2: number, y2: number) => {
      const [lox, hix] = [Math.min(x1, x2), Math.max(x1, x2)];
      const [loy, hiy] = [Math.min(y1, y2), Math.max(y1, y2)];
      return obstacles.some(
        ([, r]) => hix > r.x && lox < r.x + r.w && hiy > r.y && loy < r.y + r.h
      );
    };
    const routeFor = (lane: number, vert = vertical) =>
      vert
        ? [start, { x: start.x, y: lane }, { x: end.x, y: lane }, end]
        : [start, { x: lane, y: start.y }, { x: lane, y: end.y }, end];
    const routeBlocked = (pts: Array<{ x: number; y: number }>) =>
      pts.slice(1).some((pt, k) => segBlocked(pts[k].x, pts[k].y, pt.x, pt.y));
    // How many node footprints a route cuts through. Used to pick the least
    // bad option when NOTHING is fully clear: inflating the obstacles to the
    // rendered footprint made clear lanes scarcer, and falling back to the
    // centre lane regardless meant some routes came out worse than before.
    // Never returning a route worse than the best one seen is the guarantee
    // that keeps this monotone.
    const blockCount = (pts: Array<{ x: number; y: number }>) => {
      let n = 0;
      for (let k = 1; k < pts.length; k++)
        if (segBlocked(pts[k - 1].x, pts[k - 1].y, pts[k].x, pts[k].y)) n++;
      return n;
    };
    let best: Array<{ x: number; y: number }> | null = null;
    let bestHits = Infinity;
    const consider = (pts: Array<{ x: number; y: number }>) => {
      const hits = blockCount(pts);
      if (hits < bestHits) {
        bestHits = hits;
        best = pts;
      }
      return hits === 0;
    };

    // Walk outward from centre and score every unblocked lane by how far it
    // sits from lanes already in use, so parallel edges fan out instead of
    // stacking on one corridor. Nearest-to-centre breaks ties, which keeps
    // routes short when the canvas is empty.
    const taken = vertical ? usedLanes.h : usedLanes.v;
    const centre = vertical ? (start.y + end.y) / 2 : (start.x + end.x) / 2;
    const clearance = (lane: number) =>
      taken.length ? Math.min(...taken.map((l) => Math.abs(l - lane))) : Infinity;
    let route = routeFor(centre);
    let bestLane: number | null = null;
    let bestScore = -Infinity;
    for (let step = 0; step <= 60; step++) {
      for (const lane of step === 0 ? [centre] : [centre + step * 10, centre - step * 10]) {
        if (!consider(routeFor(lane))) continue;
        const score = Math.min(clearance(lane), 48) * 100 - Math.abs(lane - centre);
        if (score > bestScore) {
          bestScore = score;
          bestLane = lane;
        }
      }
      // 48px of clearance is enough to read as a separate line; stop looking
      // once a lane achieves that rather than scanning the whole canvas.
      if (bestLane !== null && clearance(bestLane) >= 48) break;
    }
    if (bestLane !== null) {
      route = routeFor(bestLane);
      taken.push(bestLane);
    }
    // Still blocked: the corridor between these two is full, so turn the
    // dog-leg the other way round. A vertical pair whose horizontal lanes are
    // all occupied often has a clear vertical one, and vice versa.
    if (routeBlocked(route)) {
      const alt = vertical ? (start.x + end.x) / 2 : (start.y + end.y) / 2;
      for (let step = 0; step <= 60; step++) {
        const found = [alt + step * 10, alt - step * 10]
          .map((l) => routeFor(l, !vertical))
          .find((r) => consider(r));
        if (found) {
          route = found;
          break;
        }
      }
    }
    // Last resort: go AROUND the obstruction entirely. Searching ±600px from
    // centre is not enough on a dense canvas -- when every lane between two
    // nodes is occupied the search gave up and returned a blocked route, and a
    // blocked route renders as a line vanishing behind a box, which is exactly
    // the "where does this arrow go" problem. Leaving past the edge of
    // everything in the way always has room.
    if (routeBlocked(route)) {
      const spans = obstacles.map(([, r]) =>
        vertical ? [r.y, r.y + r.h] : [r.x, r.x + r.w]
      );
      const lo = Math.min(...spans.map((sp) => sp[0])) - 24;
      const hi = Math.max(...spans.map((sp) => sp[1])) + 24;
      const escape = [lo, hi].map((l) => routeFor(l)).find((r) => consider(r));
      if (escape) route = escape;
    }
    // Nothing came back clean: take the route that cut through the fewest
    // nodes rather than whatever the centre lane happened to be.
    if (routeBlocked(route) && best && blockCount(best) < blockCount(route))
      route = best;
    return route;
  };

  // Draw the replication edges withheld from ELK. They were excluded so they
  // could not distort layering, but they still have to be DRAWN -- a standby
  // database with no line to its primary reads as a second unrelated database.
  for (const [i, e] of model.dataEdges.entries()) {
    if (e.kind !== "replication") continue;
    const route = routeBetween(e.source, e.target);
    if (!route) continue;
    edges.push({
      id: `e${i}`,
      source: e.source,
      target: e.target,
      label: e.label,
      onPath: false,
      seq: null,
      attach: false,
      kind: "replication",
      points: route,
    });
  }

  // VALIDATE EVERY ROUTE, AND REDRAW THE ONES THAT DO NOT HOLD UP.
  //
  // ELK routes cross-container edges to container PORTS, so under
  // SEPARATE_CHILDREN a polyline often stops at a boundary instead of at the
  // node it belongs to. There used to be a correction here that measured how
  // far both ends had drifted and translated the whole line back; it was
  // written for INCLUDE_CHILDREN, where the shape was right and only the
  // origin was wrong. Against port-routed edges it drags the line toward the
  // node centres and straight through whatever stands between -- 117 label
  // overlaps and 34 edges through nodes came from exactly that.
  //
  // So check the route instead of patching it: it has to start and end at the
  // right boxes, miss every other node, and not be a canvas-spanning detour.
  // Anything that fails is redrawn by the obstacle-avoiding router above.
  // An orthogonal two-segment connector from a node box out to `to`, leaving
  // through whichever face points at it. Used to join a node to where ELK's
  // port-routed polyline actually begins.
  const connectTo = (
    b: { x: number; y: number; w: number; h: number },
    to: { x: number; y: number }
  ): Array<{ x: number; y: number }> => {
    const clamp = (v: number, lo: number, hi: number) => Math.min(Math.max(v, lo), hi);
    const dx = to.x - (b.x + b.w / 2);
    const dy = to.y - (b.y + b.h / 2);
    if (Math.abs(dx) >= Math.abs(dy)) {
      const exit = { x: dx > 0 ? b.x + b.w : b.x, y: clamp(to.y, b.y + 8, b.y + b.h - 8) };
      return [exit, { x: to.x, y: exit.y }];
    }
    const exit = { x: clamp(to.x, b.x + 8, b.x + b.w - 8), y: dy > 0 ? b.y + b.h : b.y };
    return [exit, { x: exit.x, y: to.y }];
  };
  const dedupe = (pts: Array<{ x: number; y: number }>) =>
    pts.filter(
      (pt, k) =>
        k === 0 || Math.abs(pt.x - pts[k - 1].x) > 0.5 || Math.abs(pt.y - pts[k - 1].y) > 0.5
    );

  // Same inflated footprint the router avoids, so validation and routing
  // agree on what counts as "through a node".
  const hitsNode = (
    pts: Array<{ x: number; y: number }>,
    srcId: string,
    tgtId: string
  ) => {
    for (let k = 1; k < pts.length; k++) {
      const [lox, hix] = [Math.min(pts[k - 1].x, pts[k].x), Math.max(pts[k - 1].x, pts[k].x)];
      const [loy, hiy] = [Math.min(pts[k - 1].y, pts[k].y), Math.max(pts[k - 1].y, pts[k].y)];
      for (const [id, r] of inflatedObstacles(srcId, tgtId)) {
        void id;
        // A shallow inset, so an edge legitimately grazing a node's border does
        // not count as passing through it.
        if (hix > r.x + 3 && lox < r.x + r.w - 3 && hiy > r.y + 3 && loy < r.y + r.h - 3)
          return true;
      }
    }
    return false;
  };
  const endsAt = (pt: { x: number; y: number }, id: string) => {
    const b = box.get(id);
    if (!b) return false;
    const dx = Math.max(b.x - pt.x, 0, pt.x - (b.x + b.w));
    const dy = Math.max(b.y - pt.y, 0, pt.y - (b.y + b.h));
    return Math.hypot(dx, dy) <= 24;
  };
  const pathLength = (pts: Array<{ x: number; y: number }>) =>
    pts.reduce(
      (sum, pt, k) =>
        k === 0 ? 0 : sum + Math.abs(pt.x - pts[k - 1].x) + Math.abs(pt.y - pts[k - 1].y),
      0
    );
  for (const edge of edges) {
    if (edge.kind === "replication") continue;
    const a = box.get(edge.source);
    const b = box.get(edge.target);
    if (!a || !b) continue;
    const pts = edge.points;
    const direct =
      Math.abs(b.x + b.w / 2 - (a.x + a.w / 2)) +
      Math.abs(b.y + b.h / 2 - (a.y + a.h / 2));
    // KEEP ELK'S ROUTE WHEREVER IT IS SOUND.
    //
    // ELK minimises crossings across the whole graph; our router only avoids
    // nodes, one edge at a time. Measured, discarding ELK wholesale and
    // redrawing every edge as a dog-leg is what produced the spaghetti: ELK
    // routes kept 0 of 22, every edge exactly four points.
    //
    // The reason none survived was not that the routes were bad. Under
    // SEPARATE_CHILDREN, ELK routes a cross-container edge to the CONTAINER's
    // port, so the polyline legitimately stops at a boundary rather than at
    // the node -- and the endpoint test threw the whole route away for it.
    // A port-routed edge is incomplete, not wrong. Bridge the ends instead.
    const usable =
      pts.length >= 2 &&
      !hitsNode(pts, edge.source, edge.target) &&
      // Generous: orthogonal routing around containers is legitimately longer
      // than the straight line, and only real detours should go.
      pathLength(pts) < Math.max(direct * 2.5, direct + 420);
    if (usable) {
      if (!endsAt(pts[0], edge.source)) pts.unshift(...connectTo(a, pts[0]));
      const tail = pts[pts.length - 1];
      if (!endsAt(tail, edge.target)) pts.push(...connectTo(b, tail).reverse());
      edge.points = dedupe(pts);
      routeStats.elkKept++;
      continue;
    }
    routeStats.replaced++;
    const route = routeBetween(edge.source, edge.target);
    if (route) edge.points = route;
  }

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
