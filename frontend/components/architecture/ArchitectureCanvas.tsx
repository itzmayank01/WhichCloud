"use client";

import { useLayoutEffect, useRef, useState } from "react";
import type { ArchitectureView, Flow, Tier } from "@/lib/api";

/**
 * Draws an architecture the server has already placed.
 *
 * Every coordinate here arrives from the layout engine, including the routed
 * polyline for each arrow. That is deliberate: layout is deterministic and
 * depends on nothing the browser knows, so computing it once on the server
 * means two people looking at the same architecture see the same picture.
 * This component decides how things look, never where they go.
 */

/* Each flow gets its own stroke, because a request path and a replication
   path are not the same claim about the system. Colour alone would not carry
   it -- these are read at a glance and often printed. */
const FLOW: Record<Flow, { stroke: string; dash?: string; width: number; label: string }> = {
  sync: { stroke: "var(--accent)", width: 1.8, label: "Request path" },
  async: { stroke: "#8B5CF6", width: 1.8, dash: "7 5", label: "Event / queue" },
  replication: { stroke: "#0EA5E9", width: 1.8, dash: "2 4", label: "Replication" },
  control: { stroke: "#94A3B8", width: 1.3, dash: "1 4", label: "Control plane" },
};

const TIER_LABEL: Record<Tier, string> = {
  edge: "Edge",
  api: "API",
  compute: "Compute",
  data: "Data",
  async: "Async",
  analytics: "Analytics",
  ml: "Machine learning",
  security: "Security",
  cicd: "Delivery",
  observability: "Observability",
};

/* Containers are tinted by what they are, so a region and a subnet are
   distinguishable without reading the label. */
const GROUP: Record<string, { stroke: string; fill: string }> = {
  account: { stroke: "#CBD5E1", fill: "rgba(148,163,184,0.05)" },
  region: { stroke: "#93C5FD", fill: "rgba(59,130,246,0.05)" },
  az: { stroke: "#A7F3D0", fill: "rgba(16,185,129,0.05)" },
  vpc: { stroke: "#FCD34D", fill: "rgba(245,158,11,0.05)" },
  subnet: { stroke: "#E2E8F0", fill: "rgba(148,163,184,0.07)" },
};

