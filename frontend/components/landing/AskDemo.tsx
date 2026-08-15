"use client";

import { Icon } from "@iconify/react";
import { useEffect, useRef, useState } from "react";

/**
 * The plain-English intake, playing itself.
 *
 * A cursor picks one of the prompts, the question types into the box, the
 * reader parses it into a requirement, and the priced answer arrives. Then it
 * moves to the next prompt.
 *
 * Two rules govern what it is allowed to show.
 *
 * The readers are the two the backend actually has: `intake.py` defines
 * Provider as gemini | anthropic and nothing else. A chip for a tool
 * WhichCloud does not integrate with would be claiming an integration on the
 * landing page, which is the thing the rest of this site is built to avoid.
 *
 * And every figure is passed in from the catalog, never written here. A demo
 * of a pricing tool that invents prices to look convincing gives away the
 * only claim the page is making.
 */

export type Scenario = {
  question: string;
  chips: string[];
  rows: { provider: string; label: string; monthly: string; cheapest: boolean }[];
};

const READERS = [
  { id: "gemini", label: "Gemini", icon: "logos:google-gemini" },
  { id: "anthropic", label: "Claude", icon: "logos:claude-icon" },
];

/** A mark per prompt, so the three read as different questions at a glance. */
const PROMPT_ICONS = ["💰", "⚡", "🌍"];

const T = {
  toPrompt: 450,
  press: 1350,
  typeStart: 1750,
  typeSpeed: 32,
  parseGap: 480,
  answerGap: 820,
  hold: 3200,
};

