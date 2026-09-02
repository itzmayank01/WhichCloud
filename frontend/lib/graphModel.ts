/**
 * The architecture graph model — three planes, derived from the priced
 * topology, so the renderer is a pure function of the component graph.
 *
 * A diagram that draws every service in one flat row, with governance boxes
 * dangling off arrows to nowhere, is unreadable however prettily it is laid
 * out. Real AWS reference diagrams separate three concerns, and so do we:
 *
 *   DATA plane     things a request or event flows THROUGH. Directed, ordered,
 *                  animatable. The only plane that carries arrows.
 *   CONTROL plane  things that act ON a data-plane node but are not in the
 *                  path — KMS, Secrets, ACM, Cognito, Backup, DNS. Drawn as a
 *                  dotted attachment line to the one node each serves.
 *   ACCOUNT plane  account-wide observability and governance — CloudTrail,
 *                  GuardDuty, Security Hub, Config, VPC Flow Logs, CloudWatch,
 *                  X-Ray. A labelled band, NO edges: they watch everything, so
 *                  an arrow to any one node would be a lie.
 *
 * This module is pure TypeScript with no React or DOM dependency, so the
 * layout quality harness imports exactly the graph the browser renders.
 */

import type { Node as TopoNode, Edge as TopoEdge } from "@/lib/api";

export type Plane = "data" | "control" | "account";

/** Which plane each topology `kind` belongs to. A kind absent here defaults
 *  to the data plane — a new priced service shows up in the flow rather than
 *  vanishing, the failure mode we are fixing. */
const PLANE_BY_KIND: Record<string, Plane> = {
  // ── account plane: watches everything, connected to nothing ──
  audit: "account", // CloudTrail
  threat: "account", // GuardDuty
  posture: "account", // Security Hub / Config
  flowlogs: "account", // VPC Flow Logs
  monitoring: "account", // CloudWatch
  tracing: "account", // X-Ray
  // ── control plane: acts on one data node, dotted attachment ──
  kms: "control",
  secrets: "control",
  tls: "control", // ACM
  auth: "control", // Cognito
  dns: "control", // Route 53 resolves the entry point
  backup: "control",
  // everything else is data plane (see default in planeOf)
};

export function planeOf(kind: string): Plane {
  return PLANE_BY_KIND[kind] ?? "data";
}

/** The canonical order of the request/data path. Present nodes are threaded
 *  onto this spine to assign sequence numbers; a kind not on it is still a
 *  data node (a branch off the spine), it just carries no step number. */
const FLOW_SPINE: string[] = [
  "users", // the client node's id (kind "client")
  "dns",
  "network", // CloudFront / edge
  "waf",
  "apigateway",
  "loadbalancer",
  "compute",
  "compute_fargate",
  "lambda",
  "database",
  "dynamodb",
  "timestream",
  "search",
  "warehouse",
];

/** Data-plane branch edges: (from → to, label), drawn but NOT sequenced —
 *  they hang off the spine (a cache lookup, a replica, an async fan-out). Only
 *  added when both endpoints are present. */
const BRANCH_EDGES: Array<[string, string, string]> = [
  ["compute", "cache", "cache"],
  ["compute_fargate", "cache", "cache"],
  ["lambda", "cache", "cache"],
  ["database", "database_replica", "replicates"],
  ["compute", "storage", "objects"],
  ["compute_fargate", "storage", "objects"],
  ["lambda", "storage", "objects"],
  ["network", "storage", "assets"],
  ["compute", "queue", "enqueue"],
  ["lambda", "queue", "enqueue"],
  ["queue", "notification", "fan-out"],
  ["compute", "notification", "notify"],
  ["lambda", "notification", "notify"],
  ["compute", "email", "email"],
  ["lambda", "email", "email"],
  ["compute", "streaming", "events"],
  ["lambda", "streaming", "events"],
  ["iot", "streaming", "ingest"],
  ["streaming", "firehose", "deliver"],
  ["firehose", "storage", "land"],
  ["streaming", "timestream", "writes"],
  // Kafka (MSK) plays the same role as the Kinesis stream at the top tier.
  ["iot", "kafka", "ingest"],
  ["compute", "kafka", "events"],
  ["compute_fargate", "kafka", "events"],
  ["lambda", "kafka", "events"],
  ["kafka", "firehose", "deliver"],
  ["kafka", "timestream", "writes"],
  ["kafka", "storage", "land"],
  ["kafka", "warehouse", "load"],
  ["kafka", "search", "index"],
  ["storage", "athena", "query"],
  ["storage", "glue", "catalog"],
  ["glue", "warehouse", "load"],
  ["athena", "warehouse", "load"],
  ["storage", "warehouse", "load"],
  ["storage", "rekognition", "analyze"],
  ["storage", "comprehend", "analyze"],
  ["lambda", "rekognition", "infer"],
  ["lambda", "comprehend", "infer"],
  ["compute", "nat", "outbound"],
  ["compute_fargate", "nat", "outbound"],
];

/** Which data node a control-plane service attaches to, in priority order.
 *  The first present target wins; if none is present the control node is
 *  dropped (nothing to attach a dotted line to). */
const CONTROL_TARGETS: Record<string, string[]> = {
  kms: ["database", "dynamodb", "timestream", "storage", "warehouse"],
  secrets: ["compute", "compute_fargate", "lambda", "database"],
  tls: ["network", "apigateway", "loadbalancer", "compute"],
  auth: ["apigateway", "loadbalancer", "compute", "compute_fargate", "lambda"],
  dns: ["network", "waf", "apigateway", "loadbalancer", "compute"],
  backup: ["storage", "database", "dynamodb"],
};

