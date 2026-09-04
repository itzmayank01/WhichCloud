"use client";

import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  Handle,
  Position,
  BaseEdge,
  EdgeLabelRenderer,
  useReactFlow,
  type Node as RFNode,
  type Edge as RFEdge,
  type EdgeProps,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Icon } from "@iconify/react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { Node as TopoNode, Edge as TopoEdge } from "@/lib/api";
import { buildGraphModel } from "@/lib/graphModel";
import { layout, type CloudId, type Layout, type LaidNode } from "@/lib/elkLayout";
import { iconFor } from "@/lib/serviceIcon";
import { KIND_ICON_LABEL, roleFor } from "@/lib/serviceMeta";

const money = (v: number) =>
  v >= 1000 ? `$${(v / 1000).toFixed(1)}k` : v >= 1 ? `$${v.toFixed(0)}` : v > 0 ? `$${v.toFixed(2)}` : "—";

function serviceIconPath(kind: string): string | null {
  const label = KIND_ICON_LABEL[kind];
  return label ? iconFor(label) : null;
}

/* ── container background box ──
 *
 * AWS reference-architecture styling: every container fill is WHITE and the
 * structure is carried entirely by border colour, weight and dash pattern.
 * Stacked translucent tints were what muddied the previous version -- three
 * washes over each other turn every boundary into another shade of grey.
 *
 * Border weight descends with depth so the nesting reads without labels:
 *   VPC 2px solid > AWS Cloud 1.5px solid > AZ 1.5px dashed > subnet 1.5px
 *   solid > node 1px solid.
 * The subnet is the only level allowed a tint, and only at 4-6%.
 */
type ContainerStyle = {
  border: string;
  dash?: string;
  width: number;
  fill: string;
  ink: string;
};

const CONTAINER_STYLE: Record<string, ContainerStyle> = {
  cloud:    { border: "#232F3E", width: 1.5, fill: "#FFFFFF", ink: "#232F3E" },
  // #00A4A6 fails 4.5:1 on white, so the darker #007F80 is used for the text
  // while the border keeps the lighter teal.
  region:   { border: "#00A4A6", width: 1.5, dash: "6 4", fill: "#FFFFFF", ink: "#007F80" },
  vpc:      { border: "#248814", width: 2,   fill: "#FFFFFF", ink: "#248814" },
  az:       { border: "#147EBA", width: 1.5, dash: "5 4", fill: "#FFFFFF", ink: "#147EBA" },
  "subnet-public": { border: "#248814", width: 1.5, fill: "#F5FBF5", ink: "#248814" },
  "subnet-app":    { border: "#147EBA", width: 1.5, fill: "#F6FAFD", ink: "#147EBA" },
  "subnet-data":   { border: "#3B48CC", width: 1.5, fill: "#F7F8FD", ink: "#3B48CC" },
  edge:     { border: "#8C4FFF", width: 1.5, dash: "6 4", fill: "#FFFFFF", ink: "#8C4FFF" },
  regional: { border: "#232F3E", width: 1.5, dash: "6 4", fill: "#FFFFFF", ink: "#232F3E" },
  "routetable-public": { border: "#7AA116", width: 1.5, fill: "#FFFFFF", ink: "#5B7A10" },
  "routetable-private": { border: "#00A4A6", width: 1.5, fill: "#FFFFFF", ink: "#007F80" },
};

function containerStyle(kind: string): ContainerStyle {
  if (kind.startsWith("az-")) return CONTAINER_STYLE.az;
  if (kind.startsWith("subnet-public")) return CONTAINER_STYLE["subnet-public"];
  if (kind.startsWith("subnet-app")) return CONTAINER_STYLE["subnet-app"];
  if (kind.startsWith("subnet-data")) return CONTAINER_STYLE["subnet-data"];
  return CONTAINER_STYLE[kind] ?? CONTAINER_STYLE.cloud;
}

