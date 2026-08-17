"use client";

import { Icon } from "@iconify/react";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { ArchitectureView, Flow, Tier } from "@/lib/api";
import { iconFor } from "@/lib/serviceIcon";

/**
 * Enterprise AWS Architecture Canvas with animated data flow simulation.
 *
 * Implements the authentic AWS Architecture Center standard:
 * - Official AWS Cloud boundary with dark brand banner
 * - Multi-user actor vector graphic
 * - VPC container (green border, green badge)
 * - Private Subnet container (soft blue fill, blue dashed border, lock badge)
 * - Functional component grouping boxes
 * - High-resolution official AWS icons with 2-line crisp typography
 * - Solid blue step callout badges (1..N) on orthogonal routed arrows
 * - Live animated request packet simulation flowing across steps
 * - Interactive step playback, node hover highlights, and layer filtering
 */

/* Navy and heavier for the request path. AWS draws it in near black at a
   weight that survives printing; a thin grey line reads as a hairline and
   disappears against the tinted subnet fills. */
const FLOW_CONFIG: Record<Flow, { stroke: string; dash?: string; width: number; label: string; particleColor: string }> = {
  sync: { stroke: "#232F3E", width: 2.2, label: "Request path", particleColor: "#2563EB" },
  async: { stroke: "#8B5CF6", width: 1.8, dash: "7 5", label: "Event / Queue", particleColor: "#A855F7" },
  replication: { stroke: "#0EA5E9", width: 1.8, dash: "3 4", label: "Replication", particleColor: "#38BDF8" },
  control: { stroke: "#8896A6", width: 1.5, dash: "2 4", label: "Control plane", particleColor: "#9CA3AF" },
};

/* How far back from a corner an arrow starts to turn. stroke-linejoin only
   softens a corner by the stroke width, which at 2px is invisible; a drawn
   curve is what makes an elbow read as a route the eye follows round rather
   than two lines that happen to meet. */
const CORNER_R = 9;

const TIER_COLOR: Record<Tier, string> = {
  edge: "#8C4FFF",
  api: "#8C4FFF",
  compute: "#ED7100",
  data: "#C925D1",
  async: "#E7157B",
  analytics: "#8C4FFF",
  ml: "#01A88D",
  security: "#DD344C",
  cicd: "#3334B9",
  observability: "#E7157B",
};

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

/* AWS's own group marks, vendored under public/icons/aws-groups. Drawing
   approximations of these was the last thing separating a diagram from
   theirs -- and an availability zone deliberately has none, because in AWS's
   diagrams a zone is a dashed outline and a label, a place rather than a
   thing you can point at. */
function boundaryStyle(kind: string, label: string) {
  const isPublic = /public|dmz/i.test(label);
  switch (kind) {
    case "vpc":
      return { stroke: "#248814", fill: "none", dashed: false, icon: "vpc" };
    case "subnet":
      return isPublic
        ? { stroke: "#248814", fill: "#F2F9F0", dashed: false, icon: "public-subnet" }
        : { stroke: "#147EBA", fill: "#F2F8FC", dashed: false, icon: "private-subnet" };
    case "account":
      return { stroke: "#232F3E", fill: "none", dashed: true, icon: "account" };
    case "az":
      return { stroke: "#00A4A6", fill: "none", dashed: true, icon: "" };
    default:
      return { stroke: "#147EBA", fill: "none", dashed: true, icon: "region" };
  }
}

function BoundaryBadge({ x, y, icon }: { x: number; y: number; icon: string }) {
  if (!icon) return null;
  return <image x={x} y={y} width={26} height={26} href={`/icons/aws-groups/${icon}.png`} />;
}

