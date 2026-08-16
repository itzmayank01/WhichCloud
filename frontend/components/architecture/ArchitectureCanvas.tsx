"use client";

import { Icon } from "@iconify/react";
import { useLayoutEffect, useRef, useState } from "react";
import type { ArchitectureView, Flow, Tier } from "@/lib/api";
import { iconFor } from "@/lib/serviceIcon";

/**
 * Draws an architecture the server has already placed.
 *
 * Every coordinate arrives from the layout engine, including the routed
 * polyline for each arrow. Layout is deterministic and depends on nothing the
 * browser knows, so computing it once on the server means two people looking
 * at the same architecture see the same picture. This decides how things
 * look, never where they go.
 *
 * Bands, containers and arrows are SVG; the boxes are HTML positioned over
 * it. Text in SVG cannot wrap, so a service box either truncates its label or
 * overflows silently -- and an icon inside SVG needs a foreignObject anyway.
 * The priced diagram already works this way; this follows it.
 */

/* Each flow gets its own stroke, not only its own colour. A request path and
   a replication path are different claims about a system, and these are read
   at a glance and often printed, where colour alone does not survive. */
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

/* AWS's own category colours, which is what makes a reference architecture
   readable at a glance: compute is orange, databases magenta, networking
   purple, security red. Every box being the same white made the diagram one
   undifferentiated field, so a reader had to consult each label to find the
   data layer instead of seeing it.

   Taken from AWS's published architecture-icon palette rather than invented,
   so a diagram drawn here sits beside one drawn in draw.io without clashing. */
const TIER_COLOR: Record<Tier, string> = {
  edge: "#8C4FFF",           // networking & content delivery
  api: "#8C4FFF",
  compute: "#ED7100",        // compute
  data: "#C925D1",           // database
  async: "#E7157B",          // application integration
  analytics: "#8C4FFF",
  ml: "#01A88D",             // machine learning
  security: "#DD344C",       // security, identity & compliance
  cicd: "#3334B9",           // developer tools
  observability: "#E7157B",  // management & governance
};

/* The mark shown when a service has no logo of its own. Says what kind of
   thing it is rather than pretending to be a specific product. */
const TIER_GLYPH: Record<Tier, string> = {
  edge: "mdi:web",
  api: "mdi:api",
  compute: "mdi:server",
  data: "mdi:database",
  async: "mdi:swap-horizontal",
  analytics: "mdi:chart-box-outline",
  ml: "mdi:brain",
  security: "mdi:shield-lock-outline",
  cicd: "mdi:source-branch",
  observability: "mdi:chart-line",
};

const GROUP: Record<string, { stroke: string; fill: string }> = {
  account: { stroke: "#94A3B8", fill: "rgba(148,163,184,0.04)" },
  region: { stroke: "#60A5FA", fill: "rgba(59,130,246,0.04)" },
  az: { stroke: "#34D399", fill: "rgba(16,185,129,0.04)" },
  vpc: { stroke: "#FBBF24", fill: "rgba(245,158,11,0.05)" },
  subnet: { stroke: "#CBD5E1", fill: "rgba(148,163,184,0.06)" },
};

function path(points: { x: number; y: number }[]): string {
  return points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x} ${p.y}`).join(" ");
}

export function ArchitectureCanvas({
  view,
  revealed,
}: {
  view: ArchitectureView;
  /** How many nodes are revealed; undefined means all of them. */
  revealed?: number;
}) {
  const shell = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  const lastWidth = useRef(-1);

  /* Measured before paint, so the canvas never shows at full size and then
     snaps down. No server equivalent exists, hence the guard. */
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
      {/* The scaled stage. Height is set explicitly because a transform does
          not change an element's layout box, so without it the page would
          reserve the unscaled height and leave a gap underneath. */}
      <div
        style={{
          width: view.canvas.width * scale,
          height: view.canvas.height * scale,
        }}
      >
        <div
          className="relative origin-top-left"
          style={{
            width: view.canvas.width,
            height: view.canvas.height,
            transform: `scale(${scale})`,
          }}
        >
          <svg
            width={view.canvas.width}
            height={view.canvas.height}
            className="absolute inset-0"
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

            {/* Bands first: the ground everything sits on. */}
            {view.bands.map((band, i) => (
              <g key={`${band.tier}-${band.y}`}>
                {i % 2 === 1 && (
                  <rect
                    x={0}
                    y={band.y}
                    width={view.canvas.width}
                    height={band.h}
                    fill="var(--sunk)"
                    opacity={0.45}
                  />
                )}
                <text
                  x={18}
                  y={band.y + 14}
                  fill="var(--ink-3)"
                  fontSize={11.5}
                  fontFamily="var(--font-geist-mono), monospace"
                  letterSpacing="0.12em"
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
                    fill={style.stroke}
                    fontSize={11.5}
                    fontFamily="var(--font-geist-mono), monospace"
                    letterSpacing="0.07em"
                  >
                    {group.kind.toUpperCase()} · {group.label}
                  </text>
                </g>
              );
            })}

            {/* Arrows under the boxes, so a line never crosses a label. */}
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
                  opacity={on ? 0.8 : 0}
                  style={{ transition: "opacity 380ms ease-out" }}
                />
              );
            })}
          </svg>

          {/* Boxes as HTML, so labels wrap and logos render as themselves. */}
          {view.nodes.map((node, i) => {
            const on = visible.has(node.id);
            const icon = iconFor(node.label);
            return (
              <div
                key={node.id}
                className="absolute overflow-hidden rounded-xl border border-line-strong bg-surface elev-1"
                style={{
                  left: node.x,
                  top: node.y,
                  width: node.w,
                  height: node.h,
                  opacity: on ? 1 : 0,
                  transform: on ? "translateY(0)" : "translateY(6px)",
                  transition: "opacity 320ms ease-out, transform 320ms ease-out",
                  transitionDelay: on ? `${Math.min(i, 6) * 18}ms` : "0ms",
                }}
              >
                {/* The category, as a bar along the top. Colour does the work
                    a reader would otherwise do by reading every label. */}
                <span
                  className="absolute inset-x-0 top-0 h-[3px]"
                  style={{ background: TIER_COLOR[node.tier] }}
                  aria-hidden
                />
                <div className="flex h-full flex-col justify-center px-3 pt-[3px]">
                  <div className="flex items-center gap-2">
                    <span
                      className="grid h-[26px] w-[26px] shrink-0 place-items-center rounded-md"
                      style={{ background: `${TIER_COLOR[node.tier]}14` }}
                    >
                      <Icon
                        icon={icon ?? TIER_GLYPH[node.tier]}
                        width={17}
                        height={17}
                        style={icon ? undefined : { color: TIER_COLOR[node.tier] }}
                        aria-hidden
                      />
                    </span>
                    <span className="min-w-0 flex-1 truncate text-[13.5px] font-semibold leading-tight text-ink">
                      {node.label}
                    </span>
                  </div>
                  {node.purpose && (
                    <p className="mt-1 line-clamp-2 pl-[34px] text-[11.5px] leading-snug text-ink-3">
                      {node.purpose}
                    </p>
                  )}
                  {/* Unpriced is stated rather than left blank: a blank reads
                      as free, and most services here are not in the catalog. */}
                  <span
                    className={`mt-1 pl-[34px] font-mono text-[10.5px] ${
                      node.priced ? "text-save" : "text-ink-3"
                    }`}
                  >
                    {node.priced && node.monthly_usd !== null
                      ? `$${node.monthly_usd.toFixed(2)}/mo`
                      : "not priced"}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
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
