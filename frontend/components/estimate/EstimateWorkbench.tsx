"use client";

import { useState } from "react";
import { PricedDiagram } from "@/components/PricedDiagram";
import { money, type Option, type Recommendation } from "@/lib/api";

/**
 * The estimate page: requirements in, three priced architectures out.
 *
 * Two ways in, deliberately. The form needs no model and no key, returns in
 * milliseconds, and cannot be broken by a quota — so the page always works.
 * Plain English is the fast path on top, not the only path, and when it is
 * used the interface reports what the model assumed rather than presenting
 * guesses as though they were stated.
 */

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

const WORKLOADS = [
  ["web", "Web app"],
  ["api", "API"],
  ["batch", "Batch job"],
  ["ml", "ML / training"],
  ["storage", "Storage"],
] as const;

const SCALES = [
  ["low", "Low", "a few thousand users"],
  ["medium", "Medium", "tens of thousands"],
  ["high", "High", "hundreds of thousands"],
] as const;

type Form = {
  goal: string;
  workload_type: string;
  traffic_scale: string;
  traffic_pattern: string;
  budget_monthly_usd: number | null;
  storage_gb: number;
  egress_gb: number;
  interruptible: boolean;
  arm_compatible: boolean;
};

const DEFAULTS: Form = {
  goal: "an online shop",
  workload_type: "web",
  traffic_scale: "medium",
  traffic_pattern: "spiky",
  budget_monthly_usd: 400,
  storage_gb: 200,
  egress_gb: 500,
  interruptible: false,
  arm_compatible: true,
};

