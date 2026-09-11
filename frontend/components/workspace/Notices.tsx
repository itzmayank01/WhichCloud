"use client";

import { money, type Option, type Recommendation } from "@/lib/api";

/**
 * Everything qualifying the number above, in one band.
 *
 * These used to be three separate full-wash amber panels stacked down the
 * rail. Any two of them together made a block of colour taller and louder
 * than the price it was qualifying, and because they all looked identical
 * there was no way to tell "this total is short a component" (the figure is
 * wrong) from "this shape fails your brief" (the figure is right and the
 * architecture is not) from "you have headroom" (nothing is wrong at all).
 *
 * So: one band, a severity stripe per notice, and the fill dropped. A left
 * rule carries the same signal at a fraction of the visual weight, which
 * leaves the price the loudest thing on the panel -- as it should be, since
 * it is the answer. The colour then means something when it appears.
 */

type Level = "blocking" | "caution" | "note";

const STRIPE: Record<Level, string> = {
  blocking: "border-l-caution",
  caution: "border-l-caution/50",
  note: "border-l-line-strong",
};

const TITLE: Record<Level, string> = {
  blocking: "text-caution",
  caution: "text-caution",
  note: "text-ink-2",
};

function Notice({
  level,
  title,
  children,
}: {
  level: Level;
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <div className={`border-l-2 pl-2.5 ${STRIPE[level]}`}>
      <p className={`text-[12px] font-semibold leading-snug ${TITLE[level]}`}>
        {title}
      </p>
      {children && (
        <div className="mt-1 space-y-1 text-[12px] leading-relaxed text-ink-2">
          {children}
        </div>
      )}
    </div>
  );
}

export function Notices({
  option,
  result,
  cheapestCompliantCost,
  onSelectOption,
}: {
  option: Option;
  result: Recommendation | null;
  cheapestCompliantCost: number | null;
  onSelectOption?: (label: string) => void;
}) {
  const unmet = !option.compliant;
  const incomplete = !option.complete;
  const saturated = option.budget_saturated;

  if (!unmet && !incomplete && !saturated) return null;

  return (
    <div className="mt-3 flex flex-col gap-2.5 border-t border-line pt-3">
      {/* Ordered by how much they change the decision, not by severity of
          tone. A shape that fails the brief is the one thing that should stop
          someone reading further, so it leads. */}
      {unmet && (
        <Notice level="blocking" title="Does not meet what you asked for">
          <ul className="space-y-1">
            {option.unmet.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
          {result?.cheapest_compliant ? (
            <p>
              <button
                type="button"
                onClick={() => onSelectOption?.(result.cheapest_compliant!)}
                className="font-semibold text-accent underline underline-offset-2"
              >
                {result.cheapest_compliant}
              </button>{" "}
              is the cheapest shape that does
              {cheapestCompliantCost != null && (
                <>
                  , at{" "}
                  <span className="tnum font-mono font-semibold">
                    {money(cheapestCompliantCost)}/mo
                  </span>
                </>
              )}
              .
            </p>
          ) : (
            <p>
              Nothing here meets it at this budget. That is a fact about the
              budget, not a reason to ship a single point of failure.
            </p>
          )}
        </Notice>
      )}

      {incomplete && (
        <Notice
          level="caution"
          title={`${option.missing.length} component${
            option.missing.length === 1 ? "" : "s"
          } could not be priced`}
        >
          <p>This total is a floor, not the answer.</p>
        </Notice>
      )}

      {/* A note, not a warning. Nothing is wrong -- the workload simply cannot
          use more money -- and dressing that as caution was telling people off
          for having budget left. */}
      {saturated && (
        <Notice level="note" title="Sized to what this workload can use">
          <p>A higher budget won&apos;t add useful capacity; the rest is headroom.</p>
        </Notice>
      )}
    </div>
  );
}
