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
import { layout, type Layout, type LaidNode } from "@/lib/elkLayout";
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
};

function containerStyle(kind: string): ContainerStyle {
  if (kind.startsWith("az-")) return CONTAINER_STYLE.az;
  if (kind.startsWith("subnet-public")) return CONTAINER_STYLE["subnet-public"];
  if (kind.startsWith("subnet-app")) return CONTAINER_STYLE["subnet-app"];
  if (kind.startsWith("subnet-data")) return CONTAINER_STYLE["subnet-data"];
  return CONTAINER_STYLE[kind] ?? CONTAINER_STYLE.cloud;
}

function ContainerNode({ data }: NodeProps) {
  const d = data as { label: string; kind: string; w: number; h: number };
  const st = containerStyle(d.kind);
  const locked = d.kind.startsWith("subnet-");
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
        className="absolute flex items-center gap-1 whitespace-nowrap rounded-[2px] px-1.5 text-[12px] font-semibold leading-[18px]"
        style={{ left: 10, top: -10, background: "#FFFFFF", color: st.ink }}
      >
        {locked && (
          <svg width="9" height="11" viewBox="0 0 9 11" aria-hidden>
            <path
              d="M2 4V3a2.5 2.5 0 015 0v1"
              fill="none"
              stroke={st.ink}
              strokeWidth="1.2"
            />
            <rect x="1" y="4" width="7" height="6" rx="1" fill={st.ink} />
          </svg>
        )}
        {d.label}
      </span>
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
  onPaneClick,
}: {
  nodes: TopoNode[];
  edges: TopoEdge[];
  playing: boolean;
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
    layout(model)
      .then((res) => alive && setLaid(res))
      .catch((err) => console.error("[graph] layout failed", err));
    return () => {
      alive = false;
    };
  }, [topoNodes, topoEdges]);

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

  // Fit once the nodes are actually in the store and measured. Running this on
  // rAF at mount fit an empty graph; a short settle after the node set changes
  // frames the whole diagram reliably.
  useEffect(() => {
    if (!rfNodes.length) return;
    // Fit after the container/service nodes have measured. Two settles: the
    // first frames the graph, the second corrects once large container boxes
    // have reported their size so the whole height (account band included) fits.
    const fit = () =>
      rf.fitView({ padding: 0.12, duration: 400, maxZoom: 1.2, minZoom: 0.15 });
    // Three settles, not two. The layout now runs ELK twice (once per
    // direction) before nodes exist, and container boxes report their size a
    // frame after that -- so a fit at 160ms framed an empty graph and a fit at
    // 520ms framed a partly-measured one. The last settle is what the full-page
    // overlay actually lands on, and it has to outlast both layouts.
    const t1 = setTimeout(fit, 200);
    const t2 = setTimeout(fit, 700);
    const t3 = setTimeout(fit, 1400);
    // Re-fit whenever THIS instance's container changes size -- which is how
    // the full-page overlay gets fitted correctly. Two instances are mounted
    // (collapsed pane and overlay), so a document-wide querySelector matched
    // the collapsed one and the overlay fitted to a stale size, opening
    // zoomed in with the diagram running off the edge. Scope it to our own
    // element via a ref, and let the observer -- not a fixed timeout -- be
    // what tells us the surface has finished resizing.
    let raf = 0;
    const ro = new ResizeObserver(() => {
      window.clearTimeout(raf);
      raf = window.setTimeout(fit, 150);
    });
    if (hostRef.current) ro.observe(hostRef.current);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      window.clearTimeout(raf);
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
      fitViewOptions={{ padding: 0.12 }}
      minZoom={0.1}
      maxZoom={2.5}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable
      onPaneClick={onPaneClick}
      // onInit fires once React Flow has measured its own container, which is
      // the only moment we can be sure the surface has real dimensions. The
      // timer-based settles were firing against a container React Flow had not
      // measured yet, so the overlay opened at whatever zoom the instance
      // started with instead of a fitted one.
      onInit={(inst) => {
        window.setTimeout(
          () => inst.fitView({ padding: 0.1, maxZoom: 1.2, minZoom: 0.05 }),
          400
        );
        window.setTimeout(
          () => inst.fitView({ padding: 0.1, maxZoom: 1.2, minZoom: 0.05 }),
          1200
        );
      }}
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
  /** Rendered at the top of the overlay so tiers can be compared without
   *  leaving full-page view. */
  overlayHeader?: React.ReactNode;
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
    <ReactFlowProvider>
      <Inner
        nodes={props.nodes}
        edges={props.edges}
        playing={props.playing ?? true}
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

      {!expanded && (
        <div className="pointer-events-none absolute bottom-3 right-3 rounded-md border border-line bg-surface/95 px-2 py-1 text-[11px] font-medium text-ink-3 opacity-0 shadow-sm transition-opacity group-hover:opacity-100">
          Click to expand
        </div>
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
          <div className="h-full w-full" key="overlay-graph">{graph(true)}</div>
        </div>
      )}
    </div>
  );
}
