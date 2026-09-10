"use client";

import { money, type Option } from "@/lib/api";
import type { SelectedNode } from "@/components/architecture/ArchitectureGraph";

/**
 * What one box on the diagram costs, and why it is there.
 *
 * The diagram and the bill are two renderings of a single estimate, but until
 * now nothing connected them: a reader looking at a box labelled "Database"
 * had to find the matching row in a 380px column of line items themselves.
 * Clicking the box should answer the question the box raises.
 *
 * The match is by label rather than by id because the estimator's line items
 * and the topology's nodes are built from the same spec but not from the same
 * objects -- there is no shared key to join on. Labels carry a "× 3" suffix on
 * multi-instance lines, which is stripped here for the comparison and kept in
 * what is shown, since the count is part of what the reader is being told.
 */
function lineFor(node: SelectedNode, option: Option | null) {
  if (!option) return null;
  const wanted = node.label.trim().toLowerCase();
  return (
    option.items.find(
      (item) => item.label.replace(/ ×.*$/, "").trim().toLowerCase() === wanted,
    ) ?? null
  );
}

export function Inspector({
  node,
  option,
  onClose,
}: {
  node: SelectedNode;
  option: Option | null;
  onClose: () => void;
}) {
  const line = lineFor(node, option);

  return (
    <div className="pointer-events-auto w-[290px] rounded-xl border border-line bg-surface/95 shadow-lg backdrop-blur">
      <div className="flex items-start gap-2 border-b border-line px-3.5 py-2.5">
        <div className="min-w-0 flex-1">
          <p className="truncate text-[13.5px] font-semibold text-ink">
            {node.label}
          </p>
          {node.tier && (
            <p className="mt-0.5 font-mono text-[10.5px] uppercase tracking-wide text-ink-3">
              {node.tier}
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="-mr-1 rounded p-1 text-ink-3 transition-colors hover:bg-sunk hover:text-ink"
        >
          <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" aria-hidden>
            <path
              d="M4 4l8 8M12 4l-8 8"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
            />
          </svg>
        </button>
      </div>

      <div className="flex flex-col gap-2.5 px-3.5 py-3">
        {node.purpose && (
          <p className="text-[12.5px] leading-relaxed text-ink-2">
            {node.purpose}
          </p>
        )}

        {line ? (
          <div className="flex flex-col gap-1.5 rounded-lg bg-sunk px-3 py-2.5">
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-[12px] text-ink-3">Monthly</span>
              <span className="tnum font-mono text-[15px] font-semibold text-ink">
                {money(line.monthly_usd)}
              </span>
            </div>
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-[12px] text-ink-3">Rate</span>
              {/* The arithmetic, shown. "$121.91" is a conclusion; "730 ×
                  $0.167/hour" is the reason, and it is the reason that makes
                  the number checkable against a provider's own page. */}
              <span className="tnum font-mono text-[11.5px] text-ink-2">
                {line.quantity} × ${line.unit_price}/{line.unit}
              </span>
            </div>
            {line.sku && (
              <div className="flex items-baseline justify-between gap-2 border-t border-line pt-1.5">
                <span className="text-[12px] text-ink-3">SKU</span>
                <span className="truncate font-mono text-[11px] text-ink-2">
                  {line.sku}
                </span>
              </div>
            )}
          </div>
        ) : (
          /* Two different silences, kept apart. A component the catalog could
             not price is a hole in the total; one the estimator simply does
             not bill for (a subnet, a route table) is not. Collapsing them
             into "no price" would make a real gap look like a detail. */
          <p className="rounded-lg bg-caution-wash px-3 py-2 text-[12px] leading-relaxed text-caution">
            {node.priced === false
              ? "The catalog could not price this in this region, so the total on the left excludes it."
              : "Not billed on its own — its cost sits inside another line."}
          </p>
        )}
      </div>
    </div>
  );
}
