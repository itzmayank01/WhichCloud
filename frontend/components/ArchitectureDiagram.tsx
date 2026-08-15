"use client";

import { useState } from "react";
import type { Node as ApiNode, Topology } from "@/lib/api";
import { money } from "@/lib/api";
import { serviceName } from "@/lib/services";

/**
 * A cloud architecture diagram where every node carries its own cost.
 *
 * Provider reference diagrams colour services by category — compute orange,
 * storage green, networking purple — so an engineer reads the shape of a
 * system before reading a single label. This borrows that language and adds
 * the thing those diagrams never have: the monthly figure, on the box.
 *
 * Hovering a node dims the rest and reveals its detail. Costly nodes are drawn
 * heavier, so the expensive part of the architecture looks expensive.
 */

const CATEGORY: Record<
  string,
  { colour: string; wash: string; glyph: React.ReactNode; group: string }
> = {
  client: {
    colour: "var(--svc-client)",
    wash: "#f3f4f6",
    group: "",
    glyph: (
      <>
        <circle cx="12" cy="8.5" r="3.2" />
        <path d="M5.5 19c0-3.6 2.9-6.5 6.5-6.5s6.5 2.9 6.5 6.5" />
      </>
    ),
  },
  network: {
    colour: "var(--svc-network)",
    wash: "#f4efff",
    group: "Edge",
    glyph: (
      <>
        <circle cx="12" cy="12" r="7.5" />
        <path d="M4.5 12h15M12 4.5c2 2.4 3 4.9 3 7.5s-1 5.1-3 7.5c-2-2.4-3-4.9-3-7.5s1-5.1 3-7.5Z" />
      </>
    ),
  },
  loadbalancer: {
    colour: "var(--svc-network)",
    wash: "#f4efff",
    group: "Edge",
    glyph: (
      <>
        <path d="M12 4v5M12 9 6 14M12 9l6 5" />
        <rect x="3.5" y="14" width="5" height="5" rx="1" />
        <rect x="15.5" y="14" width="5" height="5" rx="1" />
      </>
    ),
  },
  compute: {
    colour: "var(--svc-compute)",
    wash: "#fff2e6",
    group: "Application tier",
    glyph: (
      <>
        <rect x="4.5" y="4.5" width="15" height="15" rx="2" />
        <rect x="9" y="9" width="6" height="6" rx="1" />
        <path d="M9 2.5v2M15 2.5v2M9 19.5v2M15 19.5v2M2.5 9h2M2.5 15h2M19.5 9h2M19.5 15h2" />
      </>
    ),
  },
  database: {
    colour: "var(--svc-database)",
    wash: "#eef1fd",
    group: "Data tier",
    glyph: (
      <>
        <ellipse cx="12" cy="6.5" rx="7" ry="3" />
        <path d="M5 6.5v11c0 1.7 3.1 3 7 3s7-1.3 7-3v-11M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3" />
      </>
    ),
  },
  storage: {
    colour: "var(--svc-storage)",
    wash: "#eff6e8",
    group: "Data tier",
    glyph: (
      <>
        <path d="M4 7.5 12 3.5l8 4v9l-8 4-8-4v-9Z" />
        <path d="M4 7.5l8 4 8-4M12 11.5v9" />
      </>
    ),
  },
};

function Glyph({ kind }: { kind: string }) {
  const cat = CATEGORY[kind] ?? CATEGORY.compute;
  return (
    <span
      className="grid h-9 w-9 shrink-0 place-items-center rounded-md"
      style={{ background: cat.wash }}
    >
      <svg
        viewBox="0 0 24 24"
        className="h-[19px] w-[19px]"
        fill="none"
        stroke={cat.colour}
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden
      >
        {cat.glyph}
      </svg>
    </span>
  );
}