function formatPoints(points: { x: number; y: number }[]): string {
  if (!points || points.length === 0) return "";
  if (points.length < 3) {
    return points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");
  }

  const out = [`M${points[0].x} ${points[0].y}`];
  for (let i = 1; i < points.length - 1; i++) {
    const prev = points[i - 1];
    const cur = points[i];
    const next = points[i + 1];

    const inLen = Math.max(1, Math.abs(cur.x - prev.x) + Math.abs(cur.y - prev.y));
    const outLen = Math.max(1, Math.abs(next.x - cur.x) + Math.abs(next.y - cur.y));
    /* Clamped to half the shorter segment, so a tight elbow curves less
       rather than overshooting into the segment beyond it. */
    const r = Math.min(CORNER_R, inLen / 2, outLen / 2);

    const ax = cur.x - ((cur.x - prev.x) * r) / inLen;
    const ay = cur.y - ((cur.y - prev.y) * r) / inLen;
    const bx = cur.x + ((next.x - cur.x) * r) / outLen;
    const by = cur.y + ((next.y - cur.y) * r) / outLen;

    out.push(`L${ax} ${ay}`, `Q${cur.x} ${cur.y} ${bx} ${by}`);
  }
  out.push(`L${points[points.length - 1].x} ${points[points.length - 1].y}`);
  return out.join(" ");
}

