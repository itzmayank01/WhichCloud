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
 * The join key is `group`, which the API sets to the node KIND on every line
 * for exactly this purpose. This comment used to say there was no shared key
 * and that matching had to be done on the label -- which was wrong, and the
 * matching built on it failed on the largest line in most estimates.
 */
/** Every line belonging to this node.
 *
 *  Matched on `group`, which the API sets to the node KIND for exactly this
 *  purpose -- "so clicking a node can find its lines and clicking a line can
 *  find its node without a second mapping to keep in step".
 *
 *  This used to match on the label and it silently failed on the largest line
 *  in most estimates: the bill says "Database (Multi-AZ) (1-yr reserved)"
 *  where the diagram says "Database", so an exact match found nothing and the
 *  panel reported a $219 service as not billed at all. Matching prose against
 *  prose was the mistake; the join key already existed.
 *
 *  Returning all of them rather than the first is the other half. Object
 *  storage bills standard and infrequent-access separately, and a database
 *  its instance, its storage and its backups -- showing one line and calling
 *  it the cost understates the service.
 */
function linesFor(node: SelectedNode, option: Option | null) {
  if (!option) return [];
  if (node.kind) {
    const byGroup = option.items.filter((item) => item.group === node.kind);
    if (byGroup.length) return byGroup;
  }
  // Older payloads carry no group; fall back to the label match.
  const wanted = node.label.trim().toLowerCase();
  return option.items.filter(
    (item) => item.label.replace(/ ×.*$/, "").trim().toLowerCase() === wanted,
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
  const lines = linesFor(node, option);
  const total = lines.reduce((sum, l) => sum + l.monthly_usd, 0);

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

        {lines.length > 0 ? (
          <div className="flex flex-col gap-2 rounded-lg bg-sunk px-3 py-2.5">
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-[12px] text-ink-3">Monthly</span>
              <span className="tnum font-mono text-[15px] font-semibold text-ink">
                {money(total)}
              </span>
            </div>
            {/* Every line, not just the first. A database bills its instance,
                its storage and its backups; showing one and calling it the
                cost understates the service. The arithmetic is shown too --
                "730 × $0.167/hour" is what makes "$121.91" checkable against
                the provider's own page. */}
            {lines.map((line, i) => (
              <div
                key={`${line.sku}-${i}`}
                className="flex flex-col gap-0.5 border-t border-line pt-1.5"
              >
                <div className="flex items-baseline justify-between gap-2">
                  <span className="min-w-0 truncate text-[11.5px] text-ink-2">
                    {line.label}
                  </span>
                  <span className="tnum shrink-0 font-mono text-[11.5px] text-ink">
                    {money(line.monthly_usd)}
                  </span>
                </div>
                <div className="flex items-baseline justify-between gap-2">
                  <span className="tnum font-mono text-[10.5px] text-ink-3">
                    {line.quantity} × ${line.unit_price}/{line.unit}
                  </span>
                  {line.sku && (
                    <span className="truncate font-mono text-[10px] text-ink-3">
                      {line.sku}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : node.priced === false ? (
          /* A real gap: the catalog could not price this, so the total is
             short by whatever it costs. Amber, because the number on the left
             is wrong until it is resolved. */
          <p className="rounded-lg border border-caution/25 bg-caution-wash px-3 py-2 text-[12px] leading-relaxed text-caution">
            The catalog could not price this in this region, so the total on
            the left excludes it.
          </p>
        ) : (
          /* NOT a warning, and it must not look like one. A subnet, a route
             table or the end users are not billed separately -- that is how
             the cloud works, not a problem with the estimate. Amber here put a
             caution panel on the most ordinary fact in the diagram, which
             teaches people to discount the colour by the time it means
             something. */
          <p className="rounded-lg bg-sunk px-3 py-2 text-[12px] leading-relaxed text-ink-3">
            Not billed on its own — its cost sits inside another line.
          </p>
        )}
      </div>
    </div>
  );
}
