"use client";

import { useState } from "react";
import {
  api,
  money,
  CLOUDS,
  type CloudId,
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

  // A recommendation that does not meet the brief is not a recommendation.
  // The cheapest way to serve traffic is always one machine and one database,
  // so on a workload whose owner wrote that it cannot go down, the cheapest
  // option is both the lowest number here AND the one that fails the
  // requirement. Without this filter it could be put forward as the pick,
  // with "it fits the budget with room to spare" written underneath.
  const meets = usable.filter((o) => o.compliant);
  const candidates = meets.length ? meets : usable;

  const affordable = candidates.filter((o) => o.within_budget !== false);
  if (affordable.length === 0) {
    const cheapest = candidates.reduce((a, b) =>
      a.monthly_usd <= b.monthly_usd ? a : b,
    );
    return {
      pick: cheapest,
      because: meets.length
        ? "Nothing here fits the budget given. This is the least expensive " +
          "option that still meets what you asked for."
        : "Nothing here both fits the budget and meets what you asked for. " +
          "This is the least expensive option that runs the workload — see " +
          "what it does not meet, below.",
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
  cloud,
}: {
  description: string;
  option: string;
  cloud: CloudId;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function download() {
    setBusy(true);
    setError("");
    try {
      // The provider travels with the request. Without it the route fell
      // back to the description's stated preference -- almost always unset --
      // and handed out AWS resources to someone looking at a Google Cloud or
      // Azure architecture.
      const blob = await api.describeExportTf({ description, option, provider: cloud });
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
      {/* Disabled off AWS rather than left to fail on click. The export
          generates AWS resources only, and a button that looks available and
          then errors is a worse answer than one that says up front what it
          can do. */}
      <button
        type="button"
        onClick={download}
        disabled={busy || cloud !== "aws"}
        title={
          cloud === "aws"
            ? "Download this architecture as a Terraform project"
            : `Terraform export generates AWS resources only — this architecture is priced on ${cloud.toUpperCase()}`
        }
        className="inline-flex items-center gap-1.5 rounded-lg border border-line-strong bg-surface px-3 py-1.5 text-[12.5px] font-medium text-ink transition-colors hover:bg-sunk disabled:opacity-60"
      >
        <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <path d="M10 3v10m0 0l-3.5-3.5M10 13l3.5-3.5M3.5 16h13" />
        </svg>
        {busy ? "Generating…" : cloud === "aws" ? "Terraform" : "Terraform (AWS only)"}
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
  // Which cloud to price against. Null means "let the description decide",
  // which is the honest default: someone describing a retail chain has no
  // reason to have picked a cloud yet, and being made to choose one before
  // seeing a number is the opposite of what this tool is for.
  const [cloud, setCloud] = useState<CloudId | null>(null);

  // NOTE the guard on `overrideCloud`. This is passed to onAsk, and a click
  // handler receives the event as its first argument -- so an unguarded
  // parameter here became the provider, and a React synthetic event went into
  // the request body as one. It serialises to a circular structure through its
  // fibre, so the failure surfaced as "Converting circular structure to JSON"
  // rather than as anything to do with clouds.
  async function ask(overrideCloud?: CloudId | null | unknown) {
    const text = description.trim() || EXAMPLE;
    const picked =
      overrideCloud === null ||
      overrideCloud === "aws" ||
      overrideCloud === "gcp" ||
      overrideCloud === "azure"
        ? (overrideCloud as CloudId | null)
        : undefined;
    const provider = picked === undefined ? cloud : picked;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const answer = await api.describe({
        description: text,
        ...(provider ? { provider } : {}),
      });
      setResult(answer);
      setAsked(text);
      // The backend decides when we sent nothing, so read the provider back
      // rather than assuming ours won.
      setCloud(answer.provider);
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
  // Tier chips and the pick both read the ON-DEMAND total, matching the
  // headline. Comparing one tier's committed price against another's
  // on-demand would rank them on a difference in commitment rather than in
  // architecture.
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
      <DownloadTerraformButton
        description={asked}
        option={shown.label}
        cloud={cloud ?? "aws"}
      />
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
        {/* Which cloud. Shown only once there is a result, because before that
            there is nothing to compare and the question is premature -- the
            product's job is to recommend a cloud, not to make someone pick one
            before they have seen a single number. */}
        {result && (
          <div className="flex shrink-0 items-center gap-1 rounded-lg border border-line bg-canvas p-0.5">
            {CLOUDS.map((c) => {
              const active = cloud === c.id;
              return (
                <button
                  key={c.id}
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    setCloud(c.id);
                    void ask(c.id);
                  }}
                  title={`Price this on ${c.name} — ${c.region}`}
                  className={`rounded-md px-2.5 py-1 text-[12px] font-semibold transition-colors disabled:opacity-50 ${
                    active
                      ? "bg-surface text-ink shadow-sm ring-1 ring-line-strong"
                      : "text-ink-3 hover:text-ink-2"
                  }`}
                >
                  {c.name}
                </button>
              );
            })}
          </div>
        )}
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
                    {money(option.ondemand_monthly_usd ?? option.monthly_usd)}
                  </span>
                  {recommended && (
                    <span className="rounded-full bg-save px-1.5 py-px font-mono text-[9px] font-bold uppercase tracking-wide text-white">
                      pick
                    </span>
                  )}
                  {/* An option that does not meet the brief must not read as a
                      peer of the ones that do. The cheapest architecture is
                      always one machine and one database, so on a workload
                      whose owner wrote "it must not go down" this tab was the
                      cheapest number on screen with nothing to say it fails
                      the requirement. */}
                  {!option.compliant && (
                    <span
                      className="rounded-full bg-caution px-1.5 py-px font-mono text-[9px] font-bold uppercase tracking-wide text-white"
                      title={option.unmet.join("\n\n")}
                    >
                      ⚠ unmet
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
          cloud={cloud ?? "aws"}
          description={description}
          setDescription={setDescription}
          onAsk={ask}
          onUseExample={() => setDescription(EXAMPLE)}
          busy={busy}
          error={error}
          result={result}
          option={shown}
          // Only under the option it is ABOUT. This sentence explains why
          // the pick was put forward; shown under every tier it read as a
          // verdict on whichever one was selected, so the cheapest option
          // carried "it fits the budget with room to spare" directly above
          // the notice saying it fails the requirement.
          because={
            advice && shown?.label === advice.pick.label ? advice.because : null
          }
          onSelectOption={setSelected}
        />

        {/* canvas — the stage.
            White, not the sunk grey. The diagram already draws its own
            boundaries as pale outlines on white, and a grey stage behind them
            put a second, stronger edge around the whole picture -- the eye
            reads that outer rectangle as part of the architecture. Reference
            architecture diagrams are published on white for the same reason. */}
        <main className="relative min-h-0 flex-1 bg-surface">
          {shown?.topology?.nodes?.length ? (
            <>
              <div className="h-full overflow-hidden">
                {/* Keyed on option + replay counter so switching tiers or
                    pressing replay rebuilds the diagram (and its ELK layout)
                    from scratch rather than silently swapping node positions
                    under a finished animation. */}
                <ArchitectureGraph
                  graphKey={`${shown.label}-${replay}-${cloud ?? "aws"}`}
                  cloud={cloud ?? "aws"}
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
                              {money(option.ondemand_monthly_usd ?? option.monthly_usd)}
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