function Segmented({
  options,
  value,
  onChange,
}: {
  options: readonly (readonly [string, string, string?])[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map(([v, label, hint]) => (
        <button
          key={v}
          type="button"
          onClick={() => onChange(v)}
          title={hint}
          className={`rounded-lg border px-3.5 py-2 text-[14px] font-medium transition-colors ${
            value === v
              ? "border-accent bg-accent-wash text-accent"
              : "border-line bg-white text-ink-2 hover:border-line-strong hover:bg-sunk"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-2 text-[14px] font-medium">{label}</div>
      {children}
    </div>
  );
}

function NumberInput({
  value,
  onChange,
  suffix,
}: {
  value: number | null;
  onChange: (n: number | null) => void;
  suffix: string;
}) {
  return (
    <div className="flex w-fit items-center gap-2 rounded-lg border border-line-strong px-3 py-2">
      <input
        type="number"
        min={0}
        inputMode="numeric"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
        className="tnum w-24 bg-transparent font-mono text-[15px] outline-none"
      />
      <span className="text-[13px] font-medium text-ink-3">{suffix}</span>
    </div>
  );
}

export function EstimateWorkbench() {
  const [mode, setMode] = useState<"form" | "describe">("form");
  const [form, setForm] = useState<Form>(DEFAULTS);
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Recommendation | null>(null);
  const [active, setActive] = useState(1);

  const set = <K extends keyof Form>(k: K, v: Form[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  async function run() {
    setBusy(true);
    setError(null);
    try {
      const [path, body] =
        mode === "describe"
          ? ["/describe", { description }]
          : ["/recommend", form];
      const res = await fetch(`${BASE}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Could not price that.");
      setResult(data);
      setActive(Math.min(1, data.options.length - 1));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      setResult(null);
    } finally {
      setBusy(false);
    }
  }

  const option: Option | null = result?.options[active] ?? null;

  return (
    <div className="flex flex-col gap-8">
      {/* ── input ── */}
      <div className="rounded-xl border border-line bg-white p-6">
        <div className="mb-6 flex gap-1.5">
          {(["form", "describe"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className={`rounded-lg px-4 py-2 text-[14px] font-medium transition-colors ${
                mode === m ? "bg-ink text-white" : "text-ink-2 hover:bg-sunk"
              }`}
            >
              {m === "form" ? "Set the details" : "Describe it"}
            </button>
          ))}
        </div>

        {mode === "describe" ? (
          <div>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="A food delivery app for one city. About 80,000 customers, mostly ordering at lunch and dinner. Budget around $500 a month."
              className="w-full resize-none rounded-lg border border-line-strong px-4 py-3 text-[16px] leading-relaxed outline-none placeholder:text-ink-3 focus:border-accent"
            />
            <p className="mt-2 text-[13px] font-medium text-ink-3">
              Needs a model API key on the server. The form works without one.
            </p>
          </div>
        ) : (
          <div className="grid gap-6 sm:grid-cols-2">
            <Field label="What are you building?">
              <Segmented
                options={WORKLOADS}
                value={form.workload_type}
                onChange={(v) => set("workload_type", v)}
              />
            </Field>

            <Field label="How much traffic?">
              <Segmented
                options={SCALES}
                value={form.traffic_scale}
                onChange={(v) => set("traffic_scale", v)}
              />
            </Field>

            <Field label="Traffic pattern">
              <Segmented
                options={[
                  ["spiky", "Spiky"],
                  ["steady", "Steady"],
                ]}
                value={form.traffic_pattern}
                onChange={(v) => set("traffic_pattern", v)}
              />
            </Field>

            <Field label="Can the work be restarted?">
              <Segmented
                options={[
                  ["no", "No — serves live users"],
                  ["yes", "Yes"],
                ]}
                value={form.interruptible ? "yes" : "no"}
                onChange={(v) => set("interruptible", v === "yes")}
              />
            </Field>

            <Field label="Monthly budget">
              <NumberInput
                value={form.budget_monthly_usd}
                onChange={(n) => set("budget_monthly_usd", n)}
                suffix="USD"
              />
            </Field>

            <Field label="Storage and egress">
              <div className="flex flex-wrap gap-2">
                <NumberInput
                  value={form.storage_gb}
                  onChange={(n) => set("storage_gb", n ?? 0)}
                  suffix="GB stored"
                />
                <NumberInput
                  value={form.egress_gb}
                  onChange={(n) => set("egress_gb", n ?? 0)}
                  suffix="GB out"
                />
              </div>
            </Field>
          </div>
        )}

        <div className="mt-6 flex items-center gap-4">
          <button
            type="button"
            onClick={run}
            disabled={busy || (mode === "describe" && !description.trim())}
            className="rounded-lg bg-accent px-6 py-3 text-[15px] font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40"
          >
            {busy ? "Pricing…" : "Price it"}
          </button>
          {error && (
            <span className="text-[14px] font-medium text-spend">{error}</span>
          )}
        </div>
      </div>

      {/* ── result ── */}
      {result && option && (
        <div className="flex flex-col gap-5">
          {(result.assumed.length > 0 || result.clarifying_question) && (
            <div className="rounded-xl border border-caution/30 bg-caution-wash px-5 py-4">
              {result.assumed.length > 0 && (
                <p className="text-[14.5px] font-medium text-ink-2">
                  <span className="text-caution">Assumed, not stated:</span>{" "}
                  {result.assumed.join(", ")}
                </p>
              )}
              {result.clarifying_question && (
                <p className="mt-1.5 text-[14.5px] font-medium text-ink-2">
                  <span className="text-caution">Worth answering:</span>{" "}
                  {result.clarifying_question}
                </p>
              )}
            </div>
          )}

          <div role="tablist" className="grid gap-3 sm:grid-cols-3">
            {result.options.map((o, i) => (
              <button
                key={o.label}
                role="tab"
                aria-selected={i === active}
                onClick={() => setActive(i)}
                className={`rounded-xl border px-5 py-4 text-left transition-all ${
                  i === active
                    ? "border-accent bg-accent-wash"
                    : "border-line bg-white hover:border-line-strong hover:bg-sunk"
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="text-[16px] font-semibold">{o.label}</span>
                  {o.within_budget === true && (
                    <span className="rounded-full bg-accent px-2 py-0.5 text-[11px] font-semibold uppercase text-white">
                      In budget
                    </span>
                  )}
                  {o.within_budget === false && (
                    <span className="rounded-full bg-spend px-2 py-0.5 text-[11px] font-semibold uppercase text-white">
                      Over
                    </span>
                  )}
                </div>
                {/* Partial totals read as floors, not prices. */}
                <div
                  className={`tnum mt-1.5 font-mono text-[28px] font-semibold leading-none ${
                    o.complete ? "" : "text-ink-3"
                  }`}
                >
                  {!o.complete && (
                    <span className="mr-0.5 text-[21px] font-normal">&ge;</span>
                  )}
                  {money(o.monthly_usd, 0)}
                  <span className="ml-1 text-[15px] font-normal text-ink-3">/mo</span>
                </div>
                {o.measured_saving_usd > 0 && (
                  <div className="mt-2 font-mono text-[13px] font-medium text-accent">
                    {money(o.measured_saving_usd)} saved by {o.applied.length}{" "}
                    optimization{o.applied.length === 1 ? "" : "s"}
                  </div>
                )}
              </button>
            ))}
          </div>

          <PricedDiagram option={option} provider={option.provider} />

          <div className="grid gap-5 lg:grid-cols-2">
            <div className="rounded-xl border border-line bg-white p-5">
              <h3 className="text-[16px] font-semibold">Cost breakdown</h3>
              <table className="mt-4 w-full">
                <tbody className="font-mono text-[14px]">
                  {option.items.map((i) => (
                    <tr key={i.label} className="border-b border-line last:border-0">
                      <td className="py-2.5 pr-3 font-medium">{i.label}</td>
                      <td className="py-2.5 pr-3 text-ink-3">{i.sku}</td>
                      <td className="tnum py-2.5 text-right font-medium">
                        {money(i.monthly_usd)}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t border-line-strong">
                    <td className="pt-3 text-[15px] font-semibold" colSpan={2}>
                      Total
                    </td>
                    <td className="tnum pt-3 text-right font-mono text-[17px] font-semibold">
                      {money(option.monthly_usd)}
                    </td>
                  </tr>
                </tfoot>
              </table>
              {option.missing.length > 0 && (
                <p className="mt-3 text-[13.5px] font-medium text-caution">
                  Not priced: {option.missing.join(", ")}
                </p>
              )}
            </div>

            <div className="flex flex-col gap-5">
              <div className="rounded-xl border border-line bg-white p-5">
                <h3 className="text-[16px] font-semibold">Optimizations applied</h3>
                <div className="mt-4 space-y-3.5">
                  {option.applied.map((t) => (
                    <div key={t.id} className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="text-[14.5px] font-medium leading-snug">
                          {t.name}
                        </div>
                        <div className="mt-0.5 font-mono text-[13px] font-medium text-ink-3">
                          vs {t.versus_sku} · {t.tool}
                        </div>
                      </div>
                      <span className="tnum shrink-0 font-mono text-[14px] font-semibold text-accent">
                        −{money(t.saved_monthly_usd ?? 0)}
                      </span>
                    </div>
                  ))}
                  {option.advisory.map((t) => (
                    <div key={t.id} className="border-t border-line pt-3">
                      <div className="text-[14.5px] font-medium text-ink-2">{t.name}</div>
                      <div className="mt-0.5 font-mono text-[13px] font-medium text-caution">
                        not priced — depends on your workload
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {option.tradeoffs.length > 0 && (
                <div className="rounded-xl border border-line bg-sunk p-5">
                  <h3 className="text-[16px] font-semibold">What you give up</h3>
                  <ul className="mt-3 space-y-2">
                    {option.tradeoffs.map((t) => (
                      <li
                        key={t}
                        className="flex gap-2.5 text-[14px] font-medium leading-relaxed text-ink-2"
                      >
                        <span className="mt-[9px] h-1 w-1 shrink-0 rounded-full bg-ink-3" />
                        {t}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>

          {result.not_applied.length > 0 && (
            <div className="rounded-xl border border-line bg-white p-5">
              <h3 className="text-[16px] font-semibold">Not applied, and why</h3>
              <div className="mt-3 space-y-2">
                {result.not_applied.map((t) => (
                  <p key={t.id} className="text-[14px] font-medium text-ink-2">
                    <span className="font-semibold text-ink">{t.name}</span> — {t.reason}
                  </p>
                ))}
              </div>
            </div>
          )}

          <p className="text-[13.5px] font-medium leading-relaxed text-ink-3">
            {result.sizing_basis}
          </p>
        </div>
      )}
    </div>
  );
}
