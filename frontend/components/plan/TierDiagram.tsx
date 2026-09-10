"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import ELK, { type ElkNode } from "elkjs/lib/elk.bundled.js";
import { money, type Edge, type Node as GraphNode } from "@/lib/api";

/**
 * One tier's architecture, laid out by elkjs.
 *
 * THREE PLANES, DRAWN AS THREE DIFFERENT THINGS. That is the whole
 * design, and it is a graph-model decision this component only renders:
 *
 *   data     what a request flows through — boxes in a layered column,
 *            joined by orthogonal arrows, and the only plane animated
 *   control  bound to ONE data-plane node (the key that encrypts that
 *            database) — a dashed attachment, not an arrow, because a
 *            request does not travel through a key
 *   account  watches the whole account and belongs to no node — a
 *            labelled band with no edges at all, because any edge drawn
 *            from CloudTrail to the database would be invented
 *
 * The old renderer had one plane, so eleven of nineteen nodes on a
 * hospital tier-2 had no edge and fell into a disconnected row at the
 * bottom. That row was not a layout failure; it was three kinds of thing
 * drawn as one kind.
 *
 * NO HAND PLACEMENT. Every coordinate below comes from elk. The account
 * band is the one exception and is not a layout — it is a list.
 */

const elk = new ELK();

/** Layered, top-down, orthogonal. Generous spacing because these graphs
 *  are read, not glanced at, and a cramped diagram is a diagram nobody
 *  traces a path through. */
const LAYOUT_OPTIONS = {
  "elk.algorithm": "layered",
  "elk.direction": "DOWN",
  "elk.edgeRouting": "ORTHOGONAL",
  "elk.hierarchyHandling": "INCLUDE_CHILDREN",
  "elk.layered.spacing.nodeNodeBetweenLayers": "72",
  "elk.spacing.nodeNode": "44",
  "elk.spacing.edgeNode": "28",
  "elk.spacing.edgeEdge": "18",
  "elk.padding": "[top=24,left=24,bottom=24,right=24]",
  // Ports fixed to the sides so edges leave the bottom and enter the
  // top. Without this elk is free to route an arrow out of the side of a
  // box and back into the side of the one below it, which reads as a
  // loop rather than a step.
  "elk.portConstraints": "FIXED_SIDE",
  "elk.layered.nodePlacement.strategy": "NETWORK_SIMPLEX",
  "elk.layered.crossingMinimization.strategy": "LAYER_SWEEP",
} as const;

const NODE_W = 168;
const NODE_H = 62;

type Laid = { id: string; x: number; y: number; w: number; h: number };
type Routed = { source: string; target: string; label: string; kind: string; points: { x: number; y: number }[] };

/** AWS's own service colour categories. Not decoration: a reader who
 *  knows the palette can tell storage from compute before reading the
 *  label, and using one colour for everything throws that away. */
const CATEGORY_COLOUR: Record<string, string> = {
  compute: "#ED7100",
  compute_fargate: "#ED7100",
  lambda: "#ED7100",
  inference: "#01A88D",
  database: "#527FFF",
  database_replica: "#527FFF",
  dynamodb: "#527FFF",
  cache: "#527FFF",
  search: "#8C4FFF",
  warehouse: "#8C4FFF",
  athena: "#8C4FFF",
  glue: "#8C4FFF",
  storage: "#7AA116",
  block_storage: "#7AA116",
  archive: "#7AA116",
  backup: "#7AA116",
  backup_dr: "#7AA116",
  object_lock: "#7AA116",
  cdn: "#8C4FFF",
  dns: "#8C4FFF",
  loadbalancer: "#8C4FFF",
  network: "#8C4FFF",
  nat: "#8C4FFF",
  vpc_endpoints: "#8C4FFF",
  apigateway: "#E7157B",
  connections: "#E7157B",
  queue: "#E7157B",
  eventbus: "#E7157B",
  streaming: "#E7157B",
  firehose: "#E7157B",
  notification: "#E7157B",
  email: "#E7157B",
  waf: "#DD344C",
  kms: "#DD344C",
  secrets: "#DD344C",
  auth: "#DD344C",
  tls: "#DD344C",
  users: "#232F3E",
};

function colourFor(kind: string): string {
  return CATEGORY_COLOUR[kind] ?? "#5A6B7B";
}

