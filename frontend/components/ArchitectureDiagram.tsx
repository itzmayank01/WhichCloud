"use client";

import { useState } from "react";
import type { Node as ApiNode, Topology } from "@/lib/api";
import { money } from "@/lib/api";
import { serviceName } from "@/lib/services";
import { HoverBoard } from "@/components/HoverBoard";

/**
 * A provider-style cloud architecture diagram, with costs on the services.
 *
 * Drawn in the idiom of AWS, Azure and GCP reference diagrams: a cloud
 * boundary, dashed tier groups, solid category-coloured service tiles with
 * white glyphs, and arrows following the request path. What those diagrams
 * never carry is the money — so every tile here shows its monthly figure and
 * its share of the bill.
 *
 * The glyphs are drawn rather than imported. AWS publishes its icon set under
 * CC-BY-ND, which forbids the recolouring and resizing a component like this
 * needs; the category colours and line-art style are the readable part anyway,
 * and they are not what the licence protects.
 */

type Category = {
  colour: string;
  group: string;
  glyph: React.ReactNode;
};

/* Category colours follow the providers' own conventions, so an engineer reads
   the shape of a system before reading any label. */
const CATEGORY: Record<string, Category> = {
  client: {
    colour: "#5A6270",
    group: "",
    glyph: (
      <>
        <circle cx="12" cy="8" r="3.4" />
        <path d="M5 20c0-3.9 3.1-7 7-7s7 3.1 7 7" />
      </>
    ),
  },
  network: {
    colour: "#8C4FFF",
    group: "Edge",
    glyph: (
      <>
        <circle cx="12" cy="12" r="8.2" />
        <path d="M3.8 12h16.4M12 3.8c2.2 2.6 3.3 5.3 3.3 8.2s-1.1 5.6-3.3 8.2c-2.2-2.6-3.3-5.3-3.3-8.2S9.8 6.4 12 3.8Z" />
      </>
    ),
  },
  loadbalancer: {
    colour: "#8C4FFF",
    group: "Edge",
    glyph: (
      <>
        <circle cx="12" cy="4.2" r="1.8" />
        <path d="M12 6v3.4M12 9.4 5.6 15M12 9.4l6.4 5.6" />
        <rect x="2.6" y="15" width="6" height="6" rx="1.3" />
        <rect x="15.4" y="15" width="6" height="6" rx="1.3" />
      </>
    ),
  },
  compute: {
    colour: "#ED7100",
    group: "Application tier",
    glyph: (
      <>
        <rect x="5" y="5" width="14" height="14" rx="2.2" />
        <rect x="9.2" y="9.2" width="5.6" height="5.6" rx="1" />
        <path d="M9 2.4v2.4M15 2.4v2.4M9 19.2v2.4M15 19.2v2.4M2.4 9h2.4M2.4 15h2.4M19.2 9h2.4M19.2 15h2.4" />
      </>
    ),
  },
  database: {
    colour: "#3556C8",
    group: "Data tier",
    glyph: (
      <>
        <ellipse cx="12" cy="6.4" rx="7.2" ry="3.1" />
        <path d="M4.8 6.4v11.2c0 1.7 3.2 3.1 7.2 3.1s7.2-1.4 7.2-3.1V6.4M4.8 12c0 1.7 3.2 3.1 7.2 3.1s7.2-1.4 7.2-3.1" />
      </>
    ),
  },
  storage: {
    colour: "#4A8C1C",
    group: "Data tier",
    glyph: (
      <>
        <path d="M3.6 7.4 12 3.2l8.4 4.2v9.2L12 20.8l-8.4-4.2V7.4Z" />
        <path d="M3.6 7.4 12 11.6l8.4-4.2M12 11.6v9.2" />
      </>
    ),
  },
};

const CHROME: Record<string, { label: string; mark: string; tint: string }> = {
  aws: { label: "AWS Cloud", mark: "#232F3E", tint: "#f7f8fa" },
  azure: { label: "Microsoft Azure", mark: "#0078D4", tint: "#f5f9fd" },
  gcp: { label: "Google Cloud", mark: "#1A73E8", tint: "#f6f9fd" },
};

function Tile({
  node,
  provider,
  active,
  dimmed,
  onEnter,
  onLeave,
}: {
  node: ApiNode;
  provider: string;
  active: boolean;
  dimmed: boolean;
  onEnter: () => void;
  onLeave: () => void;
}) {
  const cat = CATEGORY[node.kind] ?? CATEGORY.compute;

  return (
    <div
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
      onFocus={onEnter}
      onBlur={onLeave}
      tabIndex={0}
      className={`relative flex w-[156px] flex-col items-center rounded-lg px-2 py-3 text-center outline-none transition-all duration-200 ${
        dimmed ? "opacity-35" : "opacity-100"
      } ${
        active ? "-translate-y-1 bg-white shadow-[0_10px_28px_-10px_rgba(11,13,18,.32)]" : ""
      }`}
    >
      <span
        className="grid h-[52px] w-[52px] place-items-center rounded-[10px] transition-transform duration-200"
        style={{
          background: cat.colour,
          transform: active ? "scale(1.06)" : "scale(1)",
          boxShadow: active ? `0 6px 18px -6px ${cat.colour}` : "none",
          opacity: node.priced ? 1 : 0.4,
        }}
      >
        <svg
          viewBox="0 0 24 24"
          className="h-7 w-7"
          fill="none"
          stroke="#fff"
          strokeWidth="1.7"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden
        >
          {cat.glyph}
        </svg>
      </span>

      <span className="mt-2.5 text-[14.5px] font-medium leading-tight text-ink">
        {serviceName(provider, node.kind, node.label)}
      </span>

      {node.detail && (
        <span className="mt-1 font-mono text-[13px] leading-tight text-ink-3 font-medium">
          {node.detail}
        </span>
      )}

      {node.kind !== "client" && (
        <span className="mt-1.5 flex items-baseline gap-1.5">
          {node.priced ? (
            <>
              <span className="tnum font-mono text-[15px] font-medium">
                {money(node.monthly_usd)}
              </span>
              {node.share > 0.01 && (
                <span className="tnum font-mono text-[13px] text-ink-3 font-medium">
                  {Math.round(node.share * 100)}%
                </span>
              )}
            </>
          ) : (
            <span className="font-mono text-[13px] text-caution font-medium">not priced</span>
          )}
        </span>
      )}

      {node.optimized_by.length > 0 && (
        <span
          className="absolute right-3 top-2 h-2.5 w-2.5 rounded-full ring-2 ring-white"
          style={{ background: "var(--accent)" }}
          title={`Optimized by ${node.optimized_by.join(", ")}`}
        />
      )}
    </div>
  );
}

