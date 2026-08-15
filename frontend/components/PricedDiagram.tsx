"use client";

import { useEffect, useRef, useState } from "react";
import { Icon } from "@iconify/react";
import { ServiceIcon } from "@/components/ServiceIcon";
import { money, type Node as ApiNode, type Option } from "@/lib/api";
import { serviceName } from "@/lib/services";

/**
 * The priced architecture, drawn on the same fixed canvas as the showcase.
 *
 * Same visual system — absolute boxes over an SVG arrow layer, elbow routing,
 * tier groups, a cloud boundary — but every box carries what that service
 * actually costs, and the layout adapts to whichever services a provider
 * publishes a price for.
 *
 * A provider that prices fewer services gets a sparser diagram. That is the
 * honest rendering: GCP's gaps are visible as gaps rather than smoothed over.
 */

const W = 1180;
const MIN_SCALE = 0.62;
const H = 560;
const BOX_W = 168;
const BOX_H = 104;

/** Where each service role sits. Fixed, so a cloud with fewer services
    produces a sparser diagram rather than a re-flowed one. */
const SLOT: Record<string, { x: number; y: number }> = {
  client: { x: 10, y: 228 },
  network: { x: 226, y: 118 },
  loadbalancer: { x: 226, y: 300 },
  compute: { x: 470, y: 210 },
  cache: { x: 716, y: 80 },
  database: { x: 716, y: 228 },
  storage: { x: 716, y: 376 },
  monitoring: { x: 962, y: 228 },
};

const GROUPS = [
  { kinds: ["network", "loadbalancer"], x: 208, y: 84, w: 204, h: 340, label: "Edge" },
  { kinds: ["compute"], x: 452, y: 176, w: 204, h: 172, label: "Application tier" },
  { kinds: ["cache", "database", "storage"], x: 698, y: 46, w: 204, h: 490, label: "Data tier" },
  { kinds: ["monitoring"], x: 944, y: 194, w: 204, h: 172, label: "Operations" },
];

const FLOW: [string, string][] = [
  ["client", "network"],
  ["client", "loadbalancer"],
  ["network", "compute"],
  ["loadbalancer", "compute"],
  ["compute", "cache"],
  ["compute", "database"],
  ["compute", "storage"],
  ["compute", "monitoring"],
];

const CHROME: Record<string, { label: string; logo: string; border: string }> = {
  aws: { label: "AWS Cloud", logo: "logos:aws", border: "#232F3E" },
  azure: { label: "Microsoft Azure", logo: "logos:microsoft-azure", border: "#0078D4" },
  gcp: { label: "Google Cloud", logo: "logos:google-cloud", border: "#1A73E8" },
};

function elbow(a: { x: number; y: number }, b: { x: number; y: number }): string {
  const ax = a.x + BOX_W;
  const ay = a.y + BOX_H / 2;
  const bx = b.x;
  const by = b.y + BOX_H / 2;
  if (Math.abs(ay - by) < 4) return `M${ax} ${ay} H${bx - 9}`;
  const mid = ax + (bx - ax) / 2;
  return `M${ax} ${ay} H${mid} V${by} H${bx - 9}`;
}

export function PricedDiagram({
  option,
  provider,
}: {
  option: Option;
  provider: string;
}) {
  const [hovered, setHovered] = useState<string | null>(null);
  const chrome = CHROME[provider] ?? CHROME.aws;

  /* The layout is authored on a fixed canvas so arrows can be routed to exact
     coordinates. Rather than make the reader scroll it sideways, measure the
     available width and scale the whole thing down to fit — the diagram stays
     one piece and the geometry stays exact. */
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

  const nodes = option.topology.nodes.filter((n) => SLOT[n.kind]);
  const present = new Set(nodes.map((n) => n.kind));
  const total = nodes.reduce((s, n) => s + n.monthly_usd, 0);

  const groups = GROUPS.filter((g) => g.kinds.some((k) => present.has(k)));
  const flows = FLOW.filter(([a, b]) => present.has(a) && present.has(b));

  return (
    <div ref={shell} className="rounded-xl border border-line bg-white p-4">
      <div style={{ overflowX: "auto", overflowY: "hidden" }}>
      {/* A CSS transform does not change an element's layout box: the canvas
          below still occupies its authored width whatever it is scaled to,
          which would leave a scrollbar permanently on. This sizer carries the
          *scaled* dimensions so the layout agrees with what is drawn, and the
          scrollbar appears only when the floor really has been hit. */}
      <div style={{ width: W * scale, height: H * scale }}>
      <div
        className="relative origin-top-left"
        style={{ width: W, height: H, transform: `scale(${scale})` }}
      >
        <div
          className="absolute rounded-lg border"
          style={{
            left: 198,
            top: 20,
            width: W - 210,
            height: H - 36,
            borderColor: chrome.border,
            background: "#fbfbfc",
          }}
        />
        <span
          className="absolute flex items-center gap-2 rounded-md bg-white px-2.5 py-1.5"
          style={{ left: 210, top: 6 }}
        >
          <Icon icon={chrome.logo} width={20} height={20} aria-hidden />
          <span className="text-[14px] font-semibold text-ink-2">{chrome.label}</span>
        </span>

        {groups.map((g) => (
          <div key={g.label}>
            <div
              className="absolute rounded-lg border border-dashed"
              style={{ left: g.x, top: g.y, width: g.w, height: g.h, borderColor: "#9aa3b2" }}
            />
            <span
              className="absolute whitespace-nowrap bg-[#fbfbfc] px-2 text-[13.5px] font-semibold text-ink-2"
              style={{ left: g.x + 12, top: g.y - 10 }}
            >
              {g.label}
            </span>
          </div>
        ))}

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
              id={`priced-head-${provider}`}
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
          {flows.map(([a, b]) => {
            const lit =
              hovered === nodes.find((n) => n.kind === a)?.id ||
              hovered === nodes.find((n) => n.kind === b)?.id;
            return (
              <path
                key={`${a}-${b}`}
                d={elbow(SLOT[a], SLOT[b])}
                stroke={lit ? "#0b0d12" : "#3d4552"}
                strokeWidth={lit ? 2 : 1.4}
                markerEnd={`url(#priced-head-${provider})`}
                className="transition-all duration-200"
              />
            );
          })}
        </svg>

        {nodes.map((n: ApiNode) => {
          const slot = SLOT[n.kind];
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
              style={{ left: slot.x, top: slot.y, width: BOX_W, height: BOX_H }}
            >
              <ServiceIcon
                provider={provider}
                kind={n.kind}
                size={30}
                faded={!n.priced}
              />
              <div className="mt-1 text-[13px] font-semibold leading-tight text-ink">
                {serviceName(provider, n.kind, n.label)}
              </div>
              {n.kind === "client" ? (
                <div className="mt-0.5 text-[12px] text-ink-3">web and mobile</div>
              ) : n.priced ? (
                <div className="mt-1 flex items-baseline gap-1.5">
                  <span className="tnum font-mono text-[15px] font-semibold">
                    {money(n.monthly_usd)}
                  </span>
                  <span className="tnum font-mono text-[12px] text-ink-3">
                    {total > 0 ? Math.round((n.monthly_usd / total) * 100) : 0}%
                  </span>
                </div>
              ) : (
                <div className="mt-1 font-mono text-[12px] text-caution">not priced</div>
              )}

              {n.optimized_by.length > 0 && (
                <span
                  className="absolute -right-1 -top-1 h-3 w-3 rounded-full bg-accent ring-2 ring-white"
                  title={`Optimized by ${n.optimized_by.join(", ")}`}
                />
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