/* Container badges, the way the AWS reference diagrams mark a boundary: a
   small filled square carrying a white glyph, sitting to the left of the
   label. The glyph is what tells you at a glance whether a box is the account,
   a region, a zone, the VPC or a subnet -- colour alone does not, especially
   for the two subnet tiers that share a family of blues. */
function badgeFor(kind: string): { bg: string; glyph: React.ReactNode } | null {
  const lock = (
    <>
      <path d="M4.5 7.5V6a2 2 0 014 0v1.5" fill="none" stroke="#FFF" strokeWidth="1.3" />
      <rect x="3.4" y="7.4" width="6.2" height="5" rx="1" fill="#FFF" />
    </>
  );
  if (kind === "cloud") return { bg: "#232F3E", glyph: "aws" };
  if (kind === "region")
    return {
      // Flag on a pole -- the reference's region marker.
      bg: "#00A4A6",
      glyph: (
        <>
          <path d="M4 3v9" stroke="#FFF" strokeWidth="1.3" strokeLinecap="round" />
          <path d="M4.8 3.6h5l-1.4 2 1.4 2h-5z" fill="#FFF" />
        </>
      ),
    };
  if (kind.startsWith("az-"))
    return {
      // Location pin -- a zone is a place.
      bg: "#147EBA",
      glyph: (
        <>
          <path d="M6.5 2.6c1.9 0 3.4 1.5 3.4 3.4 0 2.4-3.4 6-3.4 6S3.1 8.4 3.1 6c0-1.9 1.5-3.4 3.4-3.4z" fill="#FFF" />
          <circle cx="6.5" cy="5.9" r="1.2" fill="#147EBA" />
        </>
      ),
    };
  if (kind === "vpc")
    return {
      bg: "#8C4FFF",
      glyph: (
        <>
          <rect x="2.6" y="2.6" width="7.8" height="7.8" rx="1" fill="none" stroke="#FFF" strokeWidth="1.3" />
          <path d="M6.5 4.4v4.2M4.6 6.5h3.8" stroke="#FFF" strokeWidth="1.1" />
        </>
      ),
    };
  if (kind.startsWith("routetable-")) {
    const bg = kind.endsWith("public") ? "#7AA116" : "#00A4A6";
    return {
      bg,
      glyph: (
        <>
          <rect x="2.4" y="3" width="8.2" height="7" rx="1" fill="none" stroke="#FFF" strokeWidth="1.2" />
          <path d="M2.4 5.3h8.2M5.6 5.3V10" stroke="#FFF" strokeWidth="1.1" />
        </>
      ),
    };
  }
  if (kind.startsWith("subnet-public")) return { bg: "#7AA116", glyph: lock };
  if (kind.startsWith("subnet-")) return { bg: "#00A4A6", glyph: lock };
  if (kind === "edge")
    return {
      bg: "#8C4FFF",
      glyph: (
        <>
          <circle cx="6.5" cy="6.5" r="4" fill="none" stroke="#FFF" strokeWidth="1.3" />
          <path d="M2.5 6.5h8M6.5 2.5c1.8 2.3 1.8 5.7 0 8M6.5 2.5c-1.8 2.3-1.8 5.7 0 8" fill="none" stroke="#FFF" strokeWidth="1" />
        </>
      ),
    };
  if (kind === "regional")
    return {
      bg: "#232F3E",
      glyph: (
        <>
          <path d="M6.5 2.4l3.8 2.1v4.2L6.5 10.8 2.7 8.7V4.5z" fill="none" stroke="#FFF" strokeWidth="1.2" />
          <path d="M2.7 4.5l3.8 2.1 3.8-2.1M6.5 6.6v4.2" fill="none" stroke="#FFF" strokeWidth="1.1" />
        </>
      ),
    };
  return null;
}