function Arrow({ dimmed }: { dimmed: boolean }) {
  return (
    <div
      className={`flex shrink-0 items-center px-0.5 transition-opacity ${
        dimmed ? "opacity-20" : "opacity-100"
      }`}
      aria-hidden
    >
      <svg width="32" height="12" viewBox="0 0 32 12" fill="none">
        <path d="M0 6h24" stroke="#98A0AE" strokeWidth="1.2" />
        <path
          d="M23 2 29.5 6 23 10"
          stroke="#98A0AE"
          strokeWidth="1.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );
}

function Group({ label, children }: { label: string; children: React.ReactNode }) {
  if (!label) return <>{children}</>;
  return (
    <div className="relative rounded-lg border border-dashed border-[#b3bac6] px-3 pb-3 pt-8">
      <span className="absolute left-1/2 top-2.5 -translate-x-1/2 whitespace-nowrap text-[13.5px] font-medium text-ink-2">
        {label}
      </span>
      <div className="flex flex-col items-center gap-2">{children}</div>
    </div>
  );
}

export function ArchitectureDiagram({
  topology,
  provider = "aws",
  caption,
}: {
  topology: Topology;
  provider?: string;
  caption?: string;
}) {
  const [hovered, setHovered] = useState<string | null>(null);
  const chrome = CHROME[provider] ?? CHROME.aws;

  // Columns follow the request path, which is how these diagrams read.
  const order = ["network", "loadbalancer", "compute", "database", "storage"];
  const columns: { group: string; nodes: ApiNode[] }[] = [];

  for (const kind of order) {
    const node = topology.nodes.find((n) => n.kind === kind);
    if (!node) continue;
    const group = CATEGORY[kind]?.group ?? "";
    const last = columns[columns.length - 1];
    if (last && last.group === group && group !== "") last.nodes.push(node);
    else columns.push({ group, nodes: [node] });
  }

  const users = topology.nodes.find((n) => n.kind === "client");
  const dim = hovered !== null;
  const focused = topology.nodes.find((n) => n.id === hovered) ?? null;
  const total = topology.nodes.reduce((sum, n) => sum + n.monthly_usd, 0);

  return (
    <div className="overflow-x-auto pb-1">
      <div className="min-w-[900px]">
        <div className="flex items-stretch gap-2">
          {/* the client sits outside the boundary, as in provider diagrams */}
          {users && (
            <>
              <div className="flex items-center">
                <Tile
                  node={users}
                  provider={provider}
                  active={hovered === users.id}
                  dimmed={dim && hovered !== users.id}
                  onEnter={() => setHovered(users.id)}
                  onLeave={() => setHovered(null)}
                />
              </div>
              <div className="flex items-center">
                <Arrow dimmed={dim} />
              </div>
            </>
          )}

          <div
            className="relative flex-1 rounded-xl border border-[#9aa3b2] px-4 pb-4 pt-10"
            style={{ background: chrome.tint }}
          >
            <span className="absolute left-4 top-3 flex items-center gap-2">
              <span
                className="grid h-5 w-5 place-items-center rounded"
                style={{ background: chrome.mark }}
              >
                <span className="h-1.5 w-1.5 rounded-[1px] bg-white" />
              </span>
              <span className="text-[14px] font-medium text-ink-2">{chrome.label}</span>
            </span>

            <div className="flex items-center justify-between gap-1">
              {columns.map((col, i) => (
                <div key={i} className="flex items-center">
                  <Group label={col.group}>
                    {col.nodes.map((n) => (
                      <Tile
                        key={n.id}
                        node={n}
                        provider={provider}
                        active={hovered === n.id}
                        dimmed={dim && hovered !== n.id}
                        onEnter={() => setHovered(n.id)}
                        onLeave={() => setHovered(null)}
                      />
                    ))}
                  </Group>
                  {i < columns.length - 1 && <Arrow dimmed={dim} />}
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-3">
          <HoverBoard node={focused} provider={provider} total={total} />
        </div>

        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
            {[
              ["Compute", "#ED7100"],
              ["Database", "#3556C8"],
              ["Storage", "#4A8C1C"],
              ["Networking", "#8C4FFF"],
            ].map(([label, colour]) => (
              <span key={label} className="flex items-center gap-1.5">
                <span
                  className="h-2.5 w-2.5 rounded-[3px]"
                  style={{ background: colour as string }}
                />
                <span className="text-[13.5px] text-ink-3 font-medium">{label}</span>
              </span>
            ))}
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-accent" />
              <span className="text-[13.5px] text-ink-3 font-medium">optimized</span>
            </span>
          </div>
          {caption && <span className="font-mono text-[13px] text-ink-3 font-medium">{caption}</span>}
        </div>
      </div>
    </div>
  );
}
