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
 * The readers are exactly the ones the backend has an extractor for --
 * `intake.py` defines Provider as gemini | anthropic | openai, and a test
 * pins that set against this list. A chip for a tool with nothing behind it
 * would be an integration claimed and not built, on a page whose whole
 * argument is that its claims are checkable.
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
  { id: "openai", label: "ChatGPT", icon: "logos:openai-icon" },
];

/* A mark per prompt, so the three read as different questions at a glance.
   Drawn rather than emoji: emoji render in whatever the operating system
   ships, so the same three characters are a different weight, palette and
   era on every machine, and none of them match the rest of the interface. */
function PromptIcon({ kind }: { kind: number }) {
  const paths = [
    // a bill: cost
    "M2 7h20v10H2zM12 12a2.5 2.5 0 1 0 0 .01M6 10v.01M18 14v.01",
    // a bolt: speed
    "M13 2 4.1 12.7a1 1 0 0 0 .8 1.6H11l-1 7.7 8.9-10.7a1 1 0 0 0-.8-1.6H12z",
    // a globe: region
    "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM3.6 9h16.8M3.6 15h16.8M12 3a15 15 0 0 1 0 18 15 15 0 0 1 0-18z",
  ];
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-[17px] w-[17px] text-accent"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d={paths[kind] ?? paths[0]} />
    </svg>
  );
}

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
        className="relative overflow-hidden rounded-2xl border border-line bg-surface elev-3">
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
          {/* Three across only where three fit. Measured on the rendered
              panel: at 375px a fixed three-column grid gives each prompt 93px
              of width and 131px of height, which is a column of single words.
              They stack below sm instead. */}
          <div className="mt-4 grid grid-cols-1 gap-2.5 sm:grid-cols-3">
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
                  <PromptIcon kind={i} />
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
          {/* The gradient is a border, not a background: a 2px frame with the
              real surface inset inside it, so the field stays white and the
              colour reads as a ring around the place you type. */}
          <div
            ref={inputRef}
            className="mt-4 rounded-2xl p-[2px]"
            style={{
              backgroundImage:
                "linear-gradient(100deg, #f4a58c, #e6a8d0 28%, #a99cf0 58%, #6d7ff0 82%, #2451d9)",
            }}
          >
            <div className="flex items-center gap-3 rounded-[14px] bg-surface px-4 py-3">
              <span className="min-h-[1.4em] flex-1 truncate text-left font-mono text-[13.5px] text-ink">
                {typed || <span className="text-ink-3">Ask something…</span>}
                {!still && stage === "typing" && (
                  <span className="ml-0.5 inline-block h-[1.05em] w-[0.5ch] translate-y-[0.16em] animate-pulse bg-accent" />
                )}
              </span>
              <span
                className={`grid h-8 w-8 shrink-0 place-items-center rounded-xl transition-colors duration-300 ${
                  typed ? "bg-accent" : "bg-line-strong"
                }`}
              >
                <svg
                  viewBox="0 0 24 24"
                  className="h-4 w-4"
                  fill="none"
                  stroke="#fff"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden
                >
                  <path d="M12 19V5M5 12l7-7 7 7" />
                </svg>
              </span>
            </div>
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