function NodeBox({
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
  // Border weight tracks share of the bill — the expensive box looks expensive.
  const heavy = node.share > 0.3;

  return (
    <div
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
      onFocus={onEnter}
      onBlur={onLeave}
      tabIndex={0}
      className={`group relative w-full rounded-lg bg-surface px-3.5 py-3 text-left outline-none transition-all duration-200 ${
        dimmed ? "opacity-40" : "opacity-100"
      } ${
        active
          ? "-translate-y-0.5 shadow-[0_8px_24px_-8px_rgba(11,13,18,.28)]"
          : "shadow-[0_1px_2px_rgba(11,13,18,.05)]"
      }`}
      style={{
        border: `${heavy ? 1.5 : 1}px solid ${active ? cat.colour : "var(--border)"}`,
      }}
    >
      <div className="flex items-start gap-3">
        <Glyph kind={node.kind} />
        <div className="min-w-0 flex-1">
          <div className="truncate text-[15px] font-medium leading-tight">
            {serviceName(provider, node.kind, node.label)}
          </div>
          <div className="mt-0.5 truncate font-mono text-[12.5px] text-ink-3">
            {node.detail || node.sku || "—"}
          </div>
        </div>
        <div className="shrink-0 text-right">
          {node.priced ? (
            <>
              <div className="tnum font-mono text-[15px] leading-tight">
                {money(node.monthly_usd)}
              </div>
              {node.share > 0.01 && (
                <div className="tnum font-mono text-[12px] text-ink-3">
                  {Math.round(node.share * 100)}%
                </div>
              )}
            </>
          ) : (
            <div className="font-mono text-[12px] text-caution">not priced</div>
          )}
        </div>
      </div>

      {node.optimized_by.length > 0 && (
        <span
          className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full ring-2 ring-surface"
          style={{ background: "var(--accent)" }}
          title={`Optimized: ${node.optimized_by.join(", ")}`}
        />
      )}
    </div>
  );
}

function Connector({ dimmed }: { dimmed: boolean }) {
  return (
    <div
      className={`hidden shrink-0 items-center transition-opacity lg:flex ${
        dimmed ? "opacity-25" : "opacity-100"
      }`}
      aria-hidden
    >
      <svg width="26" height="10" viewBox="0 0 26 10" fill="none">
        <path
          d="M0 5h20"
          stroke="var(--border-strong)"
          strokeWidth="1"
          strokeDasharray="3 3"
        />
        <path
          d="M19 1.5 24 5l-5 3.5"
          stroke="var(--border-strong)"
          strokeWidth="1"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );
}

function GroupFrame({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  if (!label) return <div className="flex flex-col gap-2">{children}</div>;
  return (
    <div className="relative rounded-lg border border-dashed border-line-strong p-3 pt-6">
      <span className="absolute left-3 top-1.5 font-mono text-[12px] uppercase tracking-[0.12em] text-ink-3">
        {label}
      </span>
      <div className="flex flex-col gap-2">{children}</div>
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

  // Column layout follows the request path, which is how these diagrams read.
  const order = ["client", "network", "loadbalancer", "compute", "database", "storage"];
  const columns: { group: string; nodes: ApiNode[] }[] = [];

  for (const kind of order) {
    const node = topology.nodes.find((n) => n.kind === kind);
    if (!node) continue;
    const group = CATEGORY[kind]?.group ?? "";
    const last = columns[columns.length - 1];
    if (last && last.group === group && group !== "") last.nodes.push(node);
    else columns.push({ group, nodes: [node] });
  }

  return (
    <div className="rounded-xl border border-line bg-canvas p-5">
      <div className="flex items-start gap-0 overflow-x-auto pb-1 lg:overflow-visible">
        {columns.map((col, i) => (
          <div key={i} className="flex shrink-0 items-center lg:shrink lg:flex-1">
            <div className="w-[210px] lg:w-full">
              <GroupFrame label={col.group}>
                {col.nodes.map((n) => (
                  <NodeBox
                    key={n.id}
                    node={n}
                    provider={provider}
                    active={hovered === n.id}
                    dimmed={hovered !== null && hovered !== n.id}
                    onEnter={() => setHovered(n.id)}
                    onLeave={() => setHovered(null)}
                  />
                ))}
              </GroupFrame>
            </div>
            {i < columns.length - 1 && <Connector dimmed={hovered !== null} />}
          </div>
        ))}
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-3">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
          {[
            ["Compute", "var(--svc-compute)"],
            ["Data", "var(--svc-database)"],
            ["Storage", "var(--svc-storage)"],
            ["Edge", "var(--svc-network)"],
          ].map(([label, colour]) => (
            <span key={label} className="flex items-center gap-1.5">
              <span
                className="h-2 w-2 rounded-sm"
                style={{ background: colour as string }}
              />
              <span className="font-mono text-[12px] text-ink-3">{label}</span>
            </span>
          ))}
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-accent" />
            <span className="font-mono text-[12px] text-ink-3">optimized</span>
          </span>
        </div>
        {caption && (
          <span className="font-mono text-[12px] text-ink-3">{caption}</span>
        )}
      </div>
    </div>
  );
}
