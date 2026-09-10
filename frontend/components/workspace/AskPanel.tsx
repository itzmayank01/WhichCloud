"use client";

import { useState } from "react";
import { api, type Advice, type Suggestion } from "@/lib/api";

/**
 * Ask a question about the architecture on screen.
 *
 * The panel's job is to keep two kinds of claim visually apart. A line item
 * is measured -- it came from a provider's rate card and the engine did the
 * arithmetic. A suggestion is a model's opinion. Everywhere else in this
 * interface a number is a fact, so an answer that reads like the rest of the
 * page would borrow authority the model has not earned.
 *
 * Hence: the reader is named, the verdict is a chip rather than prose, and
 * every suggestion says plainly whether the engine can price it. A suggestion
 * carrying a lever is a change the engine can cost; one without is advice.
 * Presenting those two alike is the failure this layout exists to prevent.
 */

/** Openers, in the vocabulary of someone reading their own bill. */
const STARTERS = [
  "Why is this so expensive?",
  "What could I cut without losing uptime?",
  "Is this over-built for what I described?",
  "What breaks first if traffic doubles?",
];

const VERDICT: Record<
  Advice["verdict"],
  { label: string; className: string } | null
> = {
  sound: { label: "Sound", className: "bg-save/10 text-save ring-save/30" },
  has_risks: {
    label: "Has risks",
    className: "bg-caution-wash text-caution ring-caution/30",
  },
  not_recommended: {
    label: "Not recommended",
    className: "bg-caution-wash text-caution ring-caution/40",
  },
  // Most questions are not "is this correct", and a chip reading "not
  // applicable" on every one of them is noise pretending to be information.
  not_applicable: null,
};

const ARROW: Record<Suggestion["direction"], string> = {
  increase: "↑",
  decrease: "↓",
  enable: "+",
  disable: "−",
  unchanged: "·",
};

function SuggestionCard({ suggestion }: { suggestion: Suggestion }) {
  const priceable = suggestion.lever !== "none";

  return (
    <li className="rounded-lg border border-line bg-canvas p-3">
      <div className="flex items-start gap-2">
        <span
          aria-hidden
          className={`mt-px font-mono text-[13px] font-bold ${
            priceable ? "text-accent" : "text-ink-3"
          }`}
        >
          {ARROW[suggestion.direction]}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[13.5px] font-semibold leading-snug text-ink">
            {suggestion.title}
          </p>
          <p className="mt-1 text-[12.5px] leading-relaxed text-ink-2">
            {suggestion.rationale}
          </p>

          {suggestion.trade_off && (
            /* Never collapsed behind a toggle. Every saving costs something,
               and a list of savings whose costs are one click away is a list
               of savings. */
            <p className="mt-1.5 text-[12px] leading-relaxed text-ink-3">
              <span className="font-medium text-caution">Gives up:</span>{" "}
              {suggestion.trade_off}
            </p>
          )}

          <div className="mt-2">
            {priceable ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-accent-wash px-2 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wide text-accent ring-1 ring-accent-line">
                engine can price this · {suggestion.lever}
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 rounded-full bg-sunk px-2 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wide text-ink-3 ring-1 ring-line">
                advice · no figure
              </span>
            )}
          </div>
        </div>
      </div>
    </li>
  );
}

export function AskPanel({
  description,
  option,
  provider,
}: {
  /** The description that produced what is on screen. The route re-derives
   *  the architecture from it rather than trusting anything posted. */
  description: string;
  option: string;
  provider: string;
}) {
  const [question, setQuestion] = useState("");
  const [advice, setAdvice] = useState<Advice | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function ask(text: string) {
    const asked = text.trim();
    if (!asked || busy) return;
    setBusy(true);
    setError("");
    try {
      setAdvice(await api.advise({ description, question: asked, option, provider }));
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not answer that.",
      );
    } finally {
      setBusy(false);
    }
  }

  const verdict = advice ? VERDICT[advice.verdict] : null;

  return (
    <div className="flex flex-col gap-3 p-4">
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="text-[13px] font-semibold text-ink">Ask about this</h2>
        <span className="font-mono text-[11px] text-ink-3">{option}</span>
      </div>

      <textarea
        value={question}
        onChange={(event) => setQuestion(event.target.value)}
        onKeyDown={(event) => {
          // Enter sends; Shift+Enter breaks the line. A question is usually
          // one sentence, so reaching for a button is the rarer need.
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            void ask(question);
          }
        }}
        rows={2}
        placeholder="Why is the database the biggest line?"
        className="w-full resize-none rounded-lg border border-line bg-canvas px-3 py-2 text-[13px] text-ink outline-none placeholder:text-ink-3 focus:border-accent-line focus:ring-2 focus:ring-accent-wash"
      />

      <div className="flex flex-wrap gap-1.5">
        {STARTERS.map((starter) => (
          <button
            key={starter}
            type="button"
            disabled={busy}
            onClick={() => {
              setQuestion(starter);
              void ask(starter);
            }}
            className="rounded-full border border-line px-2.5 py-1 text-[11.5px] text-ink-2 transition-colors hover:border-line-strong hover:bg-sunk disabled:opacity-40"
          >
            {starter}
          </button>
        ))}
      </div>

      <button
        type="button"
        disabled={busy || !question.trim()}
        onClick={() => void ask(question)}
        className="rounded-lg bg-accent px-4 py-2 text-[13px] font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40"
      >
        {busy ? "Reading the bill…" : "Ask"}
      </button>

      {error && (
        <p className="rounded-lg bg-caution-wash px-3 py-2 text-[12.5px] text-caution">
          {error}
        </p>
      )}

      {advice && (
        <div className="flex flex-col gap-3">
          <div className="rounded-lg border border-line bg-canvas p-3">
            <div className="mb-2 flex items-center gap-2">
              {verdict && (
                <span
                  className={`rounded-full px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wide ring-1 ${verdict.className}`}
                >
                  {verdict.label}
                </span>
              )}
              {/* Named, not hidden. The reader should be able to tell a
                  model's answer from a catalog figure without checking the
                  docs -- and which model, since they do not agree. */}
              <span className="ml-auto font-mono text-[10.5px] text-ink-3">
                answered by {advice.read_by}
              </span>
            </div>
            <p className="text-[13px] leading-relaxed text-ink-2">
              {advice.answer}
            </p>
          </div>

          {advice.suggestions.length > 0 && (
            <ul className="flex flex-col gap-2">
              {advice.suggestions.map((suggestion, index) => (
                <SuggestionCard
                  key={`${suggestion.title}-${index}`}
                  suggestion={suggestion}
                />
              ))}
            </ul>
          )}

          <p className="text-[11.5px] leading-relaxed text-ink-3">
            Suggestions are a model&apos;s reading of the bill above. The
            figures on this page are measured; these are not, which is why
            none of them carries one.
          </p>
        </div>
      )}
    </div>
  );
}
