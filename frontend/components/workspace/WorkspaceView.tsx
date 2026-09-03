"use client";

import { useState } from "react";
import {
  api,
  money,
  type Option,
  type Recommendation,
} from "@/lib/api";
import { ArchitectureGraph } from "@/components/architecture/ArchitectureGraph";
import { CostRail } from "@/components/workspace/CostRail";

/**
 * The workspace, canvas-first.
 *
 * The old layout stacked everything down one page: describe, three cards, a
 * chart, a table, then the diagram last — so the architecture, which is the
 * thing being recommended, was the part you had to scroll furthest to reach
 * and the part that got the least room.
 *
 * This inverts it. The diagram is the stage and holds the full height of the
 * viewport; the rail beside it carries what the diagram cannot say — the
 * description that produced it, what it costs, and why each choice was made.
 * Switching options repaints the canvas rather than moving the page.
 */

const EXAMPLE =
  "I run operations for a retail chain in India with 40 stores. We want to " +
  "move our stock and billing system online so staff can use it from any " +
  "store and head office can see live numbers. Around 300 staff use it " +
  "daily and we do about 8,000 transactions a day. It must not go down " +
  "during business hours because billing stops. Budget is around $500 a month.";

/** Which option to put forward, and why. Unchanged from the previous
 *  workspace — the reasoning is sound, only its presentation moved. */
function recommend(options: Option[]): { pick: Option; because: string } | null {
  const complete = options.filter((o) => o.complete);
  const usable = complete.length ? complete : options;
  if (usable.length === 0) return null;

  if (!complete.length) {
    const cheapest = usable.reduce((a, b) =>
      a.monthly_usd <= b.monthly_usd ? a : b,
    );
    return {
      pick: cheapest,
      because:
        "Every option here is missing components the catalog cannot price " +
        "in this region, so these totals are floors rather than answers.",
    };
  }

  const affordable = usable.filter((o) => o.within_budget !== false);
  if (affordable.length === 0) {
    const cheapest = usable.reduce((a, b) =>
      a.monthly_usd <= b.monthly_usd ? a : b,
    );
    return {
      pick: cheapest,
      because:
        "Nothing here fits the budget given. This is the least expensive " +
        "option that still runs the workload.",
    };
  }

  const pick = affordable.reduce((a, b) =>
    a.monthly_usd >= b.monthly_usd ? a : b,
  );
  return {
    pick,
    because:
      pick.label === "Most reliable"
        ? "It fits the budget and survives an availability-zone failure."
        : "It fits the budget with room to spare, and handles the expected peak.",
  };
}

