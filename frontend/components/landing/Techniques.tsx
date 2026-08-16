import { api, type Technique } from "@/lib/api";
import { Reveal } from "@/components/landing/Reveal";

/**
 * The eight optimizations, named.
 *
 * The stats band claims eight are tested and the page never said what they
 * were, which is the same unsupported-claim problem the provenance section
 * was built to fix, one layer up: prices are now shown with their working
 * while the techniques that act on those prices remained an assertion.
 *
 * Each one is printed with the thing it costs you and whether it can be
 * priced at all. Four of the eight cannot be -- their saving depends on a
 * workload's own read mix or idle pattern, which list rates do not contain --
 * and those are marked as advice rather than folded in with a plausible
 * number. That distinction is the project's rule, so it belongs on the page
 * rather than buried in the engine.
 */

const CONFIDENCE: Record<string, { label: string; className: string }> = {
  high: { label: "High confidence", className: "bg-save-wash text-save" },
  medium: { label: "Medium confidence", className: "bg-caution-wash text-caution" },
  low: { label: "Low confidence", className: "bg-sunk text-ink-3" },
};

function Card({ t }: { t: Technique }) {
  const c = CONFIDENCE[t.confidence] ?? CONFIDENCE.low;

  return (
    <div className="flex flex-col rounded-xl border border-line bg-surface p-5 elev-1 transition-shadow duration-300 hover:elev-3">
      <div className="flex items-center gap-2">
        <span className="font-mono text-[11.5px] uppercase tracking-[0.11em] text-ink-3">
          {t.category}
        </span>
        <span
          className={`ml-auto shrink-0 rounded-full px-2 py-0.5 font-mono text-[11px] font-medium ${c.className}`}
        >
          {c.label}
        </span>
      </div>

      <h3 className="mt-2.5 text-balance text-[16px] font-semibold leading-snug tracking-[-0.015em]">
        {t.name}
      </h3>
      <p className="mt-2 flex-1 text-[14px] leading-relaxed text-ink-2">{t.summary}</p>

      {/* Every technique states what it costs you. Printing the first one
          beside the claim keeps the two together; a saving shown on its own
          is the half of the story that sells. */}
      {t.tradeoffs.length > 0 && (
        <div className="mt-4 border-t border-line pt-3">
          <div className="font-mono text-[11px] uppercase tracking-[0.1em] text-ink-3">
            Costs you
          </div>
          <p className="mt-1.5 text-[13.5px] leading-relaxed text-ink-2">
            {t.tradeoffs[0]}
            {t.tradeoffs.length > 1 && (
              <span className="text-ink-3">
                {" "}
                and {t.tradeoffs.length - 1} more
              </span>
            )}
          </p>
        </div>
      )}

      <div className="mt-3.5 flex items-center gap-2 border-t border-line pt-3">
        <span className="font-mono text-[11px] uppercase tracking-[0.1em] text-ink-3">
          Uses
        </span>
        {t.tool_url ? (
          <a
            href={t.tool_url}
            target="_blank"
            rel="noopener noreferrer"
            className="truncate text-[13px] text-accent hover:underline"
          >
            {t.tool}
          </a>
        ) : (
          <span className="truncate text-[13px] text-ink-2">{t.tool}</span>
        )}
        <span
          className={`ml-auto shrink-0 font-mono text-[11px] ${
            t.priced ? "text-save" : "text-ink-3"
          }`}
          title={
            t.priced
              ? "Its effect is measured against live rates"
              : "Its saving depends on your workload, so it is offered as advice and never costed"
          }
        >
          {t.priced ? "priced" : "advice only"}
        </span>
      </div>
    </div>
  );
}

export async function Techniques() {
  let techniques: Technique[] = [];
  try {
    techniques = (await api.techniques()).techniques;
  } catch {
    return null; /* The section is the list; with no list there is nothing. */
  }
  if (techniques.length === 0) return null;

  const priced = techniques.filter((t) => t.priced).length;

  /* Priced first, then by confidence: the ones whose effect can actually be
     measured are the ones worth reading first, and sorting by name would
     scatter them through the grid at random. */
  const rank = { high: 0, medium: 1, low: 2 } as Record<string, number>;
  const ordered = [...techniques].sort(
    (a, b) =>
      Number(b.priced) - Number(a.priced) ||
      (rank[a.confidence] ?? 3) - (rank[b.confidence] ?? 3),
  );

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mx-auto mb-10 max-w-2xl text-center">
        <div className="font-mono text-[13.5px] uppercase tracking-[0.14em] text-accent font-medium">
          The techniques
        </div>
        <h2 className="mt-3 text-balance text-[clamp(1.75rem,3.6vw,2.5rem)] font-semibold leading-tight tracking-[-0.025em]">
          All {techniques.length}, and what each one costs you
        </h2>
        <p className="mt-4 text-[16px] leading-relaxed text-ink-2">
          Every optimization the engine tests, with its trade-offs and the real
          tool it uses. {priced} of the {techniques.length} can be priced
          against live rates. The rest depend on your own read mix or idle
          pattern, which list rates do not contain, so they are offered as
          advice and never costed with a number that would only look precise.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {ordered.map((t, i) => (
          <Reveal
            key={t.id}
            className="reveal-line flex"
            style={{ "--i": i % 4 } as React.CSSProperties}
          >
            <Card t={t} />
          </Reveal>
        ))}
      </div>
    </div>
  );
}