export function AskDemo({ scenarios }: { scenarios: Scenario[] }) {
  const [index, setIndex] = useState(0);
  const [typed, setTyped] = useState("");
  const [stage, setStage] = useState<"idle" | "picking" | "typing" | "parsed" | "answered">("idle");
  const [reader, setReader] = useState(0);
  const [still, setStill] = useState(false);
  const timers = useRef<number[]>([]);
  const cardRef = useRef<HTMLDivElement>(null);
  const promptRefs = useRef<(HTMLDivElement | null)[]>([]);
  const inputRef = useRef<HTMLDivElement>(null);
  const [cursor, setCursor] = useState<{ x: number; y: number } | null>(null);

  const scenario = scenarios[index] ?? scenarios[0];

  useEffect(() => {
    if (!scenarios.length) return;

    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      // Motion is the whole point of this panel, so with it turned off it
      // shows its finished state rather than an empty shell.
      setStill(true);
      setTyped(scenarios[0].question);
      setStage("answered");
      return;
    }

    let cancelled = false;
    const at = (ms: number, fn: () => void) =>
      timers.current.push(window.setTimeout(() => !cancelled && fn(), ms));

    timers.current.forEach(clearTimeout);
    timers.current = [];
    setTyped("");
    setStage("idle");

    at(T.toPrompt, () => setStage("picking"));
    at(T.press, () => setReader((r) => (r + 1) % READERS.length));

    const q = scenario.question;
    at(T.typeStart, () => setStage("typing"));
    for (let i = 1; i <= q.length; i++) {
      at(T.typeStart + i * T.typeSpeed, () => setTyped(q.slice(0, i)));
    }

    const done = T.typeStart + q.length * T.typeSpeed;
    at(done + T.parseGap, () => setStage("parsed"));
    at(done + T.parseGap + T.answerGap, () => setStage("answered"));
    at(done + T.parseGap + T.answerGap + T.hold, () =>
      setIndex((i) => (i + 1) % scenarios.length),
    );

    return () => {
      cancelled = true;
      timers.current.forEach(clearTimeout);
      timers.current = [];
    };
  }, [index, scenarios, scenario.question]);

  /* The cursor is placed from the real geometry of whatever it is pointing
     at, measured each time the target changes. Positioning it as a
     percentage of the card looks right until the answer rows appear and the
     card grows taller underneath it -- then the pointer slides off the input
     and onto the results. */
  useEffect(() => {
    if (still) return;
    const card = cardRef.current;
    if (!card) return;

    const place = () => {
      const typingNow =
        stage === "typing" || stage === "parsed" || stage === "answered";
      const target = typingNow
        ? inputRef.current
        : promptRefs.current[Math.min(index, 2)];
      if (!target) return;
      const c = card.getBoundingClientRect();
      const t = target.getBoundingClientRect();
      setCursor({
        x: t.left - c.left + t.width * (typingNow ? 0.22 : 0.62),
        y: t.top - c.top + t.height * (typingNow ? 0.72 : 0.68),
      });
    };

    place();
    window.addEventListener("resize", place);
    return () => window.removeEventListener("resize", place);
  }, [stage, index, still]);

  if (!scenarios.length) return null;

  const answered = stage === "answered";
  const parsed = stage === "parsed" || answered;

  return (
    /* Nested frame: a soft outer panel holding the card, which is what gives
       the product shot its depth without a drop shadow doing all the work. */
    <div className="rounded-[22px] border border-line bg-sunk p-3 sm:p-4">
      <div
        ref={cardRef}
        className="relative overflow-hidden rounded-2xl border border-line bg-surface shadow-[0_1px_2px_rgba(13,20,20,.04),0_18px_40px_-26px_rgba(13,20,20,.28)]">
        {/* reader selector */}
        <div className="flex flex-wrap items-center gap-2.5 border-b border-line px-4 py-3">
          <span className="text-[14px] font-semibold text-ink">Read by</span>
          {READERS.map((r, i) => {
            const on = i === reader;
            return (
              <span
                key={r.id}
                className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[13.5px] font-medium transition-all duration-300 ${
                  on
                    ? "border-accent bg-accent-wash text-ink"
                    : "border-line bg-surface text-ink-3"
                }`}
              >
                <Icon icon={r.icon} width={15} height={15} aria-hidden />
                {r.label}
              </span>
            );
          })}
        </div>

        <div className="px-4 pb-4 pt-6 sm:px-5">
          <p className="text-center text-[18px] font-semibold tracking-[-0.02em]">
            What are you building?
          </p>

          {/* the three prompts */}
          <div className="mt-4 grid grid-cols-3 gap-2.5">
            {scenarios.slice(0, 3).map((s, i) => {
              const active = i === index;
              return (
                <div
                  key={s.question}
                  ref={(el) => {
                    promptRefs.current[i] = el;
                  }}
                  className={`rounded-lg border px-2.5 py-2.5 text-left transition-all duration-300 ${
                    active && stage === "picking"
                      ? "-translate-y-0.5 border-accent bg-accent-wash shadow-[0_8px_18px_-10px_rgba(36,81,217,.5)]"
                      : active
                        ? "border-line-strong bg-surface"
                        : "border-line bg-surface"
                  }`}
                >
                  <span className="text-[15px] leading-none">{PROMPT_ICONS[i]}</span>
                  <p
                    className={`mt-1.5 text-[12.5px] leading-snug ${
                      active ? "text-ink-2" : "text-ink-3"
                    }`}
                  >
                    {s.question}
                  </p>
                </div>
              );
            })}
          </div>

          {/* the input */}
          <div
            ref={inputRef}
            className="mt-4 flex items-center gap-2.5 rounded-xl border border-line bg-sunk px-3 py-2.5"
          >
            <svg viewBox="0 0 24 24" className="h-4 w-4 shrink-0 text-ink-3" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" aria-hidden>
              <path d="M21.4 11.05 12.25 20.2a5.5 5.5 0 0 1-7.78-7.78l9.2-9.19a3.67 3.67 0 0 1 5.18 5.18l-9.2 9.2a1.83 1.83 0 0 1-2.6-2.6l8.5-8.48" />
            </svg>
            <span className="min-h-[1.4em] flex-1 truncate text-left font-mono text-[13.5px] text-ink">
              {typed || <span className="text-ink-3">Ask something…</span>}
              {!still && stage === "typing" && (
                <span className="ml-0.5 inline-block h-[1.05em] w-[0.5ch] translate-y-[0.16em] animate-pulse bg-accent" />
              )}
            </span>
            <span
              className={`grid h-7 w-7 shrink-0 place-items-center rounded-lg transition-colors duration-300 ${
                typed ? "bg-accent" : "bg-line-strong"
              }`}
            >
              <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                <path d="M22 2 11 13M22 2l-7 20-4-9-9-4z" />
              </svg>
            </span>
          </div>

          {/* what the reader understood */}
          <div
            className={`mt-3.5 flex flex-wrap items-center justify-center gap-1.5 transition-all duration-300 ${
              parsed ? "opacity-100" : "translate-y-1 opacity-0"
            }`}
          >
            <span className="font-mono text-[11px] uppercase tracking-[0.1em] text-ink-3 font-medium">
              Understood as
            </span>
            {scenario.chips.map((c) => (
              <span
                key={c}
                className="rounded border border-line bg-sunk px-1.5 py-0.5 font-mono text-[11.5px] font-medium text-ink-2"
              >
                {c}
              </span>
            ))}
          </div>

          {/* the priced answer */}
          <div
            className={`mt-3 space-y-1.5 transition-all duration-500 ${
              answered ? "opacity-100" : "translate-y-2 opacity-0"
            }`}
          >
            {scenario.rows.map((row, i) => (
              <div
                key={row.provider}
                className={`flex items-center justify-between rounded-lg border px-3 py-2 transition-all duration-500 ${
                  row.cheapest ? "border-save/45" : "border-line"
                }`}
                style={{ transitionDelay: answered ? `${i * 80}ms` : "0ms" }}
              >
                <span className="text-[13.5px] font-medium text-ink-2">{row.label}</span>
                <span className="flex items-baseline gap-2">
                  <span
                    className={`tnum font-mono text-[15px] font-semibold ${
                      row.cheapest ? "text-save" : "text-ink"
                    }`}
                  >
                    {row.monthly}
                  </span>
                  {row.cheapest && (
                    <span className="rounded-full bg-save px-1.5 py-0.5 text-[9.5px] font-semibold uppercase tracking-[0.05em] text-white">
                      Cheapest
                    </span>
                  )}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* the pointer, travelling from prompt to input */}
        {!still && cursor && (
          <svg
            viewBox="0 0 24 24"
            className={`pointer-events-none absolute z-10 h-6 w-6 drop-shadow-[0_2px_4px_rgba(11,13,18,.35)] transition-all duration-[650ms] ease-[cubic-bezier(.4,.1,.2,1)] ${
              stage === "idle" ? "opacity-0" : "opacity-100"
            } ${stage === "picking" ? "scale-90" : "scale-100"}`}
            style={{ left: cursor.x, top: cursor.y }}
            fill="#0b0d12"
            stroke="#fff"
            strokeWidth="1.3"
            strokeLinejoin="round"
            aria-hidden
          >
            <path d="M5 2.5 19.5 11.2l-6.4 1.5-3.2 6.4z" />
          </svg>
        )}
      </div>
    </div>
  );
}
