"use client";

import { useMemo, useState } from "react";
import { ICON_CATALOG, GROUP_ICONS, type IconEntry } from "@/lib/iconCatalog";

/**
 * Every mark we vendored, searchable, for building on the canvas.
 *
 * Grouped by provider rather than merged into one list. The three vendors name
 * the same job differently -- Cloud SQL, RDS, Azure Database -- and a single
 * alphabetical run puts those three rows far apart while placing unrelated
 * services next to each other. Someone drawing an AWS diagram wants the AWS
 * shelf, not a search result that happens to include it.
 */

const TABS: { id: IconEntry["provider"]; label: string }[] = [
  { id: "aws", label: "AWS" },
  { id: "gcp", label: "Google" },
  { id: "azure", label: "Azure" },
  { id: "group", label: "Boundaries" },
];

export function ServicePalette({
  onPick,
  onClose,
  cloud,
}: {
  onPick: (entry: IconEntry) => void;
  onClose: () => void;
  /** Opens on the cloud already being priced -- the likeliest shelf. */
  cloud: "aws" | "gcp" | "azure";
}) {
  const [tab, setTab] = useState<IconEntry["provider"]>(cloud);
  const [query, setQuery] = useState("");

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    // A search runs across ALL providers. Someone typing "kubernetes" wants
    // EKS, GKE and AKS side by side -- that comparison is the product's whole
    // subject, and confining the search to one tab would hide it.
    const pool = q
      ? [...ICON_CATALOG, ...GROUP_ICONS]
      : tab === "group"
        ? GROUP_ICONS
        : ICON_CATALOG.filter((entry) => entry.provider === tab);
    if (!q) return pool;
    return pool.filter(
      (entry) =>
        entry.name.toLowerCase().includes(q) || entry.id.toLowerCase().includes(q),
    );
  }, [query, tab]);

  return (
    <div className="pointer-events-auto flex h-full w-[290px] flex-col rounded-xl border border-line bg-surface/95 shadow-lg backdrop-blur">
      <div className="flex items-center gap-2 border-b border-line px-3 py-2.5">
        <h2 className="flex-1 text-[13px] font-semibold text-ink">Add a service</h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close palette"
          className="rounded p-1 text-ink-3 transition-colors hover:bg-sunk hover:text-ink"
        >
          <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" aria-hidden>
            <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
          </svg>
        </button>
      </div>

      <div className="px-3 pt-2.5">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search all clouds…"
          className="w-full rounded-lg border border-line bg-canvas px-2.5 py-1.5 text-[12.5px] text-ink outline-none placeholder:text-ink-3 focus:border-accent-line focus:ring-2 focus:ring-accent-wash"
        />
      </div>

      {/* Hidden while searching: the tabs filter by provider and the search
          deliberately does not, so leaving them lit would show a selected AWS
          tab above a list containing Azure results. */}
      {!query.trim() && (
        <div className="flex gap-1 px-3 pt-2">
          {TABS.map((entry) => (
            <button
              key={entry.id}
              type="button"
              onClick={() => setTab(entry.id)}
              className={`rounded-md px-2 py-1 text-[11.5px] font-medium transition-colors ${
                tab === entry.id
                  ? "bg-accent text-white"
                  : "text-ink-3 hover:bg-sunk hover:text-ink-2"
              }`}
            >
              {entry.label}
            </button>
          ))}
        </div>
      )}

      <div className="mt-2 min-h-0 flex-1 overflow-y-auto px-2 pb-2">
        {results.length === 0 ? (
          <p className="px-2 py-6 text-center text-[12.5px] text-ink-3">
            No mark for “{query}”. It may not be one of the 147 vendored yet.
          </p>
        ) : (
          <ul className="grid grid-cols-1 gap-0.5">
            {results.map((entry) => (
              <li key={entry.id}>
                <button
                  type="button"
                  onClick={() => onPick(entry)}
                  className="flex w-full items-center gap-2.5 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-sunk"
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={entry.icon} alt="" className="h-6 w-6 shrink-0 object-contain" />
                  <span className="min-w-0 flex-1 truncate text-[12.5px] text-ink-2">
                    {entry.name}
                  </span>
                  {/* Only while searching, when the list is mixed and the
                      provider is the thing distinguishing two identical rows. */}
                  {query.trim() && (
                    <span className="shrink-0 font-mono text-[10px] uppercase text-ink-3">
                      {entry.provider}
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