function DownloadTerraformButton({
  description,
  option,
}: {
  description: string;
  option: string;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function download() {
    setBusy(true);
    setError("");
    try {
      const blob = await api.describeExportTf({ description, option });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "whichcloud-terraform.zip";
      link.click();
      URL.revokeObjectURL(url);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Export failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={download}
        disabled={busy}
        title="Download this architecture as a Terraform project"
        className="inline-flex items-center gap-1.5 rounded-lg border border-line-strong bg-surface px-3 py-1.5 text-[12.5px] font-medium text-ink transition-colors hover:bg-sunk disabled:opacity-60"
      >
        <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <path d="M10 3v10m0 0l-3.5-3.5M10 13l3.5-3.5M3.5 16h13" />
        </svg>
        {busy ? "Generating…" : "Terraform"}
      </button>
      {error && <span className="text-[12px] text-spend">{error}</span>}
    </>
  );
}

export function WorkspaceView({ name }: { name: string | null }) {
  const [description, setDescription] = useState("");
  const [asked, setAsked] = useState("");
  const [result, setResult] = useState<Recommendation | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  /* Bumped on every replay press. It is the canvas's React key, so a press
     remounts it and the build-in animation runs again from the first node --
     the animation is a mount effect, and without a new key there is nothing
     to re-trigger. */
  const [replay, setReplay] = useState(0);

  async function ask() {
    const text = description.trim() || EXAMPLE;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const answer = await api.describe({ description: text });
      setResult(answer);
      setAsked(text);
      setSelected(
        recommend(answer.options)?.pick.label ?? answer.options[0]?.label ?? null,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not read that description");
    } finally {
      setBusy(false);
    }
  }

  const advice = result ? recommend(result.options) : null;
  const shown = result?.options.find((o) => o.label === selected) ?? null;

  // Built once and rendered in both places -- floating over the pane, and
  // again inside the full-page overlay. Going full page should not cost you
  // the ability to replay the build or pull the Terraform for what you are
  // looking at.
  const actionBar = shown ? (
    <div className="flex items-center gap-2 rounded-xl border border-line bg-surface/95 px-3 py-2 shadow-lg backdrop-blur">
      <button
        type="button"
        onClick={() => setReplay((n) => n + 1)}
        title="Replay the build animation"
        className="inline-flex items-center gap-1.5 rounded-lg border border-line-strong bg-surface px-3 py-1.5 text-[12.5px] font-medium text-ink transition-colors hover:bg-sunk"
      >
        <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="currentColor" aria-hidden>
          <path d="M6.5 4.5v11l9-5.5z" />
        </svg>
        Replay
      </button>
      <span className="h-4 w-px bg-line" aria-hidden />
      <DownloadTerraformButton description={asked} option={shown.label} />
      <span className="h-4 w-px bg-line" aria-hidden />
      <span className="px-1 font-mono text-[11.5px] text-ink-3">
        {shown.topology.nodes.length} services · {shown.region}
      </span>
    </div>
  ) : null;

  return (
    /* The header is 64px and sticky; the workspace takes what is left, so the
       canvas is sized by the viewport rather than by its own content. */
    <div className="flex h-[calc(100vh-4rem)] flex-col overflow-hidden">
      {/* ── option switcher ───────────────────────────────────────────── */}
      <div className="flex shrink-0 items-center gap-4 border-b border-line bg-surface px-5 py-2.5">
        <span className="shrink-0 font-mono text-[10.5px] uppercase tracking-[0.12em] text-ink-3">
          Workspace
        </span>
        {result && result.options.length > 0 ? (
          <div className="flex min-w-0 flex-1 items-center gap-1.5 overflow-x-auto">
            {result.options.map((option) => {
              const active = option.label === selected;
              const recommended = option.label === advice?.pick.label;
              return (
                <button
                  key={option.label}
                  onClick={() => setSelected(option.label)}
                  className={`group flex shrink-0 items-center gap-2 rounded-lg border px-3 py-1.5 transition-all ${
                    active
                      ? "border-accent bg-accent-wash shadow-sm"
                      : "border-line bg-canvas hover:border-line-strong hover:bg-sunk"
                  }`}
                >
                  <span
                    className={`text-[13px] font-semibold ${active ? "text-ink" : "text-ink-2"}`}
                  >
                    {option.label}
                  </span>
                  <span className="tnum font-mono text-[13px] font-semibold text-ink">
                    {money(option.monthly_usd)}
                  </span>
                  {recommended && (
                    <span className="rounded-full bg-save px-1.5 py-px font-mono text-[9px] font-bold uppercase tracking-wide text-white">
                      pick
                    </span>
                  )}
                  {!option.complete && (
                    <span
                      className="h-1.5 w-1.5 rounded-full bg-caution"
                      title={`${option.missing.length} components unpriced`}
                    />
                  )}
                </button>
              );
            })}
          </div>
        ) : (
          <p className="flex-1 truncate text-[13px] text-ink-3">
            {name ? `Welcome back, ${name} — describe what you're building.` : "Describe what you're building."}
          </p>
        )}
      </div>

      {/* ── rail + canvas ─────────────────────────────────────────────── */}
      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <CostRail
          description={description}
          setDescription={setDescription}
          onAsk={ask}
          onUseExample={() => setDescription(EXAMPLE)}
          busy={busy}
          error={error}
          result={result}
          option={shown}
          because={advice?.because ?? null}
        />

        {/* canvas — the stage */}
        <main className="relative min-h-0 flex-1 bg-sunk">
          {shown?.topology?.nodes?.length ? (
            <>
              <div className="h-full overflow-hidden">
                {/* Keyed on option + replay counter so switching tiers or
                    pressing replay rebuilds the diagram (and its ELK layout)
                    from scratch rather than silently swapping node positions
                    under a finished animation. */}
                <ArchitectureGraph
                  graphKey={`${shown.label}-${replay}`}
                  nodes={shown.topology.nodes}
                  edges={shown.topology.edges}
                  playing
                  overlayFooter={actionBar}
                  overlayHeader={
                    result && result.options.length > 0 ? (
                      /* Tier switcher travels into the overlay so the three
                         options can be compared full-page without exiting. */
                      <div className="flex items-center gap-1.5 rounded-xl border border-line bg-surface/95 p-1.5 shadow-lg backdrop-blur">
                        {result.options.map((option) => (
                          <button
                            key={option.label}
                            onClick={() => setSelected(option.label)}
                            className={`flex shrink-0 items-center gap-2 rounded-lg border px-3 py-1.5 transition-all ${
                              option.label === selected
                                ? "border-accent bg-accent-wash shadow-sm"
                                : "border-line bg-canvas hover:border-line-strong hover:bg-sunk"
                            }`}
                          >
                            <span className="text-[13px] font-semibold text-ink">
                              {option.label}
                            </span>
                            <span className="tnum font-mono text-[13px] font-semibold text-ink">
                              {money(option.monthly_usd)}
                            </span>
                          </button>
                        ))}
                      </div>
                    ) : null
                  }
                />
              </div>

              {/* action bar, floating over the canvas */}
              <div className="pointer-events-none absolute inset-x-0 bottom-0 flex justify-center p-4">
                <div className="pointer-events-auto">{actionBar}</div>
              </div>
            </>
          ) : (
            <div className="grid h-full place-items-center p-8">
              <div className="max-w-sm text-center">
                {busy ? (
                  <>
                    <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-line border-t-accent" />
                    <p className="mt-4 text-[14px] text-ink-2">
                      Pricing your architecture…
                    </p>
                    <p className="mt-1 text-[12.5px] text-ink-3">
                      Reading the description, then costing every service
                      against the live catalog.
                    </p>
                  </>
                ) : result && shown ? (
                  <p className="text-[14px] text-ink-3">
                    Diagram not available for {shown.label} — only AWS
                    architectures are drawn today.
                  </p>
                ) : (
                  <>
                    <svg viewBox="0 0 48 48" className="mx-auto h-12 w-12 text-ink-3/40" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
                      <rect x="6" y="10" width="36" height="28" rx="3" />
                      <rect x="12" y="16" width="9" height="7" rx="1.5" />
                      <rect x="27" y="16" width="9" height="7" rx="1.5" />
                      <rect x="19.5" y="27" width="9" height="7" rx="1.5" />
                      <path d="M16.5 23v2.5h15V23M24 25.5V27" />
                    </svg>
                    <p className="mt-4 text-[14.5px] font-medium text-ink-2">
                      Your architecture appears here
                    </p>
                    <p className="mt-1.5 text-[13px] leading-relaxed text-ink-3">
                      Describe what you&apos;re building in the panel on the
                      left. You get a priced AWS architecture, drawn from the
                      same estimate as the bill.
                    </p>
                  </>
                )}
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
