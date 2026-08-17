"use client";

import { useState } from "react";
import {
  api,
  money,
  type ArchitectureView,
  type Option,
  type Recommendation,
} from "@/lib/api";
import { ArchitectureCanvas } from "@/components/architecture/ArchitectureCanvas";

/**
 * The advisor: a description of a business problem in, three costed options
 * out, with one recommended.
 *
 * Written for someone who does not know what a load balancer is. They are not
 * asked to pick services, a traffic tier or an instance size -- they describe
 * their situation and their budget, and the engine decides. Every figure comes
 * from the price catalog, so "this costs $280 a month" is a fact rather than
 * an estimate dressed as one.
 *
 * Distinct from the architecture workbench below it, which draws whatever
 * somebody names. This answers the question a manager actually has: what
 * should I build, and can I afford it.
 */

const EXAMPLE =
  "I run operations for a retail chain in India with 40 stores. We want to " +
  "move our stock and billing system online so staff can use it from any " +
  "store and head office can see live numbers. Around 300 staff use it daily " +
  "and we do about 8,000 transactions a day. It must not go down during " +
  "business hours because billing stops. Budget is around $500 a month.";

/** Which option to put forward, and why. */
function recommend(options: Option[]): { pick: Option; because: string } | null {
  if (options.length === 0) return null;

  /* An incomplete estimate is missing a component, so its total is not a
     smaller number for the same thing -- it is the wrong number. Those can
     never be recommended, however cheap they look. */
  const usable = options.filter((o) => o.complete);
  if (usable.length === 0) return null;

  const affordable = usable.filter((o) => o.within_budget !== false);
  if (affordable.length === 0) {
    const cheapest = usable.reduce((a, b) => (a.monthly_usd <= b.monthly_usd ? a : b));
    return {
      pick: cheapest,
      because:
        "Nothing here fits the budget given. This is the least expensive " +
        "option that still runs the workload.",
    };
  }

  /* The most capable thing the budget allows, rather than the cheapest that
     fits. Someone who states a budget has already decided what they are
     willing to spend; handing back the minimum spends their allowance on
     nothing. */
  const pick = affordable.reduce((a, b) => (a.monthly_usd >= b.monthly_usd ? a : b));
  return {
    pick,
    because:
      pick.label === "Most reliable"
        ? "It fits the budget and survives an availability-zone failure."
        : "It fits the budget with room to spare, and handles the expected peak.",
  };
}

