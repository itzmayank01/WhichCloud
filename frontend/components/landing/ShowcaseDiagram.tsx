"use client";

import { Icon } from "@iconify/react";
import { useEffect, useRef, useState } from "react";

/**
 * The example architecture on the landing page.
 *
 * This one is illustrative, not priced — it shows the *kind* of system
 * WhichCloud reasons about, at the scale a real application actually reaches.
 * The live, costed diagrams built from the catalog live on the product pages;
 * putting invented prices here would undercut them, so this carries no
 * figures at all.
 *
 * Laid out on a fixed 1180×640 canvas so arrows can be drawn to exact box
 * edges rather than floated between columns. Boxes are absolutely positioned
 * HTML over an SVG arrow layer sharing the same coordinate space.
 */

const W = 1180;
const MIN_SCALE = 0.62;
const H = 640;
const BOX_W = 156;
const BOX_H = 88;

type Node = {
  id: string;
  x: number;
  y: number;
  label: string;
  sub?: string;
  icon?: string;
  outside?: boolean;
};

const NODES: Node[] = [
  { id: "users", x: 14, y: 276, label: "Users", sub: "web and mobile", outside: true },

  { id: "cdn", x: 214, y: 74, label: "Amazon CloudFront", sub: "CDN", icon: "logos:aws-cloudfront" },
  { id: "s3site", x: 410, y: 74, label: "Amazon S3", sub: "static website", icon: "logos:aws-s3" },

  { id: "apigw", x: 214, y: 276, label: "Amazon API Gateway", sub: "REST", icon: "logos:aws-api-gateway" },
  { id: "cognito", x: 214, y: 478, label: "Amazon Cognito", sub: "identity", icon: "logos:aws-cognito" },

  { id: "ecs", x: 452, y: 232, label: "Amazon ECS", sub: "Fargate tasks", icon: "logos:aws-ecs" },
  { id: "lambda", x: 452, y: 372, label: "AWS Lambda", sub: "background jobs", icon: "logos:aws-lambda" },

  { id: "rds", x: 706, y: 118, label: "Amazon RDS", sub: "PostgreSQL", icon: "logos:aws-rds" },
  { id: "cache", x: 706, y: 250, label: "Amazon ElastiCache", sub: "Valkey", icon: "logos:aws-elasticache" },
  { id: "s3data", x: 706, y: 382, label: "Amazon S3", sub: "uploads", icon: "logos:aws-s3" },

  { id: "cw", x: 950, y: 250, label: "Amazon CloudWatch", sub: "metrics and logs", icon: "logos:aws-cloudwatch" },
];

const GROUPS = [
  { x: 434, y: 200, w: 192, h: 300, label: "Application tier" },
  { x: 688, y: 86, w: 192, h: 428, label: "Data tier" },
  { x: 932, y: 218, w: 192, h: 168, label: "Operations" },
];

/** Arrows are described by node, so they always meet the box edge. */
const EDGES: [string, string][] = [
  ["users", "cdn"],
  ["users", "apigw"],
  ["users", "cognito"],
  ["cdn", "s3site"],
  ["cognito", "apigw"],
  ["apigw", "ecs"],
  ["apigw", "lambda"],
  ["ecs", "rds"],
  ["ecs", "cache"],
  ["lambda", "s3data"],
  ["ecs", "cw"],
];

const byId = (id: string) => NODES.find((n) => n.id === id)!;

/** Right edge of the source, left edge of the target, both mid-height. */
function path(a: Node, b: Node): string {
  const ax = a.x + BOX_W;
  const ay = a.y + BOX_H / 2;
  const bx = b.x;
  const by = b.y + BOX_H / 2;

  if (Math.abs(ay - by) < 4) return `M${ax} ${ay} H${bx - 8}`;

  // Elbow: out, across, in — the idiom provider diagrams use, and it never
  // cuts diagonally through a box the way a straight line would.
  const mid = ax + (bx - ax) / 2;
  return `M${ax} ${ay} H${mid} V${by} H${bx - 8}`;
}