export function ArchitectureCanvas({
  view,
  revealed,
  activeStep,
  selectedTier,
  onSelectNode,
  isPlaying,
}: {
  view: ArchitectureView;
  revealed?: number;
  activeStep?: number | null;
  selectedTier?: Tier | "all";
  onSelectNode?: (nodeId: string | null) => void;
  isPlaying?: boolean;
}) {
  const shell = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [zoomLevel, setZoomLevel] = useState(1);
  const lastWidth = useRef(-1);

  const useIsomorphic = typeof window !== "undefined" ? useLayoutEffect : useEffect;

  useIsomorphic(() => {
    const el = shell.current;
    if (!el) return;

    const fit = () => {
      const available = el.clientWidth;
      if (available === lastWidth.current || available === 0) return;
      lastWidth.current = available;
      const baseScale = Math.min(1, (available - 16) / view.canvas.width);
      setScale(baseScale);
    };

    fit();
    const observer = new ResizeObserver(fit);
    observer.observe(el);
    return () => observer.disconnect();
  }, [view.canvas.width]);

  const shown = revealed ?? view.nodes.length;
  const visibleNodes = useMemo(
    () => new Set(view.nodes.slice(0, shown).map((n) => n.id)),
    [view.nodes, shown]
  );

  // Determine connected edges and nodes for hover highlight
  const { connectedEdges, connectedNodes } = useMemo(() => {
    if (!hoveredNode) return { connectedEdges: new Set<number>(), connectedNodes: new Set<string>() };
    const edges = new Set<number>();
    const nodes = new Set<string>([hoveredNode]);
    view.edges.forEach((e, idx) => {
      if (e.source === hoveredNode || e.target === hoveredNode) {
        edges.add(idx);
        nodes.add(e.source);
        nodes.add(e.target);
      }
    });
    return { connectedEdges: edges, connectedNodes: nodes };
  }, [hoveredNode, view.edges]);

  const totalWidth = view.canvas.width;
  const totalHeight = view.canvas.height;
  const effectiveScale = scale * zoomLevel;

  return (
    <div ref={shell} className="relative w-full overflow-hidden select-none">
      {/* Zoom controls */}
      <div className="absolute right-4 top-4 z-20 flex items-center gap-1.5 rounded-lg border border-neutral-200 bg-white/95 p-1 shadow-sm backdrop-blur">
        <button
          onClick={() => setZoomLevel((z) => Math.max(0.6, z - 0.15))}
          title="Zoom out"
          className="grid h-7 w-7 place-items-center rounded text-neutral-600 hover:bg-neutral-100 active:scale-95"
        >
          <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="4" y1="10" x2="16" y2="10" />
          </svg>
        </button>
        <span className="w-12 text-center font-mono text-[11px] font-semibold text-neutral-600">
          {Math.round(zoomLevel * 100)}%
        </span>
        <button
          onClick={() => setZoomLevel((z) => Math.min(1.8, z + 0.15))}
          title="Zoom in"
          className="grid h-7 w-7 place-items-center rounded text-neutral-600 hover:bg-neutral-100 active:scale-95"
        >
          <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="10" y1="4" x2="10" y2="16" />
            <line x1="4" y1="10" x2="16" y2="10" />
          </svg>
        </button>
        <button
          onClick={() => setZoomLevel(1)}
          title="Reset zoom"
          className="ml-0.5 rounded px-1.5 py-1 text-[10.5px] font-semibold text-neutral-500 hover:bg-neutral-100 hover:text-neutral-900"
        >
          Reset
        </button>
      </div>

      <div
        className="overflow-auto scrollbar-thin transition-all"
        style={{
          width: "100%",
          maxHeight: "820px",
        }}
      >
        <div
          style={{
            width: totalWidth * effectiveScale,
            height: totalHeight * effectiveScale,
            position: "relative",
          }}
        >
          <div
            className="relative origin-top-left"
            style={{
              width: totalWidth,
              height: totalHeight,
              transform: `scale(${effectiveScale})`,
            }}
          >
            {/* SVG Background Layer: Boundaries, Containers, Arrows, and Step Badges */}
            <svg
              width={totalWidth}
              height={totalHeight}
              className="absolute inset-0"
              role="img"
              aria-label="AWS Cloud Architecture Diagram"
            >
              <defs>
                {/* Arrow markers */}
                {Object.entries(FLOW_CONFIG).map(([flow, cfg]) => (
                  <marker
                    key={flow}
                    id={`aws-arrow-${flow}`}
                    viewBox="0 0 12 12"
                    refX="10"
                    refY="6"
                    markerWidth="8"
                    markerHeight="8"
                    orient="auto-start-reverse"
                  >
                    {/* An open chevron, not a filled triangle. A solid head at
                        this scale reads as a blob on the end of a line; two
                        strokes meeting at a point read as a direction. */}
                    <path
                      d="M3.5 2.5 L9.5 6 L3.5 9.5"
                      fill="none"
                      stroke={cfg.stroke}
                      strokeWidth={1.9}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </marker>
                ))}

                {/* Animated Flow Gradient */}
                <linearGradient id="flow-pulse-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#3B82F6" stopOpacity="0" />
                  <stop offset="50%" stopColor="#60A5FA" stopOpacity="1" />
                  <stop offset="100%" stopColor="#2563EB" stopOpacity="0" />
                </linearGradient>

                {/* Glow Filter for Active Step */}
                <filter id="badge-glow" x="-20%" y="-20%" width="140%" height="140%">
                  <feDropShadow dx="0" dy="2" stdDeviation="3" floodColor="#2563EB" floodOpacity="0.45" />
                </filter>

                {/* Drop shadow for AWS Cloud boundary */}
                <filter id="cloud-shadow" x="-5%" y="-5%" width="110%" height="110%">
                  <feDropShadow dx="0" dy="4" stdDeviation="10" floodColor="#0F172A" floodOpacity="0.06" />
                </filter>
              </defs>

              {/* 1. AWS Cloud Outer Container */}
              {view.cloud && (
                <g filter="url(#cloud-shadow)">
                  {/* Outer Cloud Boundary */}
                  <rect
                    x={view.cloud.x}
                    y={view.cloud.y}
                    width={view.cloud.w}
                    height={view.cloud.h}
                    rx={10}
                    fill="#FFFFFF"
                    stroke="#232F3E"
                    strokeWidth={1.8}
                  />

                  {/* AWS's own AWS Cloud mark, vendored beside the other
                      group icons. This was a hand-drawn likeness -- navy
                      square, wordmark, an orange arc for the smile -- and a
                      decent likeness is still a likeness. */}
                  <g>
                    <image
                      x={view.cloud.x + 12}
                      y={view.cloud.y + 9}
                      width={36}
                      height={36}
                      href="/icons/aws-groups/aws-cloud.png"
                    />
                    <text
                      x={view.cloud.x + 58}
                      y={view.cloud.y + 33}
                      fontSize="15"
                      fontWeight="600"
                      fill="#232F3E"
                      letterSpacing="0.01em"
                    >
                      AWS Cloud
                    </text>
                  </g>
                </g>
              )}

              {/* 2. Users (Actor) on the left */}
              {view.actor && (
                <g className="transition-transform duration-200">
                  {/* Actor Box */}
                  <rect
                    x={view.actor.x}
                    y={view.actor.y}
                    width={view.actor.w}
                    height={view.actor.h}
                    rx={8}
                    fill="#FFFFFF"
                    stroke="#E2E8F0"
                    strokeWidth={1.2}
                    className="shadow-sm"
                  />
                  {/* Multi-person Users SVG Icon */}
                  <g transform={`translate(${view.actor.x + view.actor.w / 2 - 20}, ${view.actor.y + 16})`}>
                    <circle cx="20" cy="11" r="5.5" fill="none" stroke="#232F3E" strokeWidth="1.8" />
                    <path d="M 11 26 C 11 20, 29 20, 29 26" fill="none" stroke="#232F3E" strokeWidth="1.8" />
                    {/* Left user */}
                    <circle cx="10" cy="13" r="4" fill="none" stroke="#475569" strokeWidth="1.5" opacity="0.8" />
                    <path d="M 3 26 C 3 21, 15 21, 16 26" fill="none" stroke="#475569" strokeWidth="1.5" opacity="0.8" />
                    {/* Right user */}
                    <circle cx="30" cy="13" r="4" fill="none" stroke="#475569" strokeWidth="1.5" opacity="0.8" />
                    <path d="M 24 26 C 25 21, 37 21, 37 26" fill="none" stroke="#475569" strokeWidth="1.5" opacity="0.8" />
                  </g>
                  <text
                    x={view.actor.x + view.actor.w / 2}
                    y={view.actor.y + 68}
                    textAnchor="middle"
                    fontSize="13"
                    fontWeight="700"
                    fill="#232F3E"
                  >
                    {view.actor.label || "Users"}
                  </text>
                  <text
                    x={view.actor.x + view.actor.w / 2}
                    y={view.actor.y + 82}
                    textAnchor="middle"
                    fontSize="10"
                    fontWeight="500"
                    fill="#64748B"
                  >
                    Clients & Traffic
                  </text>
                </g>
              )}

              {/* 3. VPC Boundaries (Green Container with [VPC] badge) */}
              {/* Boundaries, all drawn the same way: a square badge in the
                  container's own colour with a white glyph, and the label
                  beside it. AWS uses these to tell the kinds apart before any
                  label is read -- a padlock on a subnet, a cloud holding a
                  padlock on a VPC -- and the subnet's colour says whether it
                  faces the internet. Three separate treatments had grown here
                  and none of them matched the exported file. */}
              {view.groups.map((g) => {
                const style = boundaryStyle(g.kind, g.label);
                return (
                  <g key={g.id}>
                    <rect
                      x={g.x}
                      y={g.y}
                      width={g.w}
                      height={g.h}
                      rx={4}
                      fill={style.fill}
                      stroke={style.stroke}
                      strokeWidth={1.5}
                      strokeDasharray={style.dashed ? "6 5" : undefined}
                    />
                    <BoundaryBadge x={g.x + 10} y={g.y + 8} icon={style.icon} />
                    <text
                      x={g.x + (style.icon ? 42 : 14)}
                      y={g.y + 27}
                      fontSize="13"
                      fontWeight="600"
                      fill={style.stroke}
                    >
                      {g.label}
                    </text>
                  </g>
                );
              })}

              {/* 6. Functional Component Groups (Dashed containers matching reference) */}
              {view.components.map((comp) => (
                <g key={comp.name}>
                  {/* Dashed outer boundary */}
                  <rect
                    x={comp.x}
                    y={comp.y}
                    width={comp.w}
                    height={comp.h}
                    rx={10}
                    fill="#FFFFFF"
                    stroke="#94A3B8"
                    strokeWidth={1.4}
                    strokeDasharray="6 4"
                    className="transition-colors"
                  />
                  {/* Component Title Header */}
                  <text
                    x={comp.x + 16}
                    y={comp.y + 24}
                    fill="#1E293B"
                    fontSize="13.5"
                    fontWeight="700"
                    letterSpacing="0.01em"
                  >
                    {comp.name} {comp.name.toLowerCase().includes("component") ? "" : "component"}
                  </text>
                </g>
              ))}

              {/* 7. Orthogonal Connection Arrows (Routed Polylines) */}
              {view.edges.map((edge, i) => {
                const isStepActive = activeStep !== null && edge.step === activeStep;
                const isHoverConnected = hoveredNode !== null && connectedEdges.has(i);
                const isDimmed =
                  (hoveredNode !== null && !isHoverConnected) ||
                  (activeStep !== null && edge.step !== activeStep);

                const flowCfg = FLOW_CONFIG[edge.flow] ?? FLOW_CONFIG.sync;
                const strokeColor = isStepActive
                  ? "#2563EB"
                  : isHoverConnected
                  ? "#2563EB"
                  : flowCfg.stroke;
                const strokeWidth = isStepActive || isHoverConnected ? 2.4 : flowCfg.width;
                const d = formatPoints(edge.points);

                return (
                  <g key={`${edge.source}-${edge.target}-${i}`}>
                    {/* Shadow / Aura for active path */}
                    {(isStepActive || isHoverConnected) && (
                      <path
                        d={d}
                        fill="none"
                        stroke="#93C5FD"
                        strokeWidth={6}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        opacity={0.65}
                      />
                    )}

                    {/* Main Flow Arrow */}
                    <path
                      d={d}
                      fill="none"
                      stroke={strokeColor}
                      strokeWidth={strokeWidth}
                      strokeDasharray={edge.flow === "sync" ? "none" : flowCfg.dash}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      markerEnd={`url(#aws-arrow-${edge.flow})`}
                      opacity={isDimmed ? 0.25 : 0.9}
                      className="transition-all duration-200"
                    />

                    {/* Live Request Flow Pulse Animation */}
                    {(isPlaying || isStepActive) && !isDimmed && (
                      <circle r={3.5} fill={flowCfg.particleColor} className="filter drop-shadow">
                        <animateMotion
                          path={d}
                          dur={isStepActive ? "1.6s" : "2.4s"}
                          repeatCount="indefinite"
                        />
                      </circle>
                    )}
                  </g>
                );
              })}

              {/* 8. Numbered Step Callout Badges (Solid Vibrant Blue Boxes: 1, 2, 3...) */}
              {view.edges.map((edge, i) => {
                if (!edge.step || !edge.badge) return null;
                const isStepActive = activeStep !== null && edge.step === activeStep;
                const isHoverConnected = hoveredNode !== null && connectedEdges.has(i);

                return (
                  <g
                    key={`step-badge-${i}`}
                    transform={`translate(${edge.badge.x}, ${edge.badge.y})`}
                    className="cursor-pointer transition-transform hover:scale-110"
                    filter={isStepActive ? "url(#badge-glow)" : undefined}
                  >
                    <rect
                      x={-11}
                      y={-11}
                      width={22}
                      height={22}
                      rx={4}
                      fill={isStepActive ? "#1D4ED8" : isHoverConnected ? "#2563EB" : "#0066CC"}
                      stroke="#FFFFFF"
                      strokeWidth={1.5}
                    />
                    <text
                      x={0}
                      y={4}
                      textAnchor="middle"
                      fontSize="11.5"
                      fontWeight="800"
                      fill="#FFFFFF"
                      fontFamily="system-ui, sans-serif"
                    >
                      {edge.step}
                    </text>
                  </g>
                );
              })}
            </svg>

            {/* HTML Layer: Service Nodes (Official Icons & Typography) */}
            {view.nodes.map((node) => {
              const isVisible = visibleNodes.has(node.id);
              const isHovered = hoveredNode === node.id;
              const isConnected = connectedNodes.has(node.id);
              const isDimmed =
                hoveredNode !== null && !isHovered && !isConnected;
              const isTierFiltered =
                selectedTier && selectedTier !== "all" && node.tier !== selectedTier;

              const iconSrc = iconFor(node.label);

              // Parse title and subtitle for clean 2-line display
              const parts = node.label.split("(");
              const mainTitle = parts[0].trim();
              const subDetail =
                parts.length > 1
                  ? parts[1].replace(")", "").trim()
                  : node.purpose || "";

              return (
                <div
                  key={node.id}
                  onMouseEnter={() => {
                    setHoveredNode(node.id);
                    onSelectNode?.(node.id);
                  }}
                  onMouseLeave={() => {
                    setHoveredNode(null);
                    onSelectNode?.(null);
                  }}
                  className={`group absolute flex cursor-pointer flex-col items-center transition-all duration-200 ${
                    isDimmed || isTierFiltered ? "opacity-25 filter grayscale" : "opacity-100"
                  } ${isHovered ? "z-30 scale-105" : "z-10"}`}
                  style={{
                    left: node.x,
                    top: node.y,
                    width: node.w,
                    height: node.h,
                    opacity: isVisible ? (isDimmed || isTierFiltered ? 0.25 : 1) : 0,
                    transform: isVisible
                      ? isHovered
                        ? "translateY(-4px) scale(1.05)"
                        : "translateY(0)"
                      : "translateY(8px)",
                  }}
                >
                  {/* Service Icon Container */}
                  <div
                    className={`relative grid h-14 w-14 place-items-center rounded-xl p-1 transition-all ${
                      isHovered
                        ? "ring-4 ring-blue-400/40 shadow-lg bg-white"
                        : "hover:shadow-md"
                    }`}
                  >
                    {iconSrc ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={iconSrc}
                        alt={node.label}
                        width={56}
                        height={56}
                        className="h-13 w-13 object-contain drop-shadow-sm transition-transform group-hover:scale-105"
                      />
                    ) : (
                      <span
                        className="grid h-12 w-12 place-items-center rounded-lg shadow-sm"
                        style={{ background: `${TIER_COLOR[node.tier]}20` }}
                      >
                        <Icon
                          icon={TIER_GLYPH[node.tier] ?? "mdi:cloud"}
                          width={28}
                          height={28}
                          style={{ color: TIER_COLOR[node.tier] }}
                        />
                      </span>
                    )}

                    {/* Optimized badge indicator */}
                    {node.priced && (
                      <span
                        className="absolute -right-1 -top-1 h-3 w-3 rounded-full bg-emerald-500 ring-2 ring-white"
                        title="Priced in catalog"
                      />
                    )}
                  </div>

                  {/* Service 2-Line Typography */}
                  <div className="mt-1.5 w-full text-center">
                    <span className="block line-clamp-2 px-1 text-[12px] font-bold leading-[1.25] text-neutral-900 group-hover:text-blue-600">
                      {mainTitle}
                    </span>
                    {subDetail && (
                      <span className="mt-0.5 block truncate px-1 text-[10.5px] font-medium leading-tight text-neutral-500">
                        {subDetail}
                      </span>
                    )}
                  </div>

                  {/* Monthly price pill if available */}
                  {node.priced && node.monthly_usd !== null && (
                    <span className="mt-1 inline-block rounded bg-emerald-50 px-1.5 py-0.5 font-mono text-[9.5px] font-bold text-emerald-700">
                      ${node.monthly_usd.toFixed(2)}/mo
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
