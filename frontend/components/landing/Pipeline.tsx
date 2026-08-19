"use client";

import { usePrefersReducedMotion } from "@/lib/usePrefersReducedMotion";
import { useEffect, useRef, useState } from "react";

/**
 * The five stages a request passes through, running one after another.
 *
 * This is the part of the product that is otherwise invisible: a sentence
 * goes in, a priced architecture comes out, and nothing on the page says what
 * happened in between. Each stage lights as it runs and stays marked done, so
 * the sequence reads as a pipeline rather than as four decorated boxes.
 *
 * The counts on each card are passed in from the catalog. They are what the
 * stage actually did -- prices really scanned, techniques really tested --
 * not illustrative figures chosen to look busy.
 */

export type Stage = {
  key: string;
  title: string;
  detail: string;
  /* Optional on purpose. Two of these steps have no figure behind them, and
     the previous version filled the gap with phrases like "plain English in"
     -- a label styled to look like data while saying nothing. A step with
     nothing to count now simply has no footer. */
  metric?: string;
  /* A key, not an element. Importing JSX out of a "use client" module into a
     server component hands back a client reference rather than the element
     itself, so the icons silently rendered as nothing at all. The name
     crosses the boundary as a string and the element is built on this side. */
  icon: keyof typeof ICONS;
};

const STEP_MS = 1250;
const HOLD_MS = 2600;

function Ico({ d }: { d: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-[19px] w-[19px]"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d={d} />
    </svg>
  );
}

const ICONS = {
  // a speech bubble with a line of text in it
  sentence: <Ico d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2zM7 8h10M7 12h6" />,
  // brackets closing around a value: the sentence becoming structured
  parse: <Ico d="M8 4H6a2 2 0 0 0-2 2v3a2 2 0 0 1-2 2 2 2 0 0 1 2 2v3a2 2 0 0 0 2 2h2M16 4h2a2 2 0 0 1 2 2v3a2 2 0 0 0 2 2 2 2 0 0 0-2 2v3a2 2 0 0 1-2 2h-2" />,
  // a database being read
  catalog: <Ico d="M21 6c0 1.66-4 3-9 3S3 7.66 3 6s4-3 9-3 9 1.34 9 3zM3 6v6c0 1.66 4 3 9 3s9-1.34 9-3V6M3 12v6c0 1.66 4 3 9 3s9-1.34 9-3v-6" />,
  // a downward trend: the bill coming down
  optimize: <Ico d="M22 17 13.5 8.5l-5 5L2 7M16 17h6v-6" />,
  // stacked layers: the three options
  output: <Ico d="m12 2 9 5-9 5-9-5 9-5zM3 12l9 5 9-5M3 17l9 5 9-5" />,
} as const;

export function Pipeline({ stages }: { stages: Stage[] }) {
  const [active, setActive] = useState(-1);
  /* Derived, not stored. `still` only ever mirrored the media query, so
     holding it as state meant rendering the moving version first and the
     finished one immediately after -- visible as a flash on a slow
     device, and exactly what React's set-state-in-effect rule catches. */
  const still = usePrefersReducedMotion();
  const host = useRef<HTMLDivElement>(null);
  const timers = useRef<number[]>([]);

  useEffect(() => {
    if (!stages.length || still) return;

    let cancelled = false;
    const clear = () => {
      timers.current.forEach(clearTimeout);
      timers.current = [];
    };

    const loop = () => {
      clear();
      setActive(-1);
      stages.forEach((_, i) => {
        timers.current.push(
          window.setTimeout(() => !cancelled && setActive(i), 350 + i * STEP_MS),
        );
      });
      timers.current.push(
        window.setTimeout(
          () => !cancelled && loop(),
          350 + stages.length * STEP_MS + HOLD_MS,
        ),
      );
    };

    /* Starts when scrolled to, and falls back to a timer: every card begins
       dimmed, so if nothing ever triggers the sequence the section reads as
       disabled rather than merely still. */
    const el = host.current;
    const fallback = window.setTimeout(loop, 1500);
    let io: IntersectionObserver | undefined;

    if (el && typeof IntersectionObserver !== "undefined") {
      io = new IntersectionObserver(
        (entries) => {
          if (entries.some((e) => e.isIntersecting)) {
            window.clearTimeout(fallback);
            io?.disconnect();
            loop();
          }
        },
        { threshold: 0.25 },
      );
      io.observe(el);
    }

    return () => {
      cancelled = true;
      io?.disconnect();
      window.clearTimeout(fallback);
      clear();
    };
  }, [stages, still]);

  return (
    <div ref={host} className="grid gap-3 md:grid-cols-5">
      {stages.map((s, i) => {
        const done = still || i < active;
        const on = !still && i === active;
        const lit = done || on;

        return (
          <div
            key={s.key}
            className={`group relative flex flex-col rounded-xl border p-4 transition-all duration-500 ${
              on
                ? "-translate-y-1 border-accent bg-surface shadow-[0_12px_28px_-14px_rgba(36,81,217,.45)]"
                : done
                  ? "border-line-strong bg-surface"
                  : "border-line bg-surface/60"
            }`}
          >
            <div className="flex items-center gap-2.5">
              <span
                className={`grid h-9 w-9 shrink-0 place-items-center rounded-lg transition-all duration-500 ${
                  lit ? "bg-accent text-white" : "bg-sunk text-ink-3"
                }`}
              >
                {ICONS[s.icon] ?? ICONS.sentence}
              </span>
              {/* The position in the row already says which step this is; a
                  chip repeating it in caps was chrome. The numeral sits back
                  where it can be found and not read. */}
              <span
                className={`ml-auto font-mono text-[13px] tabular-nums transition-colors duration-500 ${
                  lit ? "text-ink-3" : "text-line-strong"
                }`}
                aria-hidden
              >
                {i + 1}
              </span>
            </div>

            <p
              className={`mt-3 text-[15px] font-semibold leading-tight transition-colors duration-500 ${
                lit ? "text-ink" : "text-ink-3"
              }`}
            >
              {s.title}
            </p>
            <p
              className={`mt-1.5 flex-1 text-[13px] leading-relaxed transition-colors duration-500 ${
                lit ? "text-ink-2" : "text-ink-3"
              }`}
            >
              {s.detail}
            </p>

            {s.metric && (
              <div
                className={`mt-3 border-t pt-2.5 font-mono text-[12.5px] font-medium transition-all duration-500 ${
                  lit
                    ? "border-line text-accent opacity-100"
                    : "border-transparent text-ink-3 opacity-0"
                }`}
              >
                {s.metric}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