export function CostedAdvisor() {
  const [description, setDescription] = useState("");
  const [result, setResult] = useState<Recommendation | null>(null);
  /* What they described, drawn. Kept apart from the priced tiers because it
     answers a different question: the tiers say what a standard system of
     this size costs, this says what the system they described looks like. */
  const [described, setDescribed] = useState<ArchitectureView | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function ask() {
    setBusy(true);
    setError(null);
    setResult(null);
    setDescribed(null);
    try {
      /* Both at once. The pricer and the architecture reader answer different
         halves of the question and neither waits on the other; asking in
         sequence would double the wait for no gain. */
      const [answer, drawing] = await Promise.allSettled([
        api.describe({ description }),
        api.architecture({ description }),
      ]);

      if (answer.status === "rejected") throw answer.reason;
      setResult(answer.value);
      setSelected(
        recommend(answer.value.options)?.pick.label ??
          answer.value.options[0]?.label ??
          null,
      );

      /* A description naming no services draws nothing worth showing, and a
         reader that ran out of quota should not take the prices down with
         it -- the tiers are the answer either way. */
      if (drawing.status === "fulfilled" && drawing.value.counts.services > 2) {
        setDescribed(drawing.value);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not read that description");
    } finally {
      setBusy(false);
    }
  }

  const advice = result ? recommend(result.options) : null;
  const budget = result?.budget_monthly_usd ?? null;
  const unspent = advice && budget ? budget - advice.pick.monthly_usd : null;
  const shown = result?.options.find((o) => o.label === selected) ?? null;

  return (
    <div className="rounded-2xl border border-line bg-surface p-6 elev-1 sm:p-8">
      <h2 className="text-[20px] font-semibold tracking-[-0.015em]">
        What should I build, and what will it cost?
      </h2>
      <p className="mt-2 max-w-2xl text-[15px] leading-relaxed text-ink-2">
        Describe your situation in your own words — what the system is for, how
        many people use it, what happens if it stops, and what you can spend.
        No cloud knowledge needed.
      </p>

      <textarea
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        rows={5}
        placeholder={EXAMPLE}
        className="mt-5 w-full resize-y rounded-xl border border-line bg-canvas p-4 text-[14.5px] leading-relaxed text-ink outline-none placeholder:text-ink-3 focus:border-accent"
      />

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button
          onClick={ask}
          disabled={busy || !description.trim()}
          className="rounded-lg bg-accent px-5 py-2.5 text-[15.5px] font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40"
        >
          {busy ? "Working…" : "Recommend an architecture"}
        </button>
        {!description.trim() && (
          <button
            onClick={() => setDescription(EXAMPLE)}
            className="text-[14px] text-accent hover:underline"
          >
            Use the example
          </button>
        )}
      </div>

      {error && (
        <p className="mt-4 rounded-lg bg-caution-wash px-4 py-3 text-[14.5px] text-caution">
          {error}
        </p>
      )}

      {result && advice && (
        <div className="mt-8 border-t border-line pt-7">
          <p className="font-mono text-[12.5px] uppercase tracking-[0.11em] text-ink-3">
            Read as
          </p>
          <p className="mt-1 text-[16px] text-ink">{result.goal}</p>

          <div className="mt-6 rounded-xl bg-save-wash p-5">
            <p className="text-[17px] font-semibold text-ink">
              We recommend {advice.pick.label} —{" "}
              <span className="text-save">{money(advice.pick.monthly_usd)}/mo</span>
            </p>
            <p className="mt-1.5 text-[15px] leading-relaxed text-ink-2">
              {advice.because}
            </p>
            {/* Saying "within budget" without saying what is left of it hides
                the most useful number on the page: a manager with $500
                unspent has a decision to make, and a green tick tells them
                nothing about it. */}
            {unspent !== null && unspent > 1 && (
              <p className="mt-2 text-[14.5px] leading-relaxed text-ink-2">
                That leaves <strong>{money(unspent)}</strong> of your{" "}
                {money(budget!)} unspent. The catalog sizes from expected
                traffic rather than from budget, so spending it would mean
                larger instances, more of them, or a second region — none of
                which this describes yet.
              </p>
            )}
          </div>

          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            {result.options.map((option) => {
              const active = option.label === selected;
              const recommended = option.label === advice.pick.label;
              return (
                <button
                  key={option.label}
                  onClick={() => setSelected(option.label)}
                  className={`rounded-xl border p-4 text-left transition-colors ${
                    active
                      ? "border-accent bg-accent-wash"
                      : "border-line bg-canvas hover:bg-sunk"
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <span className="text-[14.5px] font-semibold">{option.label}</span>
                    {recommended && (
                      <span className="rounded-full bg-save px-2 py-0.5 font-mono text-[10.5px] font-medium text-white">
                        recommended
                      </span>
                    )}
                  </span>
                  <span className="mt-1.5 block tnum font-mono text-[19px] font-semibold">
                    {money(option.monthly_usd)}
                  </span>
                  {/* An incomplete estimate is missing a component, so it is
                      not a cheaper version of the same thing -- it is wrong.
                      Saying so is the whole point. */}
                  <span
                    className={`mt-1 block font-mono text-[11.5px] ${
                      !option.complete
                        ? "text-caution"
                        : option.within_budget === false
                          ? "text-spend"
                          : "text-ink-3"
                    }`}
                  >
                    {!option.complete
                      ? `incomplete — ${option.missing.length} unpriced`
                      : option.within_budget === false
                        ? "over budget"
                        : "within budget"}
                  </span>
                </button>
              );
            })}
          </div>

          {shown && (
            <div className="mt-6">
              <p className="text-[15px] leading-relaxed text-ink-2">
                {shown.rationale}
              </p>
              <p className="mt-1.5 font-mono text-[13px] text-ink-3">{shown.shape}</p>

              <table className="mt-4 w-full border-collapse text-left">
                <thead>
                  <tr className="border-b border-line font-mono text-[11.5px] uppercase tracking-[0.08em] text-ink-3">
                    <th className="py-2 font-medium">Service</th>
                    <th className="py-2 font-medium">What runs</th>
                    <th className="py-2 text-right font-medium">Monthly</th>
                  </tr>
                </thead>
                <tbody>
                  {shown.items.map((item) => (
                    <tr key={item.label} className="border-b border-line last:border-0">
                      <td className="py-2.5 text-[14px] text-ink-2">{item.label}</td>
                      <td className="py-2.5 font-mono text-[12.5px] text-ink-3">
                        {item.sku}
                      </td>
                      <td className="tnum py-2.5 text-right font-mono text-[14px] font-semibold">
                        {money(item.monthly_usd)}
                      </td>
                    </tr>
                  ))}
                  <tr>
                    <td className="pt-3 text-[14.5px] font-semibold" colSpan={2}>
                      Every month
                    </td>
                    <td className="tnum pt-3 text-right font-mono text-[17px] font-semibold">
                      {money(shown.monthly_usd)}
                    </td>
                  </tr>
                </tbody>
              </table>

              {/* Two drawings, because there are two answers.

                  What was described is the system in the words someone wrote,
                  every service they named. What is priced is the standard
                  architecture of this size, which is where the figures come
                  from. Showing only the second makes a rich description look
                  like it was ignored; showing only the first leaves the money
                  unexplained. */}
              {described && (
                <div className="mt-7">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <h3 className="text-[15.5px] font-semibold">
                      The system you described
                    </h3>
                    <span className="font-mono text-[12.5px] text-ink-3">
                      {described.counts.services} services ·{" "}
                      {described.counts.priced} priced by the catalog
                    </span>
                  </div>
                  <div className="mt-3 overflow-hidden rounded-xl border border-line bg-canvas p-2">
                    <ArchitectureCanvas view={described} />
                  </div>
                  <p className="mt-2 text-[13.5px] leading-relaxed text-ink-3">
                    Drawn as written. The catalog prices seven kinds of service
                    — compute, database, cache, storage, delivery, load
                    balancing and monitoring — so the figures below come from
                    the standard architecture beneath, not from every box here.
                  </p>
                </div>
              )}

              {shown.drawn && (
                <div className="mt-7">
                  <h3 className="text-[15.5px] font-semibold">
                    What the {shown.label.toLowerCase()} price pays for
                  </h3>
                  <div className="mt-3 overflow-hidden rounded-xl border border-line bg-canvas p-2">
                    <ArchitectureCanvas view={shown.drawn} />
                  </div>
                </div>
              )}

              {shown.tradeoffs.length > 0 && (
                <div className="mt-5 rounded-lg bg-caution-wash px-4 py-3">
                  <p className="font-mono text-[11.5px] uppercase tracking-[0.1em] text-caution">
                    What this gives up
                  </p>
                  <ul className="mt-1.5 space-y-1">
                    {shown.tradeoffs.map((t) => (
                      <li key={t} className="text-[14.5px] leading-relaxed text-ink-2">
                        {t}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {result.assumed.length > 0 && (
            <p className="mt-5 text-[13.5px] leading-relaxed text-ink-3">
              Guessed, because the description did not say:{" "}
              {result.assumed.join(", ")}.
              {result.clarifying_question && ` ${result.clarifying_question}`}
            </p>
          )}
          <p className="mt-2 text-[13.5px] leading-relaxed text-ink-3">
            {result.sizing_basis}
          </p>
        </div>
      )}
    </div>
  );
}