export function ShowcaseDiagram() {
  const [hovered, setHovered] = useState<string | null>(null);
  const shell = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);

  const lastWidth = useRef(-1);

  useEffect(() => {
    const el = shell.current;
    if (!el) return;

    /* Only width matters, and only width may be reacted to. Scaling changes
       this element's own height, so responding to height would feed straight
       back into the observer — a loop the browser resolves by dropping
       notifications, which silently freezes the diagram at its first size.
       Gating on width keeps the observer stable. */
    const fit = () => {
      const style = getComputedStyle(el);
      const pad =
        parseFloat(style.paddingLeft || "0") + parseFloat(style.paddingRight || "0");
      const available = el.clientWidth - pad;
      if (available === lastWidth.current) return;
      lastWidth.current = available;

      // Never shrink past the point where the labels stop being readable —
      // below that a scrollbar is the honest answer, since an illegible
      // diagram that happens to fit is worse than one you have to pan.
      setScale(Math.max(MIN_SCALE, Math.min(1, available / W)));
    };

    fit();

    // Window resize is the fallback: ResizeObserver is the precise signal,
    // but it is not delivered in every environment, and a diagram that never
    // re-fits is worse than one that re-fits a little coarsely.
    const ro = new ResizeObserver(fit);
    ro.observe(el);
    window.addEventListener("resize", fit);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", fit);
    };
  }, []);

  return (
    <div ref={shell} className="rounded-xl border border-line bg-white p-4">
      <div style={{ height: H * scale, overflowX: "auto", overflowY: "hidden" }}>
      <div
        className="relative origin-top-left"
        style={{ width: W, height: H, transform: `scale(${scale})` }}
      >
        {/* AWS cloud boundary */}
        <div
          className="absolute rounded-lg border"
          style={{
            left: 186,
            top: 24,
            width: W - 198,
            height: H - 40,
            borderColor: "#232F3E",
            background: "#fbfbfc",
          }}
        />
        <span
          className="absolute flex items-center gap-2 rounded-md bg-white px-2.5 py-1.5"
          style={{ left: 198, top: 10 }}
        >
          <Icon icon="logos:aws" width={22} height={22} aria-hidden />
          <span className="text-[14px] font-semibold text-ink-2">AWS Cloud</span>
        </span>

        {/* tier groups */}
        {GROUPS.map((g) => (
          <div key={g.label}>
            <div
              className="absolute rounded-lg border border-dashed"
              style={{
                left: g.x,
                top: g.y,
                width: g.w,
                height: g.h,
                borderColor: "#9aa3b2",
              }}
            />
            <span
              className="absolute whitespace-nowrap bg-[#fbfbfc] px-2 text-[13.5px] font-semibold text-ink-2"
              style={{ left: g.x + 12, top: g.y - 10 }}
            >
              {g.label}
            </span>
          </div>
        ))}

        {/* arrows, under the boxes so they tuck behind the edges */}
        <svg
          className="absolute inset-0"
          width={W}
          height={H}
          viewBox={`0 0 ${W} ${H}`}
          fill="none"
          aria-hidden
        >
          <defs>
            <marker
              id="showcase-head"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="8"
              markerHeight="8"
              orient="auto-start-reverse"
              markerUnits="userSpaceOnUse"
            >
              <path d="M1.5 1.5 L9 5 L1.5 8.5 Z" fill="#3d4552" />
            </marker>
          </defs>
          {EDGES.map(([from, to]) => {
            const lit = hovered === from || hovered === to;
            return (
              <path
                key={`${from}-${to}`}
                d={path(byId(from), byId(to))}
                stroke={lit ? "#0b0d12" : "#3d4552"}
                strokeWidth={lit ? 2 : 1.4}
                markerEnd="url(#showcase-head)"
                className="transition-all duration-200"
              />
            );
          })}
        </svg>

        {/* service boxes */}
        {NODES.map((n) => {
          const active = hovered === n.id;
          return (
            <div
              key={n.id}
              onMouseEnter={() => setHovered(n.id)}
              onMouseLeave={() => setHovered(null)}
              onFocus={() => setHovered(n.id)}
              onBlur={() => setHovered(null)}
              tabIndex={0}
              className={`absolute flex flex-col items-center justify-center rounded-lg border bg-white px-2 text-center outline-none transition-all duration-200 ${
                active
                  ? "-translate-y-0.5 border-line-strong shadow-[0_10px_24px_-10px_rgba(11,13,18,.3)]"
                  : "border-line shadow-[0_1px_2px_rgba(11,13,18,.05)]"
              }`}
              style={{ left: n.x, top: n.y, width: BOX_W, height: BOX_H }}
            >
              {n.icon ? (
                <Icon icon={n.icon} width={34} height={34} aria-hidden />
              ) : (
                <svg
                  viewBox="0 0 24 24"
                  width={34}
                  height={34}
                  fill="none"
                  stroke="#5A6270"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden
                >
                  <circle cx="9" cy="8" r="3.2" />
                  <path d="M2.5 20c0-3.6 2.9-6.5 6.5-6.5s6.5 2.9 6.5 6.5" />
                  <circle cx="17" cy="7.5" r="2.4" />
                  <path d="M17 12.5c2.5 0 4.5 2 4.5 4.5" />
                </svg>
              )}
              <div className="mt-1.5 text-[13px] font-semibold leading-tight text-ink">
                {n.label}
              </div>
              {n.sub && (
                <div className="mt-0.5 text-[12px] leading-tight text-ink-3">{n.sub}</div>
              )}
            </div>
          );
        })}
      </div>
      </div>
    </div>
  );
}
