"use client";

import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  MiniMap,
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

/* ── container background box ── */
function ContainerNode({ data }: NodeProps) {
  const d = data as { label: string; kind: string; w: number; h: number };
  const vpc = d.kind === "vpc";
  const az = d.kind === "az" || d.kind.startsWith("az-");
  const subnetPublic = d.kind.startsWith("subnet-public");
  const subnetPrivate = d.kind.startsWith("subnet-app") || d.kind.startsWith("subnet-data");
  const regional = d.kind === "regional";
  const edge = d.kind === "edge";
  const border = vpc
    ? "border-emerald-500/60"
    : az
    ? "border-sky-400/50 border-dashed"
    : subnetPublic
    ? "border-teal-400/40 border-dashed"
    : subnetPrivate
    ? "border-indigo-400/40 border-dashed"
    : regional
    ? "border-violet-400/45 border-dashed"
    : edge
    ? "border-amber-400/50 border-dashed"
    : "border-line-strong";
  const tint = subnetPublic
    ? "bg-teal-400/[0.04]"
    : subnetPrivate
    ? "bg-indigo-400/[0.05]"
    : regional
    ? "bg-violet-400/[0.05]"
    : edge
    ? "bg-amber-400/[0.06]"
    : vpc
    ? "bg-emerald-500/[0.02]"
    : "bg-black/[0.02]";
  return (
    <div
      className={`rounded-lg border ${border} ${tint}`}
      style={{ width: d.w, height: d.h }}
    >
      <span
        className={`absolute left-2 top-1.5 rounded bg-surface/85 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide shadow-sm ring-1 ring-black/5 ${
          vpc ? "text-emerald-600" : az ? "text-sky-600" : subnetPublic ? "text-teal-600" : subnetPrivate ? "text-indigo-500" : regional ? "text-violet-500" : edge ? "text-amber-600" : "text-ink-3"
        }`}
      >
        {d.label}
      </span>
    </div>
  );
}

/* ── a data-plane service node: icon, name, role, cost ── */
function ServiceNode({ data }: NodeProps) {
  const d = data as unknown as LaidNode & { accent: boolean };
  const icon = serviceIconPath(d.kind);
  return (
    <div
      className={`group relative flex h-full w-full items-center gap-2.5 rounded-xl border bg-surface px-2.5 py-2 shadow-sm ${
        d.accent ? "border-accent/70 ring-1 ring-accent/25" : "border-line-strong"
      } ${!d.priced ? "border-dashed opacity-70" : ""}`}
    >
      <Handle type="target" position={Position.Top} className="!opacity-0" />
      <Handle type="source" position={Position.Bottom} className="!opacity-0" />
      <div className="grid h-11 w-11 shrink-0 place-items-center rounded-lg bg-sunk">
        {icon ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={icon} alt="" className="h-9 w-9 object-contain" />
        ) : d.kind === "client" ? (
          <Icon icon="mdi:account-group" className="h-7 w-7 text-ink-2" />
        ) : (
          <Icon icon="mdi:cube-outline" className="h-7 w-7 text-ink-3" />
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="text-[12px] font-semibold leading-tight text-ink" style={{ display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
          {d.label}
        </div>
        <div className="truncate text-[10px] leading-tight text-ink-3" title={d.detail || roleFor(d.kind)}>
          {roleFor(d.kind)}
        </div>
      </div>
      <div className="shrink-0 self-start rounded-md bg-sunk px-1.5 py-0.5 font-mono text-[10.5px] font-semibold tabular-nums text-ink-2">
        {money(d.monthly_usd)}
      </div>
      {d.seq != null && (
        <div className="absolute -left-2.5 -top-2.5 grid h-5 w-5 place-items-center rounded-full bg-accent text-[10.5px] font-bold text-white shadow ring-2 ring-surface">
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
  const showLabel = Boolean(d.label) && routeLength < 420;

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
  if (!d.onPath && !d.attach && routeLength > 240) return null;
  const animate = d.onPath && d.playing && !d.reduced;
  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        markerEnd={d.attach ? undefined : markerEnd}
        style={{
          stroke: d.attach ? "#94A3B8" : d.onPath ? "#2563EB" : "#8896A6",
          strokeWidth: d.onPath ? 2 : 1.5,
          strokeDasharray: d.attach ? "3 4" : undefined,
          fill: "none",
        }}
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
}: {
  nodes: TopoNode[];
  edges: TopoEdge[];
  playing: boolean;
}) {
  const [laid, setLaid] = useState<Layout | null>(null);
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
      // ELK reports an edge's sections relative to whichever container holds
      // the edge, and with INCLUDE_CHILDREN a cross-container edge can come
      // back in a different origin than the one we add the container offset
      // for. The result is geometry that touches neither box -- the stray blue
      // arrows floating above the edge cluster. Moving the points instead
      // (snapping them to node centres) just traded them for long diagonals,
      // so an edge whose route does not reach either of its own boxes is not
      // drawn at all.
      .filter(
        (e) =>
          touches(e.points[0], e.source) ||
          touches(e.points[e.points.length - 1], e.target)
      )
      .map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      type: "poly",
      data: { points: e.points, label: e.label, onPath: e.onPath, attach: e.attach, playing, reduced },
      markerEnd: e.attach
        ? undefined
        : { type: "arrowclosed" as any, color: e.onPath ? "#2563EB" : "#8896A6", width: 16, height: 16 },
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
    const t1 = setTimeout(() => rf.fitView({ padding: 0.12, duration: 200 }), 160);
    const t2 = setTimeout(() => rf.fitView({ padding: 0.12, duration: 200 }), 520);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
    };
  }, [rfNodes, rf]);

  return (
    <ReactFlow
      nodes={rfNodes}
      edges={rfEdges}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      fitView
      fitViewOptions={{ padding: 0.12 }}
      minZoom={0.2}
      maxZoom={2}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable
      proOptions={{ hideAttribution: true }}
      className="bg-sunk"
    >
      <Background gap={22} size={1} color="var(--line, #e5e7eb)" />
      <Controls showInteractive={false} />
      <MiniMap
        pannable
        zoomable
        nodeStrokeWidth={2}
        nodeColor={(n) =>
          n.type === "container"
            ? "#E2E8F0"
            : (n.data as any)?.seq != null
            ? "#2563EB"
            : "#94A3B8"
        }
        maskColor="rgba(148,163,184,0.18)"
        className="!bg-surface"
      />
    </ReactFlow>
  );
}

export function ArchitectureGraph(props: {
  nodes: TopoNode[];
  edges: TopoEdge[];
  playing?: boolean;
}) {
  return (
    <div className="h-full w-full">
      <style>{`@keyframes wc-flow { to { stroke-dashoffset: -226; } }`}</style>
      <ReactFlowProvider>
        <Inner nodes={props.nodes} edges={props.edges} playing={props.playing ?? true} />
      </ReactFlowProvider>
    </div>
  );
}