function ContainerBadge({ kind }: { kind: string }) {
  const b = badgeFor(kind);
  if (!b) return null;
  // The AWS wordmark is set as text; every other badge is a glyph.
  if (b.glyph === "aws")
    return (
      <span
        className="grid h-[18px] w-[22px] shrink-0 place-items-center rounded-[2px] text-[8px] font-bold lowercase leading-none tracking-tight text-white"
        style={{ background: b.bg }}
      >
        aws
      </span>
    );
  return (
    <span
      className="grid h-[18px] w-[18px] shrink-0 place-items-center rounded-[2px]"
      style={{ background: b.bg }}
    >
      <svg width="13" height="13" viewBox="0 0 13 13" aria-hidden>
        {b.glyph}
      </svg>
    </span>
  );
}

/* Destination -> target, the two rows every VPC route table really has: the
   local CIDR, and the default route out. Which gateway the default route uses
   is the actual difference between a public and a private subnet, so it is
   worth showing rather than implying. */
const ROUTE_ROWS: Record<string, Array<[string, string]>> = {
  "routetable-public": [
    ["10.0.0.0/16", "local"],
    ["0.0.0.0/0", "igw"],
  ],
  "routetable-private": [
    ["10.0.0.0/16", "local"],
    ["0.0.0.0/0", "nat"],
  ],
};