export type PlanedNode = TopoNode & {
  plane: Plane;
  /** Request-path step number, 1-based; null for branch/unsequenced data nodes
   *  and for every control/account node. */
  seq: number | null;
  /** For a control node: the id of the data node it attaches to. */
  attachedTo?: string;
  /** Container placement, for the data plane. */
  container?: ContainerId;
};

export type ContainerId =
  | "cloud"
  | "region"
  | "vpc"
  | "az"
  | "subnet-public"
  | "subnet-private"
  | null;

export type DataEdge = {
  source: string;
  target: string;
  label: string;
  /** On the sequenced request spine (gets a badge + animates) vs a branch. */
  onPath: boolean;
  seq: number | null;
};

export type GraphModel = {
  data: PlanedNode[];
  control: PlanedNode[];
  account: PlanedNode[];
  dataEdges: DataEdge[];
  /** dotted attachment lines: control node → the data node it serves. */
  attachments: Array<{ source: string; target: string }>;
  /** whether a VPC is drawn at all (no VPC-resident kinds ⇒ serverless). */
  hasVpc: boolean;
};

/** Kinds that physically run inside a VPC subnet. Anything else (Lambda,
 *  DynamoDB, S3, API Gateway, CloudFront, Athena, Glue) is a regional managed
 *  service that sits outside the VPC — drawing a VPC around them is the bug
 *  that once wrapped a serverless app in a subnet it never had. */
const VPC_RESIDENT = new Set([
  "compute",
  "compute_fargate",
  "cache",
  "database",
  "database_replica",
  "search",
  "warehouse",
  "kafka",
  "nat",
  "loadbalancer",
]);

/** Public-subnet kinds face the internet; the rest sit private. */
const PUBLIC_SUBNET = new Set(["loadbalancer", "nat"]);

function containerFor(kind: string, hasVpc: boolean): ContainerId {
  if (!hasVpc) return "region";
  if (!VPC_RESIDENT.has(kind)) return "region";
  return PUBLIC_SUBNET.has(kind) ? "subnet-public" : "subnet-private";
}

/**
 * Build the three-plane graph model from a priced topology.
 *
 * Pure and deterministic: the same topology always yields the same model, so
 * the layout harness can assert on it and two identical tiers producing an
 * identical model is a real signal (the tier-spread bug), not noise.
 */
export function buildGraphModel(
  nodes: TopoNode[],
  edges: TopoEdge[]
): GraphModel {
  const present = new Set(nodes.map((n) => n.id));
  const hasVpc = nodes.some((n) => VPC_RESIDENT.has(n.kind));

  // ── plane assignment ──
  const data: PlanedNode[] = [];
  const control: PlanedNode[] = [];
  const account: PlanedNode[] = [];
  for (const n of nodes) {
    const plane = planeOf(n.kind);
    const pn: PlanedNode = { ...n, plane, seq: null };
    if (plane === "account") {
      account.push(pn);
    } else if (plane === "control") {
      control.push(pn);
    } else {
      pn.container = containerFor(n.kind, hasVpc);
      data.push(pn);
    }
  }

  // ── the request spine: sequence the data nodes that lie on it ──
  const dataIds = new Set(data.map((n) => n.id));
  const spine = FLOW_SPINE.filter((k) => dataIds.has(k));
  const seqOf = new Map<string, number>();
  spine.forEach((id, i) => {
    seqOf.set(id, i + 1);
    const node = data.find((n) => n.id === id);
    if (node) node.seq = i + 1;
  });

  // ── data-plane edges ──
  const dataEdges: DataEdge[] = [];
  const seen = new Set<string>();
  const addEdge = (s: string, t: string, label: string, onPath: boolean) => {
    if (!dataIds.has(s) || !dataIds.has(t)) return;
    const key = `${s}->${t}`;
    if (seen.has(key)) return;
    seen.add(key);
    dataEdges.push({
      source: s,
      target: t,
      label,
      onPath,
      seq: onPath ? seqOf.get(t) ?? null : null,
    });
  };
  // spine edges, sequenced
  for (let i = 0; i < spine.length - 1; i++) {
    addEdge(spine[i], spine[i + 1], "", true);
  }
  // branch edges, from the model's own table plus any labelled edge the
  // backend already emitted that we have not covered
  for (const [s, t, label] of BRANCH_EDGES) addEdge(s, t, label, false);
  for (const e of edges) {
    if (dataIds.has(e.source) && dataIds.has(e.target)) {
      addEdge(e.source, e.target, e.label, false);
    }
  }

  // ── control attachments: one dotted line each, to a present data node ──
  const attachments: Array<{ source: string; target: string }> = [];
  const keptControl: PlanedNode[] = [];
  for (const c of control) {
    const targets = CONTROL_TARGETS[c.kind] ?? [];
    const target = targets.find((t) => dataIds.has(t));
    if (target && present.has(target)) {
      c.attachedTo = target;
      attachments.push({ source: c.id, target });
      keptControl.push(c);
    }
    // A control service with nothing present to serve is dropped rather than
    // drawn floating — the exact orphan the rebuild exists to remove.
  }

  return {
    data,
    control: keptControl,
    account,
    dataEdges,
    attachments,
    hasVpc,
  };
}