export function TierDiagram({
  nodes,
  edges,
  tierName,
}: {
  nodes: GraphNode[];
  edges: Edge[];
  tierName: string;
}) {
  const [laid, setLaid] = useState<Laid[] | null>(null);
  const [routed, setRouted] = useState<Routed[]>([]);
  const [size, setSize] = useState({ w: 0, h: 0 });
  const [playing, setPlaying] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);

  /** prefers-reduced-motion is a stated accessibility need, not a
   *  preference to weigh. Read once and obeyed: the animation control is
   *  hidden entirely rather than offered and then ignored. */
  const [reducedMotion, setReducedMotion] = useState(false);
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReducedMotion(query.matches);
    const onChange = (e: MediaQueryListEvent) => {
      setReducedMotion(e.matches);
      if (e.matches) setPlaying(false);
    };
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  // Only the data and control planes are laid out. The account plane has
  // no edges by design, so handing it to a layered algorithm would
  // produce a row of boxes elk had no reason to place anywhere in
  // particular — which is exactly the disconnected row this replaces.
  const drawn = useMemo(
    () => nodes.filter((n) => n.plane !== "account"),
    [nodes],
  );
  const account = useMemo(
    () => nodes.filter((n) => n.plane === "account"),
    [nodes],
  );

  useEffect(() => {
    let cancelled = false;
    const ids = new Set(drawn.map((n) => n.id));
    void elk
      .layout({
        id: "root",
        layoutOptions: LAYOUT_OPTIONS,
        children: drawn.map((n) => ({ id: n.id, width: NODE_W, height: NODE_H })),
        edges: edges
          .filter((e) => ids.has(e.source) && ids.has(e.target))
          .map((e, i) => ({
            id: `e${i}`,
            sources: [e.source],
            targets: [e.target],
          })),
      })
      .then((result) => {
        if (cancelled) return;
        // elk's return type is inferred from the INPUT shape, which has
        // no coordinates on it -- the output does. Narrowing here rather
        // than sprinkling non-null assertions through the reader.
        const graph = result as ElkNode;
        setLaid(
          (graph.children ?? []).map((c) => ({
            id: c.id!,
            x: c.x ?? 0,
            y: c.y ?? 0,
            w: c.width ?? NODE_W,
            h: c.height ?? NODE_H,
          })),
        );
        const byId = new Map(
          (graph.children ?? []).map((c) => [c.id!, c] as const),
        );
        setRouted(
          (graph.edges ?? []).flatMap((e) => {
            const original = edges.filter(
              (x) => ids.has(x.source) && ids.has(x.target),
            )[Number(e.id!.slice(1))];
            if (!original) return [];
            const section = e.sections?.[0];
            const points = section
              ? [
                  section.startPoint,
                  ...(section.bendPoints ?? []),
                  section.endPoint,
                ].map((p) => ({ x: p.x, y: p.y }))
              : [];
            if (points.length < 2) {
              // Fall back to centre-to-centre only when elk gave no
              // route at all, so an edge is never silently dropped.
              const a = byId.get(original.source);
              const b = byId.get(original.target);
              if (!a || !b) return [];
              return [{
                ...original,
                kind: original.kind ?? "flow",
                points: [
                  { x: (a.x ?? 0) + NODE_W / 2, y: (a.y ?? 0) + NODE_H },
                  { x: (b.x ?? 0) + NODE_W / 2, y: b.y ?? 0 },
                ],
              }];
            }
            return [{ ...original, kind: original.kind ?? "flow", points }];
          }),
        );
        setSize({ w: graph.width ?? 0, h: graph.height ?? 0 });
      });
    return () => {
      cancelled = true;
    };
  }, [drawn, edges]);

  const byId = useMemo(
    () => new Map(nodes.map((n) => [n.id, n] as const)),
    [nodes],
  );
  const position = useMemo(
    () => new Map((laid ?? []).map((l) => [l.id, l] as const)),
    [laid],
  );

  /** THE REQUEST PATH ONLY. A request does not travel through a key, so
   *  attachment edges are never animated — animating them would assert a
   *  sequence that does not exist. */
  const flowEdges = routed.filter((e) => e.kind !== "attaches");

  if (!laid) {
    return (
      <div className="flex h-48 items-center justify-center rounded-xl border border-neutral-200 bg-neutral-50 text-sm text-neutral-500">
        Laying out {tierName}…
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {!reducedMotion && flowEdges.length > 0 && (
        <div className="flex items-center gap-3">
          <button
            onClick={() => setPlaying((p) => !p)}
            className="rounded-lg border border-neutral-300 px-3 py-1.5 text-xs font-semibold text-neutral-700 hover:bg-neutral-50"
          >
            {playing ? "Stop" : "Trace a request"}
          </button>
          <span className="text-xs text-neutral-500">
            Follows the data plane only — a request does not pass through a
            key or an audit trail.
          </span>
        </div>
      )}

      <div className="overflow-x-auto rounded-xl border border-neutral-200 bg-white p-4">
        <svg
          ref={svgRef}
          width={Math.max(size.w, 320)}
          height={Math.max(size.h, 160)}
          viewBox={`0 0 ${Math.max(size.w, 320)} ${Math.max(size.h, 160)}`}
          role="img"
          aria-label={`${tierName} architecture: ${drawn.length} services`}
          className="max-w-full"
        >
          <defs>
            <marker
              id={`arrow-${tierName}`}
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#5A6B7B" />
            </marker>
          </defs>

          {routed.map((e, i) => {
            const path = e.points
              .map((p, idx) => `${idx === 0 ? "M" : "L"} ${p.x} ${p.y}`)
              .join(" ");
            const attaches = e.kind === "attaches";
            return (
              <g key={`${e.source}-${e.target}-${i}`}>
                <path
                  d={path}
                  fill="none"
                  stroke={attaches ? "#B0BAC4" : "#5A6B7B"}
                  strokeWidth={attaches ? 1.25 : 1.75}
                  /* A binding is dashed because it is not a path
                     anything travels along. */
                  strokeDasharray={attaches ? "4 4" : undefined}
                  markerEnd={attaches ? undefined : `url(#arrow-${tierName})`}
                />
                {playing && !attaches && !reducedMotion && (
                  <circle r="4" fill="#0F62FE">
                    <animateMotion
                      dur="1.6s"
                      begin={`${i * 0.18}s`}
                      repeatCount="indefinite"
                      path={path}
                    />
                  </circle>
                )}
              </g>
            );
          })}

          {(laid ?? []).map((l) => {
            const node = byId.get(l.id);
            if (!node) return null;
            const colour = colourFor(node.kind);
            const control = node.plane === "control";
            return (
              <g
                key={l.id}
                transform={`translate(${l.x},${l.y})`}
                onClick={() => setSelected(selected === l.id ? null : l.id)}
                className="cursor-pointer"
              >
                <rect
                  width={l.w}
                  height={l.h}
                  rx={8}
                  fill="#fff"
                  stroke={colour}
                  strokeWidth={selected === l.id ? 2.5 : 1.5}
                  strokeDasharray={control ? "5 3" : undefined}
                />
                <rect width={5} height={l.h} rx={2} fill={colour} />
                <text x={16} y={24} className="fill-neutral-900 text-[12px] font-semibold">
                  {node.label.length > 22 ? `${node.label.slice(0, 21)}…` : node.label}
                </text>
                <text x={16} y={42} className="fill-neutral-500 text-[11px]">
                  {node.priced ? money(node.monthly_usd) : "not priced"}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {/* THE ACCOUNT PLANE. A labelled band, with no edges, because these
          watch the whole account and belong to no node in it. Drawing an
          arrow from GuardDuty to the database would be inventing a
          relationship; leaving them out entirely would hide real spend. */}
      {account.length > 0 && (
        <div className="rounded-xl border border-neutral-200 bg-neutral-50 px-4 py-3">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
            Account-wide — watches everything, attaches to nothing
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {account.map((n) => (
              <span
                key={n.id}
                className="rounded-md border border-neutral-300 bg-white px-2.5 py-1 text-xs text-neutral-700"
              >
                {n.label}
                <span className="ml-1.5 font-mono text-neutral-500">
                  {n.priced ? money(n.monthly_usd) : "—"}
                </span>
              </span>
            ))}
          </div>
        </div>
      )}

      {selected && byId.get(selected)?.because && (
        <p className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs leading-relaxed text-neutral-700">
          <span className="font-semibold">{byId.get(selected)!.label}:</span>{" "}
          {byId.get(selected)!.because}
        </p>
      )}
    </div>
  );
}