function path(points: { x: number; y: number }[]): string {
  return points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x} ${p.y}`).join(" ");
}

export function ArchitectureCanvas({
  view,
  /** How many nodes are revealed; undefined means all of them. */
  revealed,
}: {
  view: ArchitectureView;
  revealed?: number;
}) {
  const shell = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  const lastWidth = useRef(-1);

  /* Measured before paint, so the canvas never shows at its authored size and
     then snaps down. Same reasoning as the priced diagram, and the same guard
     for the server, where there is no layout phase at all. */
  const useIsomorphic = typeof window !== "undefined" ? useLayoutEffect : () => {};

  useIsomorphic(() => {
    const el = shell.current;
    if (!el) return;

    /* Only width is observed. Scaling changes this element's own height, so
       reacting to height feeds back into the observer -- a loop the browser
       resolves by dropping notifications, which silently freezes the diagram
       at whatever size it first had. */
    const fit = () => {
      const available = el.clientWidth;
      if (available === lastWidth.current || available === 0) return;
      lastWidth.current = available;
      setScale(Math.min(1, available / view.canvas.width));
    };

    fit();
    const observer = new ResizeObserver(fit);
    observer.observe(el);
    return () => observer.disconnect();
  }, [view.canvas.width]);

  const shown = revealed ?? view.nodes.length;
  const visible = new Set(view.nodes.slice(0, shown).map((n) => n.id));

  return (
    <div ref={shell} className="w-full">
      <svg
        viewBox={`0 0 ${view.canvas.width} ${view.canvas.height}`}
        width={view.canvas.width * scale}
        height={view.canvas.height * scale}
        className="block"
        role="img"
        aria-label={`Architecture diagram: ${view.counts.services} services across ${view.regions} region${view.regions === 1 ? "" : "s"}`}
      >
        <defs>
          {Object.entries(FLOW).map(([flow, style]) => (
            <marker
              key={flow}
              id={`wc-arrow-${flow}`}
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="5"
              markerHeight="5"
              orient="auto-start-reverse"
            >
              <path d="M0 0 L10 5 L0 10 z" fill={style.stroke} />
            </marker>
          ))}
        </defs>

        {/* Tier bands first: they are the ground everything else sits on. */}
        {view.bands.map((band, i) => (
          <g key={`${band.tier}-${band.y}`}>
            {i % 2 === 1 && (
              <rect
                x={0}
                y={band.y}
                width={view.canvas.width}
                height={band.h}
                fill="var(--sunk)"
                opacity={0.5}
              />
            )}
            <text
              x={18}
              y={band.y + 14}
              className="fill-[var(--ink-3)] font-mono"
              fontSize={12}
              letterSpacing="0.1em"
            >
              {TIER_LABEL[band.tier].toUpperCase()}
            </text>
          </g>
        ))}

        {/* Containers, outermost first — the server sorted them so nesting
            lands on top without this component sorting anything. */}
        {view.groups.map((group) => {
          const style = GROUP[group.kind] ?? GROUP.subnet;
          return (
            <g key={group.id}>
              <rect
                x={group.x}
                y={group.y}
                width={group.w}
                height={group.h}
                rx={14}
                fill={style.fill}
                stroke={style.stroke}
                strokeWidth={1.4}
                strokeDasharray="6 5"
              />
              <text
                x={group.x + 14}
                y={group.y + 20}
                className="font-mono"
                fill={style.stroke}
                fontSize={12}
                letterSpacing="0.06em"
              >
                {group.kind.toUpperCase()} · {group.label}
              </text>
            </g>
          );
        })}

        {/* Edges under the boxes, so a line never crosses a label. */}
        {view.edges.map((edge, i) => {
          const style = FLOW[edge.flow];
          const on = visible.has(edge.source) && visible.has(edge.target);
          return (
            <path
              key={`${edge.source}-${edge.target}-${i}`}
              d={path(edge.points)}
              fill="none"
              stroke={style.stroke}
              strokeWidth={style.width}
              strokeDasharray={style.dash}
              strokeLinecap="round"
              strokeLinejoin="round"
              markerEnd={`url(#wc-arrow-${edge.flow})`}
              opacity={on ? 0.85 : 0}
              style={{ transition: "opacity 400ms ease-out" }}
            />
          );
        })}

        {view.nodes.map((node, i) => {
          const on = visible.has(node.id);
          return (
            <g
              key={node.id}
              opacity={on ? 1 : 0}
              style={{
                transition: "opacity 320ms ease-out",
                transitionDelay: on ? `${Math.min(i, 6) * 20}ms` : "0ms",
              }}
            >
              <rect
                x={node.x}
                y={node.y}
                width={node.w}
                height={node.h}
                rx={11}
                fill="var(--surface)"
                stroke="var(--line-strong)"
                strokeWidth={1.3}
              />
              <text
                x={node.x + 14}
                y={node.y + 28}
                className="fill-[var(--ink)]"
                fontSize={14.5}
                fontWeight={600}
              >
                {node.label.length > 22 ? `${node.label.slice(0, 21)}…` : node.label}
              </text>
              <text
                x={node.x + 14}
                y={node.y + 48}
                className="fill-[var(--ink-3)]"
                fontSize={12}
              >
                {(node.purpose || "").length > 26
                  ? `${node.purpose.slice(0, 25)}…`
                  : node.purpose}
              </text>
              {/* Unpriced is stated rather than left blank. A blank cell reads
                  as free, and most services here are simply not in the
                  catalog yet. */}
              <text
                x={node.x + 14}
                y={node.y + 66}
                className="font-mono"
                fill={node.priced ? "var(--save)" : "var(--ink-3)"}
                fontSize={11}
              >
                {node.priced && node.monthly_usd !== null
                  ? `$${node.monthly_usd.toFixed(2)}/mo`
                  : "not priced"}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

/** The key, so the stroke styles mean something. */
export function FlowLegend() {
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
      {(Object.entries(FLOW) as [Flow, (typeof FLOW)[Flow]][]).map(([flow, style]) => (
        <span key={flow} className="flex items-center gap-2 text-[13px] text-ink-2">
          <svg width={26} height={8} aria-hidden>
            <path
              d="M0 4 L26 4"
              stroke={style.stroke}
              strokeWidth={style.width}
              strokeDasharray={style.dash}
              strokeLinecap="round"
            />
          </svg>
          {style.label}
        </span>
      ))}
    </div>
  );
}
