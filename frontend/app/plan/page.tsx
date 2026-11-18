"use client";

import { useRef, useState } from "react";
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
  const [plannedDescription, setPlannedDescription] = useState("");
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const reqIdRef = useRef(0);

  async function run() {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const reqId = ++reqIdRef.current;

    const text = description.trim() || EXAMPLE;
    setBusy(true);
    setError("");
    setPlan(null);
    setGeneratedAt(null);
    try {
      const next = await api.plan({ description: text }, controller.signal);
      if (controller.signal.aborted || reqId !== reqIdRef.current) return;
      setPlan(next);
      setPlannedDescription(text);
      setGeneratedAt(
        new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        })
      );
    } catch (cause) {
      if (controller.signal.aborted || reqId !== reqIdRef.current) return;
      setPlan(null);
      setError(
        cause instanceof Error
          ? cause.message
          : "Could not reach the planner. Please try again in a moment.",
      );
    } finally {
      if (!controller.signal.aborted && reqId === reqIdRef.current) {
        setBusy(false);
      }
    }
  }

  return (
    <main className="mx-auto flex max-w-4xl flex-col gap-8 px-6 py-12">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-tight text-ink">
          Plan an architecture
        </h1>
        <p className="max-w-2xl leading-relaxed text-ink-2">
          Describe what you need in plain words. Every option you get back meets
          the requirements you stated — a design that does not is shown
          separately, never priced beside them.
        </p>
      </header>

      <section className="flex flex-col gap-3 rounded-xl border border-line bg-surface p-4">
        <label htmlFor="description" className="text-sm font-medium text-ink">
          What are you building?
        </label>
        <textarea
          id="description"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder={EXAMPLE}
          rows={6}
          className="w-full resize-y rounded-lg border border-line-strong p-3 text-sm leading-relaxed text-ink placeholder:text-ink-3 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
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
            <span className="text-xs text-ink-3">
              Leave it blank to use the example.
            </span>
          )}
        </div>
        {error && (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>
        )}
      </section>

      {plan && (
        <>
          {generatedAt && (
            <div data-testid="generated-for-stamp" className="font-mono text-xs text-ink-3">
              Generated for: {plannedDescription.slice(0, 60)}
              {plannedDescription.length > 60 ? "…" : ""} at {generatedAt}
            </div>
          )}
          <PlanView plan={plan} description={plannedDescription} />
        </>
      )}
    </main>
  );
}
