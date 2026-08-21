"use client";

import { useState } from "react";
import { api, type Plan } from "@/lib/api";
import { PlanView } from "@/components/plan/PlanView";

const EXAMPLE =
  "I manage IT for a 3-hospital group in Pune. We want to move patient " +
  "appointments, records and lab reports online so doctors and front desk can " +
  "access them from all three sites. About 450 staff use it, roughly 6,000 " +
  "record lookups a day, with peaks in the morning. Patient data must stay " +
  "inside India and cannot be lost. Downtime during OPD hours is unacceptable. " +
  "Budget is about $900 a month.";

export default function PlanPage() {
  const [description, setDescription] = useState("");
  const [plan, setPlan] = useState<Plan | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run() {
    const text = description.trim() || EXAMPLE;
    setBusy(true);
    setError("");
    try {
      setPlan(await api.plan({ description: text }));
    } catch (cause) {
      /* The message says what to do, not merely that something failed. */
      setError(
        cause instanceof Error
          ? cause.message
          : "Could not reach the planner. Check the API is running on :8010.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex max-w-4xl flex-col gap-8 px-6 py-12">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-tight text-neutral-900">
          Plan an architecture
        </h1>
        <p className="max-w-2xl leading-relaxed text-neutral-600">
          Describe what you need in plain words. Every option you get back meets
          the requirements you stated — a design that does not is shown
          separately, never priced beside them.
        </p>
      </header>

      <section className="flex flex-col gap-3 rounded-xl border border-neutral-200 bg-white p-4">
        <label htmlFor="description" className="text-sm font-medium text-neutral-900">
          What are you building?
        </label>
        <textarea
          id="description"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder={EXAMPLE}
          rows={6}
          className="w-full resize-y rounded-lg border border-neutral-300 p-3 text-sm leading-relaxed text-neutral-900 placeholder:text-neutral-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        />
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={run}
            disabled={busy}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:opacity-60"
          >
            {busy ? "Planning…" : "Plan it"}
          </button>
          {!description.trim() && (
            <span className="text-xs text-neutral-500">
              Leave it blank to use the example.
            </span>
          )}
        </div>
        {error && (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>
        )}
      </section>

      {plan && <PlanView plan={plan} />}
    </main>
  );
}
