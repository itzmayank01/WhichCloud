"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  api,
  money,
  CLOUDS,
  type CloudId,
  type Option,
  type Recommendation,
} from "@/lib/api";
import {
  ArchitectureGraph,
  type SelectedNode,
} from "@/components/architecture/ArchitectureGraph";
import { CostRail } from "@/components/workspace/CostRail";
import { TerraformLogo } from "@/components/Logo";
import { AskPanel } from "@/components/workspace/AskPanel";
import { Inspector } from "@/components/workspace/Inspector";
import { ToolIcons, ToolRail } from "@/components/workspace/ToolRail";
import { ServicePalette } from "@/components/workspace/ServicePalette";
import {
  SketchCanvas,
  type Command as SketchCommand,
  type Selection as SketchSelection,
  type SketchTool,
} from "@/components/workspace/SketchCanvas";
import { SketchInspector } from "@/components/workspace/SketchInspector";
import type { IconEntry } from "@/lib/iconCatalog";

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

/**
 * Starting points for the empty canvas.
 *
 * The workspace opened on an icon and two lines of text in the middle of an
 * otherwise empty two-thirds of the viewport -- which asks the one question
 * a first-time user cannot answer ("what should I type?") and gives them a
 * blank box to answer it in. These are the same shapes the engine is built
 * around, written the way somebody actually describes their own system, so
 * one click produces a real priced architecture instead of a cold start.
 *
 * They are deliberately NOT auto-submitted: the text lands in the box so it
 * can be edited into the reader's own numbers first, which is the point of
 * a description-driven tool.
 */
/*
 * EVERY ENTRY HERE MUST CLASSIFY AND PRICE. That is not a style note.
 *
 * The engine refuses to price a description it cannot place in one of the
 * seven implemented archetypes (whichcloud/archetype.py), and refuses again
 * if a stated quantity could not be read. A starter is therefore not just
 * copy -- it is a claim that this exact text produces an architecture, and
 * the only way to know is to run it.
 *
 * The first draft of this list did not do that, and shipped two that broke:
 * a "consumer mobile app" that matched no archetype phrase at all and
 * refused outright, and an "internal reporting system" that priced only by
 * accidentally matching 'billing system' -- so a nightly batch workload was
 * being drawn as a web app. A starter that misclassifies is worse than one
 * that refuses, because nothing on screen says it went wrong.
 *
 * Each of the three below was checked end to end against the live engine:
 * the archetype it lands in is the one its title claims, and /describe
 * returns three priced options. Re-check with the same two steps before
 * adding or rewording any of them -- a reworded phrase can silently drop
 * the signal the classifier matched on.
 */
const STARTERS: { title: string; note: string; text: string }[] = [
  {
    // web_app — 4 phrase matches. Already the shipped EXAMPLE.
    title: "Retail chain going online",
    note: "40 stores · 300 staff · must not go down in business hours",
    text: EXAMPLE,
  },
  {
    // batch_etl — matches 'overnight', 'next-day reports', 'nobody uses it
    // during the day'. Deliberately states no head-count: "a team of 25"
    // reads as a quantity the planner then refuses to guess around.
    title: "Overnight reporting pipeline",
    note: "Loads nightly · next-day reports · idle during the day",
    text:
      "Our sales data is loaded overnight from the till systems into a " +
      "reporting database, and the finance team reads next-day reports each " +
      "morning. Nobody uses it during the day. We keep about 2 TB of " +
      "history. Budget is around $600 a month.",
  },
  {
    // static_site — matches 'marketing site', 'just pages and images',
    // 'no login', 'no database'. Prices at a few dollars, which is the
    // useful end of the range to show next to the other two.
    title: "Marketing site",
    note: "Just pages and images · no login · no database",
    text:
      "We need a marketing site for our product — just pages and images, no " +
      "login and no database. It should load fast for visitors in India and " +
      "the UK. Budget is around $50 a month.",
  },
];

/** Which option to put forward, and why. Unchanged from the previous
 *  workspace — the reasoning is sound, only its presentation moved. */