function ContainerNode({ data }: NodeProps) {
  const d = data as { label: string; kind: string; w: number; h: number };
  const st = containerStyle(d.kind);
  const routes = ROUTE_ROWS[d.kind];
  return (
    <div
      style={{
        width: d.w,
        height: d.h,
        background: st.fill,
        border: `${st.width}px ${st.dash ? "dashed" : "solid"} ${st.border}`,
        borderRadius: 2,
      }}
    >
      {/* Label on a white chip so the container's own border never strikes
          through its text. Sentence case, never centred, never all-caps. */}
      <span
        className="absolute flex items-center gap-1.5 whitespace-nowrap rounded-[2px] pr-1.5 text-[12px] font-semibold leading-[18px]"
        style={{ left: 8, top: -10, background: "#FFFFFF", color: st.ink }}
      >
        <ContainerBadge kind={d.kind} />
        {d.label}
      </span>
      {routes && (
        <div className="flex h-full flex-col justify-center gap-0.5 px-2 pt-2">
          {routes.map(([dest, via]) => (
            <div key={dest} className="flex items-center justify-between gap-2">
              <span className="font-mono text-[9.5px] text-ink-2">{dest}</span>
              <span className="font-mono text-[9.5px] text-ink-3">{via}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── a data-plane service node: icon, name, role, cost ── */
function ServiceNode({ data }: NodeProps) {
  const d = data as unknown as LaidNode & { accent: boolean };
  const icon = serviceIconPath(d.kind);
  // AWS reference styling: a hairline #D5DBDB box, 2px corners, NO shadow.
  // The rounded-xl card with a drop shadow read as a web UI component rather
  // than a diagram symbol -- twenty of them stacked looked like a dashboard,
  // not an architecture. The reference diagrams keep the box nearly invisible
  // so the icon and the name carry the meaning.
  return (
    <div
      className={`group relative flex h-full w-full items-center gap-2.5 border bg-white px-2.5 py-2 ${
        !d.priced ? "border-dashed opacity-70" : ""
      }`}
      style={{
        borderRadius: 2,
        borderColor: d.accent ? "#0972D3" : "#D5DBDB",
        boxShadow: d.accent ? "0 0 0 1px #0972D3" : "none",
      }}
    >
      <Handle type="target" position={Position.Top} className="!opacity-0" />
      <Handle type="source" position={Position.Bottom} className="!opacity-0" />
      <div className="grid h-9 w-9 shrink-0 place-items-center">
        {icon ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={icon} alt="" className="h-8 w-8 object-contain" />
        ) : d.kind === "client" ? (
          <Icon icon="mdi:account-group" className="h-6 w-6 text-ink-2" />
        ) : (
          <Icon icon="mdi:cube-outline" className="h-6 w-6 text-ink-3" />
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="text-[11.5px] font-semibold leading-tight text-ink" style={{ display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
          {d.label}
        </div>
        {/* Italic descriptor -- the reference diagrams set the role line in
            italic so it reads as a gloss on the service name, not a second
            name competing with it. */}
        <div className="truncate text-[10px] italic leading-tight text-ink-3" title={d.detail || roleFor(d.kind)}>
          {roleFor(d.kind)}
        </div>
      </div>
      {/* The price sits ON the top-right corner rather than in a column of
          its own. At 168px wide a price column left about sixty pixels for
          the service name, which clamped "Application load balancer" into an
          unreadable stack. */}
      {d.priced && (
        <div
          className="absolute -top-2 right-1 rounded-[2px] border bg-white px-1 font-mono text-[10px] font-semibold tabular-nums text-ink-2"
          style={{ borderColor: "#D5DBDB" }}
        >
          {money(d.monthly_usd)}
        </div>
      )}
      {d.seq != null && (
        <div
          className="absolute -left-2.5 -top-2.5 grid h-5 w-5 place-items-center rounded-full text-[10.5px] font-bold text-white"
          style={{ background: "#232F3E", boxShadow: "0 0 0 2px #FFFFFF" }}
        >
          {d.seq}
        </div>
      )}
    </div>
  );
}

/* ── a control-plane node: smaller, dotted-attached ── */
function ControlNode({ data }: NodeProps) {
  const d = data as unknown as LaidNode;
  const icon = serviceIconPath(d.kind);
  return (
    <div className="relative flex h-full w-full items-center gap-1.5 rounded-lg border border-dashed border-line-strong bg-surface/90 px-2 py-1">
      <Handle type="target" position={Position.Left} className="!opacity-0" />
      <Handle type="source" position={Position.Right} className="!opacity-0" />
      {icon ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={icon} alt="" className="h-5 w-5 shrink-0 object-contain" />
      ) : (
        <Icon icon="mdi:cog-outline" className="h-4 w-4 shrink-0 text-ink-3" />
      )}
      <div className="min-w-0">
        <div className="truncate text-[10.5px] font-medium leading-tight text-ink-2">{d.label}</div>
        <div className="truncate text-[9px] leading-tight text-ink-3">{roleFor(d.kind)}</div>
      </div>
    </div>
  );
}

/* ── an account-plane chip: lives in the band, never wired ── */
function AccountNode({ data }: NodeProps) {
  const d = data as unknown as LaidNode;
  const icon = serviceIconPath(d.kind);
  return (
    <div className="flex h-full w-full items-center gap-1.5 rounded-md border border-line bg-sunk/60 px-2">
      {icon ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={icon} alt="" className="h-5 w-5 shrink-0 object-contain opacity-90" />
      ) : (
        <Icon icon="mdi:eye-outline" className="h-4 w-4 shrink-0 text-ink-3" />
      )}
      <div className="min-w-0">
        <div className="truncate text-[10px] font-medium leading-tight text-ink-2">{d.label}</div>
        <div className="truncate text-[9px] leading-tight text-ink-3">{roleFor(d.kind)}</div>
      </div>
    </div>
  );
}

/* The ONLY fit options in this file. Every fit -- the one React Flow runs on
   mount and the one the resize observer runs -- uses these, so no two fits can
   land the diagram at different zooms. Padding is tight because the pane is
   already a small share of the workspace and margin is the one thing it cannot
   afford. No duration: an animated fit that gets superseded reads as the
   diagram lurching about. */
const FIT_OPTS = { padding: 0.06, maxZoom: 1.4, minZoom: 0.04 } as const;

/* Edge ink, by what the edge means. Four weights, straight off the AWS
   reference diagrams: the live request path is the darkest and heaviest
   because it IS the architecture; a branch call is the same grey but lighter;
   replication is dashed because it happens continuously in the background;
   and governance attachments are the palest thing on the canvas, present so
   you can see what KMS protects without competing with the traffic. */
function EDGE_STYLE(e: { attach: boolean; onPath: boolean; kind?: string }): {
  stroke: string;
  strokeWidth: number;
  strokeDasharray?: string;
} {
  if (e.attach) return { stroke: "#C8CCCC", strokeWidth: 1, strokeDasharray: "3 4" };
  if (e.kind === "replication")
    return { stroke: "#879596", strokeWidth: 1.5, strokeDasharray: "6 4" };
  if (e.onPath) return { stroke: "#545B64", strokeWidth: 2 };
  return { stroke: "#879596", strokeWidth: 1.5 };
}

/* Build an orthogonal SVG path with softly rounded corners from ELK points. */
function roundedPath(pts: Array<{ x: number; y: number }>, r = 8): string {
  if (pts.length < 2) return "";
  if (pts.length === 2) return `M${pts[0].x},${pts[0].y} L${pts[1].x},${pts[1].y}`;
  let d = `M${pts[0].x},${pts[0].y}`;
  for (let i = 1; i < pts.length - 1; i++) {
    const p = pts[i];
    const prev = pts[i - 1];
    const next = pts[i + 1];
    const v1 = norm(p.x - prev.x, p.y - prev.y);
    const v2 = norm(next.x - p.x, next.y - p.y);
    const rr = Math.min(r, dist(prev, p) / 2, dist(p, next) / 2);
    d += ` L${p.x - v1.x * rr},${p.y - v1.y * rr}`;
    d += ` Q${p.x},${p.y} ${p.x + v2.x * rr},${p.y + v2.y * rr}`;
  }
  const last = pts[pts.length - 1];
  d += ` L${last.x},${last.y}`;
  return d;
}
const dist = (a: { x: number; y: number }, b: { x: number; y: number }) =>
  Math.hypot(a.x - b.x, a.y - b.y);
function norm(x: number, y: number) {
  const m = Math.hypot(x, y) || 1;
  return { x: x / m, y: y / m };
}
/** midpoint of the longest straight segment — where a label sits clear of corners. */
function labelAnchor(pts: Array<{ x: number; y: number }>) {
  let best = 0;
  let anchor = pts[Math.floor(pts.length / 2)] ?? { x: 0, y: 0 };
  for (let i = 0; i < pts.length - 1; i++) {
    const len = dist(pts[i], pts[i + 1]);
    if (len > best) {
      best = len;
      anchor = { x: (pts[i].x + pts[i + 1].x) / 2, y: (pts[i].y + pts[i + 1].y) / 2 };
    }
  }
  return anchor;
}

function PolyEdge({ id, data, markerEnd }: EdgeProps) {
  const d = data as {
    points: Array<{ x: number; y: number }>;
    label: string;
    onPath: boolean;
    attach: boolean;
    playing: boolean;
    reduced: boolean;
  };
  const path = roundedPath(d.points, d.attach ? 0 : 8);
  const anchor = labelAnchor(d.points);
  // A label only helps where it lands NEAR the things it describes. On a
  // long-haul route -- CDN reaching object storage, the app reaching the
  // stream -- ELK parks the midpoint out in open canvas, and a dozen of those
  // become a band of stray words with nothing to attach them to. Measure the
  // routed length and drop the label past the point where it stops being
  // legible in context; the edge itself still draws.
  const routeLength = d.points.reduce(
    (sum, pt, i) =>
      i === 0 ? 0 : sum + Math.hypot(pt.x - d.points[i - 1].x, pt.y - d.points[i - 1].y),
    0
  );
  const showLabel = Boolean(d.label) && routeLength < 900;

  // A branch edge that has to cross the whole canvas costs more than it tells
  // you. These are real relationships -- the CDN reaching object storage, the
  // app reaching the cache in another tier -- but ELK routes them around every
  // container in the way, and half a dozen produce the sweeping arcs that made
  // the picture unreadable. The request spine is always drawn (it IS the
  // architecture), and so are the short dotted control attachments; only the
  // long-haul branches are dropped.
  // Threshold was 520, which still let two branches through that ELK had
  // routed into open canvas above the edge cluster -- arrows starting and
  // ending in empty space. Branch edges only earn their ink when they stay
  // local, so the bar is now short-and-local or not drawn at all. The request
  // spine (numbered, always drawn) carries the architecture, and the dotted
  // control attachments still tie KMS and Secrets to what they protect;
  // everything a branch edge would have said is in the cost table beside it.
  // No length cap any more. The stray arrows had two real causes -- the
  // tier-ordering chain reaching the renderer, and edge geometry reported in
  // the wrong origin -- and both are fixed at source now. Capping length as
  // well threw away the connections that let a reader follow the architecture,
  // which is the whole point of drawing edges.
  const animate = d.onPath && d.playing && !d.reduced;
  return (
    <>
      {/* A white casing under every line. Where two edges cross, or a line
          passes close to a box border, the casing breaks the one behind so the
          two still read as separate paths -- the standard trick on transit
          maps and AWS reference diagrams alike. Without it, crossings fuse
          into a single ambiguous mark. */}
      <path
        d={path}
        fill="none"
        stroke="#FFFFFF"
        strokeWidth={EDGE_STYLE(d).strokeWidth + 3.5}
        strokeLinecap="round"
      />
      <BaseEdge
        id={id}
        path={path}
        markerEnd={d.attach ? undefined : markerEnd}
        style={{ ...EDGE_STYLE(d), fill: "none" }}
      />
      {animate && (
        <path
          d={path}
          fill="none"
          stroke="#60A5FA"
          strokeWidth={2.5}
          strokeLinecap="round"
          strokeDasharray="6 220"
          style={{ animation: "wc-flow 2.2s linear infinite" }}
        />
      )}
      {showLabel && (
        <EdgeLabelRenderer>
          <div
            className="nodrag nopan pointer-events-none absolute -translate-x-1/2 -translate-y-1/2 rounded bg-surface/95 px-1.5 py-px text-[9.5px] font-medium text-ink-3 shadow-sm ring-1 ring-line"
            style={{ left: anchor.x, top: anchor.y }}
          >
            {d.label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

const nodeTypes = {
  container: ContainerNode,
  service: ServiceNode,
  control: ControlNode,
  account: AccountNode,
};
const edgeTypes = { poly: PolyEdge };

function Inner({
  nodes: topoNodes,
  edges: topoEdges,
  playing,
  cloud,
  onPaneClick,
}: {
  nodes: TopoNode[];
  edges: TopoEdge[];
  playing: boolean;
  cloud: CloudId;
  onPaneClick?: () => void;
}) {
  const [laid, setLaid] = useState<Layout | null>(null);
  const hostRef = useRef<HTMLDivElement | null>(null);
  const rf = useReactFlow();
  const reduced =
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  useEffect(() => {
    let alive = true;
    const model = buildGraphModel(topoNodes, topoEdges);
    layout(model, cloud)
      .then((res) => alive && setLaid(res))
      .catch((err) => console.error("[graph] layout failed", err));
    return () => {
      alive = false;
    };
  }, [topoNodes, topoEdges, cloud]);

  const { rfNodes, rfEdges } = useMemo(() => {
    if (!laid) return { rfNodes: [] as RFNode[], rfEdges: [] as RFEdge[] };
    const rfNodes: RFNode[] = [];
    // containers first (drawn beneath), then service/control/account on top
    for (const c of laid.containers) {
      rfNodes.push({
        id: `c:${c.id}`,
        type: "container",
        position: { x: c.x, y: c.y },
        data: { label: c.label, kind: c.kind, w: c.w, h: c.h },
        draggable: false,
        selectable: false,
        zIndex: 0,
        style: { width: c.w, height: c.h },
      });
    }
    for (const n of laid.nodes) {
      rfNodes.push({
        id: n.id,
        type: n.plane === "data" ? "service" : n.plane === "control" ? "control" : "account",
        position: { x: n.x, y: n.y },
        data: { ...n, accent: n.seq != null },
        draggable: false,
        selectable: true,
        zIndex: 10,
        style: { width: n.w, height: n.h },
      });
    }
    // An edge is only drawable if BOTH ends are boxes actually on the canvas.
    // Anything else routes from wherever ELK last had a coordinate and renders
    // as an arrow hanging in open space with nothing at either end -- which is
    // exactly the stray blue arrows above the edge cluster. Rather than keep
    // chasing which producer emits them, refuse to draw an edge that cannot
    // point at two real nodes.
    const drawable = new Set(laid.nodes.map((n) => n.id));
    const boxOf = new Map(laid.nodes.map((n) => [n.id, n]));
    /** Does this endpoint actually sit on the box it claims to come from? */
    const touches = (pt: { x: number; y: number } | undefined, id: string) => {
      const b = boxOf.get(id);
      if (!pt || !b) return false;
      const dx = Math.max(b.x - pt.x, 0, pt.x - (b.x + b.w));
      const dy = Math.max(b.y - pt.y, 0, pt.y - (b.y + b.h));
      return Math.hypot(dx, dy) <= 64;
    };
    const rfEdges: RFEdge[] = laid.edges
      .filter((e) => drawable.has(e.source) && drawable.has(e.target))
      .map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      type: "poly",
      data: { points: e.points, label: e.label, onPath: e.onPath, attach: e.attach, playing, reduced },
      markerEnd: e.attach
        ? undefined
        : {
            type: "arrowclosed" as any,
            color: EDGE_STYLE(e).stroke,
            width: 16,
            height: 16,
          },
      zIndex: e.attach ? 4 : 5,
    }));
    return { rfNodes, rfEdges };
  }, [laid, playing, reduced]);

  // ONE fit path, one set of options. There used to be six -- the fitView
  // prop, two onInit timers, three settle timers and a ResizeObserver -- and
  // they disagreed with each other: padding 0.1 against 0.12, minZoom 0.05
  // against 0.15. Each settled at a different zoom, so opening the diagram set
  // off a second or two of visible zooming in and out as they took turns
  // overriding one another. They also each animated, which restarted the
  // animation mid-flight.
  useEffect(() => {
    if (!rfNodes.length) return;
    const host = hostRef.current;
    if (!host) return;

    let lastSig = "";
    let timer = 0;
    const fit = () => {
      const r = host.getBoundingClientRect();
      // A hidden or not-yet-laid-out surface has no size to fit to; fitting
      // against it is what framed an empty graph and forced the later
      // corrective re-fits that the eye read as flicker.
      if (r.width < 2 || r.height < 2) return;
      // Re-fit only when something that CHANGES the fit changed. Firing on
      // every observer callback let each fit's own animation resize the
      // surface, notify the observer, and start the next one -- a loop that
      // never settled.
      const sig = `${Math.round(r.width)}x${Math.round(r.height)}:${rfNodes.length}`;
      if (sig === lastSig) return;
      lastSig = sig;
      rf.fitView(FIT_OPTS);
    };
    const schedule = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(fit, 120);
    };
    schedule();
    // The observer is what fits the full-page overlay: its host goes from zero
    // to full size on open, which is the only reliable signal that the surface
    // is real and measured.
    const ro = new ResizeObserver(schedule);
    ro.observe(host);
    return () => {
      window.clearTimeout(timer);
      ro.disconnect();
    };
  }, [rfNodes, rf]);

  return (
    <div ref={hostRef} className="h-full w-full">
    <ReactFlow
      nodes={rfNodes}
      edges={rfEdges}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      fitView
      fitViewOptions={FIT_OPTS}
      minZoom={0.1}
      maxZoom={2.5}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable
      onPaneClick={onPaneClick}
      proOptions={{ hideAttribution: true }}
      className="bg-white"
      style={{ cursor: onPaneClick ? "zoom-in" : undefined }}
    >
      <Background gap={20} size={1} color="#F3F4F6" />
      <Controls showInteractive={false} />
    </ReactFlow>
    </div>
  );
}

export function ArchitectureGraph(props: {
  nodes: TopoNode[];
  edges: TopoEdge[];
  playing?: boolean;
  /** Which cloud's boundary names to draw. Each cloud groups differently, so
   *  this is not styling: a GCP VPC is global where an AWS one is regional. */
  cloud?: CloudId;
  /** Rendered at the top of the overlay so tiers can be compared without
   *  leaving full-page view. */
  overlayHeader?: React.ReactNode;
  /** Rendered at the bottom of the overlay: replay, Terraform, service count.
   *  The same controls the pane has, so going full-page gives up nothing. */
  overlayFooter?: React.ReactNode;
  /** Remounts the DIAGRAM when it changes (switching tier, pressing replay) so
   *  the build animation restarts from scratch. It deliberately does NOT key
   *  this component: keying the whole thing tore down the expanded state with
   *  it, so picking a different tier from inside the overlay closed the
   *  overlay instead of redrawing in place. */
  graphKey?: string;
}) {
  const [expanded, setExpanded] = useState(false);

  // Esc closes. Bound on the window rather than the overlay so it works
  // regardless of where focus happens to be after a pan.
  useEffect(() => {
    if (!expanded) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setExpanded(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [expanded]);

  const graph = (inOverlay: boolean) => (
    <ReactFlowProvider key={`${inOverlay ? "overlay" : "pane"}-${props.graphKey ?? ""}`}>
      <Inner
        nodes={props.nodes}
        edges={props.edges}
        playing={props.playing ?? true}
        cloud={props.cloud ?? "aws"}
        onPaneClick={inOverlay ? undefined : () => setExpanded(true)}
      />
    </ReactFlowProvider>
  );

  return (
    <div className="group relative h-full w-full">
      <style>{`@keyframes wc-flow { to { stroke-dashoffset: -226; } }`}</style>

      {/* Only ONE graph is mounted at a time. Keeping the collapsed pane alive
          under the overlay meant two React Flow instances laying out and
          fitting simultaneously; the overlay opened un-fitted because its fit
          was racing a second instance measuring the same content. Unmounting
          the collapsed one also halves the ELK work when expanding. */}
      {!expanded && graph(false)}

      {/* A hint that does nothing when clicked is a trap -- it reads as the
          button for the thing it is describing. It IS that button now. */}
      {!expanded && (
        <button
          type="button"
          onClick={() => setExpanded(true)}
          title="Open the diagram full page"
          className="absolute bottom-3 right-3 z-10 inline-flex items-center gap-1.5 rounded-md border border-line bg-surface/95 px-2 py-1 text-[11px] font-medium text-ink-2 opacity-0 shadow-sm transition-opacity hover:bg-sunk focus-visible:opacity-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent group-hover:opacity-100"
        >
          <Icon icon="mdi:arrow-expand-all" className="h-3.5 w-3.5" />
          Click to expand
        </button>
      )}

      {expanded && (
        <div className="fixed inset-0 z-[100] bg-white" role="dialog" aria-modal="true">
          {props.overlayHeader && (
            <div className="pointer-events-none absolute inset-x-0 top-3 z-10 flex justify-center">
              <div className="pointer-events-auto">{props.overlayHeader}</div>
            </div>
          )}
          <button
            type="button"
            onClick={() => setExpanded(false)}
            aria-label="Close full-page diagram"
            className="absolute right-4 top-4 z-10 grid h-10 w-10 place-items-center rounded-lg border border-line-strong bg-surface text-ink-2 shadow-sm transition-colors hover:bg-sunk focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
          >
            <Icon icon="mdi:close" className="h-5 w-5" />
          </button>
          <div className="h-full w-full">{graph(true)}</div>
          {props.overlayFooter && (
            <div className="pointer-events-none absolute inset-x-0 bottom-0 z-10 flex justify-center p-4">
              <div className="pointer-events-auto">{props.overlayFooter}</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
