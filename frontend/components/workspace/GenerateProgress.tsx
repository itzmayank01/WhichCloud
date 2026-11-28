"use client";

/**
 * What the app is doing while an architecture is generated.
 *
 * The bar this replaces showed liveness and nothing else. These steps are the
 * real sequence a generate runs in -- the description is read by a model,
 * every service is then priced against the catalog, and the topology is drawn
 * from the result -- so naming them tells someone waiting what is happening
 * rather than only that something is.
 *
 * WHAT IT DOES NOT DO is pretend to know where in that sequence the work
 * currently is. There is no progress channel from the backend: one request
 * goes out and one response comes back, and inventing step transitions on a
 * timer would be a progress bar lying in a new costume -- the same fault as
 * the "20.2s / up to 15s" caption this followed.
 *
 * So the honest mapping is the measured one. The model read is essentially
 * the whole wait (~14s budget server-side) and pricing the result measures
 * well under a second, so for as long as anyone is watching, the true answer
 * is "reading the description". The remaining steps complete when the
 * response actually lands, and tick then -- which is both accurate and the
 * moment the animation is worth seeing.
 */

import { useEffect, useState } from "react";

/** When an ordinary wait becomes one worth remarking on. Not a deadline, and
 *  never rendered as one -- it only changes the wording. */
const SLOW_AFTER_S = 15;

type Phase = "reading" | "done";

const STEPS: { title: string; detail: string }[] = [
  { title: "Reading your description", detail: "workload, traffic, region, budget" },
  { title: "Pricing every service", detail: "against live AWS, Azure and Google rates" },
  { title: "Drawing the architecture", detail: "topology, tiers and dependencies" },
];

function Tick() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="tick-pop h-3 w-3"
      fill="none"
      stroke="#fff"
      strokeWidth="3.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}

export function GenerateProgress({ phase }: { phase: Phase }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (phase === "done") return;
    const started = Date.now();
    const id = setInterval(() => setElapsed((Date.now() - started) / 1000), 100);
    return () => clearInterval(id);
  }, [phase]);

  const slow = elapsed >= SLOW_AFTER_S;
  /* Step 0 is the one in flight for as long as this is on screen; the rest
     are done only once the response has landed. Nothing advances on a clock. */
  const activeIndex = phase === "done" ? STEPS.length : 0;

  return (
    <div className="mx-auto w-full max-w-sm text-left">
      <p className="working-text text-[13.5px] font-medium">
        {slow ? "Still working…" : "Working…"}
      </p>

      <div className="mt-3.5 space-y-3.5">
        {STEPS.map((s, i) => {
          const done = i < activeIndex;
          const active = i === activeIndex;
          return (
            <div key={s.title} className="step-in flex gap-2.5">
              <span className="relative flex flex-col items-center">
                <span
                  className={`grid h-[18px] w-[18px] shrink-0 place-items-center rounded-full transition-colors duration-300 ${
                    done
                      ? "bg-save"
                      : active
                        ? "border-2 border-accent bg-surface"
                        : "border-2 border-line-strong bg-surface"
                  }`}
                >
                  {done && <Tick />}
                  {/* The one in flight pulses, so the eye has somewhere to
                      rest that is honestly moving. */}
                  {active && (
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
                  )}
                </span>
                {i < STEPS.length - 1 && (
                  <span className="mt-1 w-px flex-1 bg-line" aria-hidden />
                )}
              </span>

              <div className="-mt-0.5 pb-0.5">
                <p
                  className={`text-[13.5px] font-medium leading-snug ${
                    done || active ? "text-ink" : "text-ink-3"
                  }`}
                >
                  {s.title}
                </p>
                <p className="mt-0.5 font-mono text-[11.5px] text-ink-3">
                  {active ? (
                    <>
                      {slow
                        ? "the service may be waking up — a cold start can take a minute"
                        : s.detail}
                      <span className="mx-1.5 text-ink-3/50">·</span>
                      <span className="tabular-nums">{elapsed.toFixed(1)}s</span>
                    </>
                  ) : (
                    s.detail
                  )}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