function recommend(
  options: Option[],
  budgetMonthlyUsd?: number | null,
): { pick: Option; because: string } | null {
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

  let because = "";
  if (budgetMonthlyUsd && budgetMonthlyUsd > 0) {
    const usedPct = (pick.monthly_usd / budgetMonthlyUsd) * 100;
    const leftUsd = Math.max(0, budgetMonthlyUsd - pick.monthly_usd);
    const leftFormatted = "$" + Math.round(leftUsd).toLocaleString();
    /* OVER BUDGET IS ITS OWN ANSWER, AND IT HAS TO COME FIRST.
       `leftUsd` clamps at zero, and the branches below only ever asked what
       PERCENTAGE of the budget was used -- so a design costing $5,145
       against a $600 budget fell into `usedPct > 90` and reported "uses most
       of your budget ($0/mo left)". It had overrun it by $4,545. A costing
       tool that cannot say a design is over budget is failing at its one
       job, and saying "$0 left" is worse than saying nothing: it reads as
       having just fit. */
    if (pick.monthly_usd > budgetMonthlyUsd) {
      const over = "$" + Math.round(pick.monthly_usd - budgetMonthlyUsd).toLocaleString();
      because =
        `Over your budget by ${over}/mo — this costs ` +
        `$${Math.round(pick.monthly_usd).toLocaleString()}/mo against a ` +
        `$${Math.round(budgetMonthlyUsd).toLocaleString()}/mo budget. ` +
        `Your stated requirements set the floor; a cheaper design means ` +
        `relaxing one of them.`;
    } else if (usedPct < 50) {
      because = `Well within budget (${leftFormatted}/mo unallocated). You can add resilience or reserve this for growth.`;
    } else if (usedPct > 90) {
      because = `Uses most of your budget (${leftFormatted}/mo left). Designed for your stated uptime needs.`;
    } else {
      because = `Fits the budget with room to spare (${leftFormatted}/mo left), and handles the expected peak.`;
    }
  } else {
    because =
      pick.label === "Most reliable"
        ? "It fits the budget and survives an availability-zone failure."
        : "Fits the budget with room to spare, and handles the expected peak.";
  }

  return {
    pick,
    because,
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
  const text = description || EXAMPLE;
  const params = new URLSearchParams();
  if (text) params.set("description", text);
  if (option) params.set("option", option);
  if (cloud) params.set("cloud", cloud);
  const targetUrl = `/terraform?${params.toString()}`;

  return (
    <Link
      href={targetUrl}
      onClick={(e) => {
        // Guarantee hard navigation even if client-side SPA router is cached
        if (typeof window !== "undefined") {
          window.location.href = targetUrl;
        }
      }}
      title="Open Terraform IaC Configuration & Architecture Studio"
      className="inline-flex items-center gap-1.5 rounded-lg border border-line-strong bg-surface px-3 py-1.5 text-[12.5px] font-medium text-ink transition-all hover:bg-sunk hover:border-brand hover:text-brand"
    >
      <TerraformLogo className="h-3.5 w-3.5" />
      <span>Terraform</span>
    </Link>
  );
}

/** What the progress line below counts toward, in seconds.
 *
 *  Not decoration: the backend abandons the model read at EXTRACT_BUDGET_S
 *  (14s in intake.py) and pricing the result measures ~0.5s, so a generate
 *  either lands inside this or fails with a message. Keep the two numbers
 *  together -- a bar that fills toward a deadline the server does not
 *  actually enforce is worse than no bar at all. */
const GENERATE_BUDGET_S = 15;

export function WorkspaceView({ name }: { name: string | null }) {
  const [description, setDescription] = useState("");
  const [asked, setAsked] = useState("");
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);
  const [result, setResult] = useState<Recommendation | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const reqIdRef = useRef(0);
  /* Seconds spent on the current generate, for the progress line below.
     The backend caps the read at 14s and pricing costs well under a second,
     so GENERATE_BUDGET_S is a real ceiling rather than a guess -- which is
     what lets the bar be determinate instead of an indefinite spinner that
     says nothing about how much longer it will be. */
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!busy) {
      setElapsed(0);
      return;
    }
    const started = Date.now();
    const id = setInterval(() => setElapsed((Date.now() - started) / 1000), 100);
    return () => clearInterval(id);
  }, [busy]);
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
  /** The component whose box was last clicked, or null for none. */
  const [inspected, setInspected] = useState<SelectedNode | null>(null);
  const [asking, setAsking] = useState(false);
  /* Sketch mode. Separate from `asking` because they are not alternatives:
     rearranging the diagram and asking about it are both things a person does
     while looking at the same architecture. */
  const [sketching, setSketching] = useState(false);
  const [palette, setPalette] = useState(false);
  const [pending, setPending] = useState<IconEntry | null>(null);
  const [tool, setTool] = useState<SketchTool>("select");
  const [seedToken, setSeedToken] = useState(0);
  const [picked, setPicked] = useState<SketchSelection | null>(null);
  const [command, setCommand] = useState<SketchCommand | null>(null);

  // Seed only the saved workload text & cloud preference on mount — never restore stale architecture results
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const cachedDesc = sessionStorage.getItem("whichcloud:active_description");
      const cachedCloud = sessionStorage.getItem("whichcloud:active_cloud") as CloudId | null;
      if (cachedDesc) setDescription(cachedDesc);
      if (cachedCloud === "aws" || cachedCloud === "gcp" || cachedCloud === "azure") {
        setCloud(cachedCloud);
      }
    } catch {
      // ignore
    }
  }, []);

  // NOTE the guard on `overrideCloud`. This is passed to onAsk, and a click
  // handler receives the event as its first argument -- so an unguarded
  // parameter here became the provider, and a React synthetic event went into
  // the request body as one. It serialises to a circular structure through its
  // fibre, so the failure surfaced as "Converting circular structure to JSON"
  // rather than as anything to do with clouds.
  async function ask(overrideCloud?: CloudId | null | unknown) {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const reqId = ++reqIdRef.current;

    const text = description.trim() || EXAMPLE;
    const picked =
      overrideCloud === null ||
        overrideCloud === "aws" ||
        overrideCloud === "gcp" ||
        overrideCloud === "azure"
        ? (overrideCloud as CloudId | null)
        : undefined;
    const provider = (picked === undefined ? cloud : picked) ?? "aws";
    setBusy(true);
    setError(null);
    setResult(null);
    setSelected(null);
    setGeneratedAt(null);

    try {
      const answer = await api.describe(
        {
          description: text,
          provider,
        },
        controller.signal,
      );
      if (controller.signal.aborted || reqId !== reqIdRef.current) return;

      setResult(answer);
      setAsked(text);
      setGeneratedAt(
        new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        }),
      );
      setCloud(answer.provider || provider);
      setSelected(
        recommend(answer.options, answer.budget_monthly_usd)?.pick.label ??
          answer.options[0]?.label ??
          null,
      );
      if (typeof window !== "undefined") {
        try {
          sessionStorage.setItem("whichcloud:active_description", text);
          sessionStorage.setItem("whichcloud:active_cloud", answer.provider || provider);
        } catch {
          // ignore session quota
        }
      }
    } catch (err: unknown) {
      if (controller.signal.aborted || reqId !== reqIdRef.current) return;
      setResult(null);
      setError(
        err instanceof Error
          ? err.message
          : "Could not price this workload. Please check the backend connection and try again.",
      );
    } finally {
      if (!controller.signal.aborted && reqId === reqIdRef.current) {
        setBusy(false);
      }
    }
  }

  const advice = result ? recommend(result.options, result.budget_monthly_usd) : null;
  const shown = result?.options.find((o) => o.label === selected) ?? null;

  /* Clear the inspector when the thing it describes is replaced. Each tier
     draws its own boxes, so a panel opened on "Database" under Most reliable
     kept describing a multi-AZ line after a switch to Cheapest, where that
     component does not exist -- the numbers stayed on screen and simply
     stopped being true of anything. */
  useEffect(() => {
    setInspected(null);
  }, [selected, cloud]);

  /* Escape releases an armed drawing tool first, and closes the sketch only
     when nothing is armed -- so it also means "never mind" to a box you were
     about to place, rather than throwing away the whole session on the way.
     Bound on the window rather than the canvas: focus after a drag sits on
     whichever node was moved, and a handler on the pane would not see it. */
  useEffect(() => {
    if (!sketching) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (tool !== "select") setTool("select");
      else {
        setSketching(false);
        setPalette(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [sketching, tool]);

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
      {/* This bar is the only home for these now. It renders in the pane AND
          inside the full-page overlay, so both views reach the same controls
          and neither needs a floating rail of its own. */}
      <button
        type="button"
        onClick={() => setAsking((open) => !open)}
        title="Ask about this architecture"
        className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-[12.5px] font-medium transition-colors ${asking
            ? "border-accent bg-accent text-canvas"
            : "border-line-strong bg-surface text-ink hover:bg-sunk"
          }`}
      >
        <span className="h-3.5 w-3.5">{ToolIcons.ask}</span>
        Ask
      </button>
      <span className="h-4 w-px bg-line" aria-hidden />
      <button
        type="button"
        onClick={() => {
          // Straight to full screen. Rearranging is the reason someone opens
          // this, and dropping them into the narrow pane to press a second
          // expand button is a step that exists only because the state does.
          setSketching(true);
          setAsking(false);
          setInspected(null);
        }}
        title="Rearrange this diagram full screen"
        className="inline-flex items-center gap-1.5 rounded-lg border border-line-strong bg-surface px-3 py-1.5 text-[12.5px] font-medium text-ink transition-colors hover:bg-sunk"
      >
        <span className="h-3.5 w-3.5">{ToolIcons.edit}</span>
        Rearrange
      </button>
      <span className="h-4 w-px bg-line" aria-hidden />
      <DownloadTerraformButton
        description={asked || description || EXAMPLE}
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
                  className={`rounded-md px-2.5 py-1 text-[12px] font-semibold transition-colors disabled:opacity-50 ${active
                      ? "bg-surface text-ink shadow-sm ring-1 ring-line-strong"
                      : "text-ink-3 hover:text-ink-2"
                    }`}
                >
                  {c.name}
                </button>
              );
            })}
            {generatedAt && asked && (
              <span
                data-testid="generated-for-stamp"
                className="ml-auto hidden xl:inline-block truncate max-w-[340px] rounded-md bg-sunk px-2 py-1 font-mono text-[11px] text-ink-3"
                title={`Generated for: ${asked} at ${generatedAt}`}
              >
                Generated for: {asked.slice(0, 60)}
                {asked.length > 60 ? "…" : ""} at {generatedAt}
              </span>
            )}
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
                  className={`group flex shrink-0 items-center gap-2 rounded-lg border px-3 py-1.5 transition-all ${active
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
                    <span className="rounded-full bg-save px-1.5 py-px font-mono text-[9px] font-bold uppercase tracking-wide text-canvas">
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
                      className="rounded-full bg-caution px-1.5 py-px font-mono text-[9px] font-bold uppercase tracking-wide text-canvas"
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
            {generatedAt && asked && (
              <span
                data-testid="generated-for-stamp"
                className="ml-auto hidden xl:inline-block truncate max-w-[340px] rounded-md bg-sunk px-2 py-1 font-mono text-[11px] text-ink-3"
                title={`Generated for: ${asked} at ${generatedAt}`}
              >
                Generated for: {asked.slice(0, 60)}
                {asked.length > 60 ? "…" : ""} at {generatedAt}
              </span>
            )}
          </div>
        ) : (
          <div className="flex flex-1 items-center justify-between">
            <p className="truncate text-[13px] text-ink-3">
              {name ? `Welcome back, ${name} — describe what you're building.` : "Describe what you're building."}
            </p>
            <a
              href="/finops"
              className="hidden sm:inline-flex items-center gap-1.5 rounded-lg border border-accent/30 bg-accent/10 px-3 py-1 text-[12px] font-semibold text-accent hover:bg-accent/20 transition-all"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse" />
              <span>Live FinOps Cockpit →</span>
            </a>
          </div>
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
        {/* Sketch mode can take the whole window. Editing is the one thing
            here that genuinely needs the room: the priced view is read, but a
            diagram being rearranged is worked on, and doing that in a pane
            inset by a 380px rail is what the request "I need these tools when
            I open the architecture" was actually about. */}
        <main
          className={
            sketching
              ? "fixed inset-0 z-50 bg-surface"
              : "relative min-h-0 flex-1 bg-surface"
          }
        >
          {shown?.topology?.nodes?.length && sketching ? (
            /* ── sketch mode ── */
            <>
              <div className="h-full overflow-hidden">
                <SketchCanvas
                  nodes={shown.topology.nodes}
                  edges={shown.topology.edges}
                  cloud={cloud ?? "aws"}
                  pending={pending}
                  onPendingConsumed={() => setPending(null)}
                  tool={tool}
                  onToolDone={() => setTool("select")}
                  seedToken={seedToken}
                  onSelectionChange={setPicked}
                  command={command}
                  onCommandDone={() => setCommand(null)}
                />
              </div>

              {/* Says what this picture is, and it has to. Every other number
                  on this screen is measured, so a diagram that has been moved
                  around by hand sitting silently beside them would inherit
                  their authority -- someone could add a Redis box and read the
                  unchanged total underneath as the price of it. */}
              <div className="pointer-events-none absolute inset-x-0 top-0 flex justify-center p-3">
                <div className="pointer-events-auto flex items-center gap-3 rounded-lg border border-caution/30 bg-caution-wash px-3 py-1.5 shadow-sm">
                  <span className="text-[12.5px] text-caution">
                    Sketch — your changes are not priced.
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      setSketching(false);
                      setPalette(false);
                      setTool("select");
                    }}
                    className="rounded-md border border-caution/40 px-2 py-0.5 text-[11.5px] font-medium text-caution transition-colors hover:bg-caution/10"
                  >
                    Back to the priced diagram
                  </button>
                </div>
              </div>

              {/* sketch tools */}
              <div className="pointer-events-none absolute left-0 top-0 flex h-full items-center p-3">
                <ToolRail
                  tools={[
                    {
                      id: "select",
                      label: "Select and move",
                      icon: ToolIcons.cursor,
                      active: tool === "select",
                      onSelect: () => setTool("select"),
                    },
                    {
                      id: "connect",
                      label: "Draw an arrow between two services",
                      icon: ToolIcons.arrow,
                      active: tool === "connect",
                      onSelect: () =>
                        setTool(tool === "connect" ? "select" : "connect"),
                    },
                    {
                      id: "add",
                      label: "Add a service",
                      icon: ToolIcons.plus,
                      active: palette,
                      onSelect: () => setPalette((open) => !open),
                    },
                    {
                      id: "box",
                      label: "Draw a boundary",
                      icon: ToolIcons.box,
                      active: tool === "box",
                      onSelect: () => setTool(tool === "box" ? "select" : "box"),
                    },
                    {
                      id: "text",
                      label: "Add a label",
                      icon: ToolIcons.text,
                      active: tool === "text",
                      onSelect: () => setTool(tool === "text" ? "select" : "text"),
                    },
                    "divider",
                    {
                      id: "reset",
                      label: "Start again from the priced layout",
                      icon: ToolIcons.replay,
                      onSelect: () => setSeedToken((n) => n + 1),
                    },
                  ]}
                />
              </div>

              {palette && (
                <div className="pointer-events-none absolute bottom-0 right-0 top-0 p-3">
                  <ServicePalette
                    cloud={cloud ?? "aws"}
                    onPick={setPending}
                    onClose={() => setPalette(false)}
                  />
                </div>
              )}

              {/* Properties for whatever is selected. Sits below the palette
                  when both are open, so adding a service and then editing it
                  does not mean closing one panel to reach the other. */}
              {picked && (
                <div
                  className={`pointer-events-none absolute right-0 p-3 ${palette ? "bottom-0" : "top-0"
                    }`}
                >
                  <SketchInspector
                    selection={picked}
                    onRename={(label) =>
                      setCommand({ type: "rename", id: picked.id, label })
                    }
                    onDelete={() => {
                      setCommand({ type: "delete", id: picked.id });
                      setPicked(null);
                    }}
                  />
                </div>
              )}

              <div className="pointer-events-none absolute inset-x-0 bottom-0 flex justify-center p-4">
                {/* Says what the SELECTED tool does. One fixed line listing
                    every gesture is the same as no line: the reader has to
                    find their case in it, which is the work the hint was
                    supposed to save. */}
                <span className="pointer-events-auto rounded-lg border border-line bg-surface/95 px-3 py-1.5 font-mono text-[11.5px] text-ink-3 shadow-sm backdrop-blur">
                  {tool === "connect"
                    ? "drag from any blue dot on a box to another box to draw an arrow"
                    : tool === "box"
                      ? "click the canvas to drop a boundary"
                      : tool === "text"
                        ? "click the canvas to place a label"
                        : "drag to move · double-click to rename · ⌫ to delete"}
                </span>
              </div>
            </>
          ) : shown?.topology?.nodes?.length ? (
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
                  onNodeSelect={setInspected}
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
                            className={`flex shrink-0 items-center gap-2 rounded-lg border px-3 py-1.5 transition-all ${option.label === selected
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

              {/* No tool rail here, deliberately.
                  This pane is the answer being read: a diagram beside the
                  bill that produced it, in whatever width is left after a
                  380px rail. Editing wants the opposite -- room, and no
                  column of numbers competing for the same attention -- so
                  the tools live in the full-page view, reached from
                  Rearrange in the bar below. Two sets of controls a few
                  hundred pixels apart, one of which barely fits, was worse
                  than one set in the place the work actually happens. */}

              {/* Inspector, floating opposite the rail. It steps aside when
                  the advisor is open rather than stacking on top of it: both
                  describe the same architecture, and one obscuring the other
                  is the reader losing the thing they clicked to see. */}
              {inspected && (
                <div
                  className={`pointer-events-none absolute top-0 p-3 transition-[right] ${asking ? "right-[330px]" : "right-0"
                    }`}
                >
                  <Inspector
                    node={inspected}
                    option={shown}
                    onClose={() => setInspected(null)}
                  />
                </div>
              )}

              {/* the advisor, when asked for */}
              {asking && (
                <div className="pointer-events-none absolute bottom-0 right-0 top-0 flex max-h-full w-[330px] flex-col p-3">
                  <div className="pointer-events-auto flex min-h-0 flex-col overflow-y-auto rounded-xl border border-line bg-surface/95 shadow-lg backdrop-blur">
                    <AskPanel
                      description={asked}
                      option={shown.label}
                      provider={cloud ?? "aws"}
                    />
                  </div>
                </div>
              )}

              {/* action bar, floating over the canvas */}
              <div className="pointer-events-none absolute inset-x-0 bottom-0 flex justify-center p-4">
                <div className="pointer-events-auto">{actionBar}</div>
              </div>
            </>
          ) : (
            <div className="grid h-full place-items-center p-8">
              {/* The wrapper caps the whole empty state, and at max-w-sm it
                  squeezed the three starter cards to 120px each on a 1250px
                  canvas. The prose still wants a short measure, so it keeps
                  one of its own below rather than the block keeping it for
                  everything. */}
              <div className="w-full max-w-4xl text-center">
                {busy ? (
                  <>
                    <p className="text-[14px] font-medium text-ink-2">
                      Generating architecture…
                    </p>

                    {/* The progress LINE. Determinate, because the wait has a
                        known ceiling (see GENERATE_BUDGET_S) -- a bar that
                        fills toward a real deadline tells you the wait is
                        bounded, which a spinner never can. It eases toward the
                        budget rather than running linearly off the end: the
                        last stretch slows down instead of hitting 100% and
                        sitting there, which would read as stuck. */}
                    <div
                      className="mx-auto mt-3 h-1 w-full max-w-xs overflow-hidden rounded-full bg-sunk"
                      role="progressbar"
                      aria-label="Generating architecture"
                      aria-valuemin={0}
                      aria-valuemax={GENERATE_BUDGET_S}
                      aria-valuenow={Math.min(elapsed, GENERATE_BUDGET_S)}
                    >
                      <div
                        className="h-full rounded-full bg-accent transition-[width] duration-100 ease-linear"
                        style={{
                          width: `${Math.min(
                            96,
                            100 * (1 - Math.exp(-elapsed / (GENERATE_BUDGET_S / 2.5))),
                          )}%`,
                        }}
                      />
                    </div>

                    <p className="mt-2 font-mono text-[12px] tabular-nums text-ink-3">
                      {elapsed.toFixed(1)}s
                      <span className="text-ink-3/70">
                        {" "}
                        / up to {GENERATE_BUDGET_S}s
                      </span>
                    </p>

                    <p className="mt-1 text-[12.5px] text-ink-3">
                      {elapsed < 1.5
                        ? "Reading the description…"
                        : elapsed < GENERATE_BUDGET_S
                          ? "Costing every service against the live catalog."
                          : "Taking longer than usual — the backend may be waking from idle."}
                    </p>
                  </>
                ) : result && shown ? (
                  <>
                    {/* Was "only AWS architectures are drawn today". That
                        stopped being true when the other two clouds gained
                        topologies -- all three now return the same 17/19/21
                        nodes across the tiers -- and the copy stayed, talking
                        readers out of a feature that had shipped. If a
                        topology is ever genuinely empty, the useful thing to
                        name is the tier, not the cloud. */}
                    <p className="text-[14px] text-ink-3">
                      No diagram for {shown.label} — the estimate priced it,
                      but nothing came back to draw.
                    </p>
                  </>
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
                    {/* Its own measure: the wrapper is wide so the cards can
                        breathe, but prose at 896px is unreadable. */}
                    <p className="mx-auto mt-1.5 max-w-sm text-[13px] leading-relaxed text-ink-3">
                      Describe what you&apos;re building in the panel on the
                      left. You get a priced architecture across AWS, Azure
                      and Google, drawn from the same estimate as the bill.
                    </p>

                    {/* The canvas is two thirds of the viewport and held
                        nothing until a description existed, so the first
                        thing a new user met was a blank box and no idea what
                        to put in it. One click now fills the description with
                        a real workload they can edit into their own. */}
                    {/* Three across rather than a stacked list. The canvas is
                        the widest thing on the page and a 670px column of thin
                        rows sitting in the middle of it is what made this read
                        as unfinished -- the composition has to use the space it
                        occupies. Each card carries the workload's shape and its
                        own note, so the row is worth its height. */}
                    <div className="mx-auto mt-9 w-full max-w-4xl">
                      <div className="mb-3 flex items-center gap-3">
                        <span className="h-px flex-1 bg-line" />
                        <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-ink-3">
                          Or start from one
                        </span>
                        <span className="h-px flex-1 bg-line" />
                      </div>
                      <div className="grid gap-3 sm:grid-cols-3">
                        {STARTERS.map((s) => (
                          <button
                            key={s.title}
                            type="button"
                            onClick={() => setDescription(s.text)}
                            className="group flex h-full flex-col rounded-xl border border-line bg-surface p-4 text-left transition-all duration-150 hover:-translate-y-0.5 hover:border-line-strong hover:elev-2 focus-visible:border-line-strong focus-visible:outline-none"
                          >
                            <span className="text-[13.5px] font-medium leading-snug text-ink">
                              {s.title}
                            </span>
                            <span className="mt-1.5 flex-1 font-mono text-[11.5px] leading-relaxed text-ink-3">
                              {s.note}
                            </span>
                            <span className="mt-3 inline-flex items-center gap-1 text-[12px] font-medium text-accent">
                              Use this
                              <svg
                                viewBox="0 0 24 24"
                                className="h-3.5 w-3.5 transition-transform duration-150 group-hover:translate-x-0.5"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                aria-hidden
                              >
                                <path d="M5 12h14M13 6l6 6-6 6" />
                              </svg>
                            </span>
                          </button>
                        ))}
                      </div>
                      <p className="mt-3 text-center text-[12px] text-ink-3">
                        Fills the description so you can change the numbers to
                        yours before pricing it.
                      </p>
                    </div>
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
