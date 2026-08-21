"use client";

import { useState } from "react";
import type { Plan, PlanTier } from "@/lib/api";
import { money } from "@/lib/api";

/* The reasoning layer, rendered.
 *
 * Two decisions shape this file. The recommended tier is selected on load
 * rather than the cheapest, because whichever number a reader sees first
 * becomes the frame for every comparison after it. And the design that
 * fails a stated requirement is not one of the three — it sits collapsed
 * at the bottom with its violations, because a cheap figure placed beside
 * two dearer ones wins arguments on price alone. */

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1">
      <span className="text-xs uppercase tracking-wide text-neutral-500">{label}</span>
      <span className="font-mono text-sm text-neutral-900">{value}</span>
    </div>
  );
}

function TierCard({
  tier,
  selected,
  onSelect,
}: {
  tier: PlanTier;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={`flex flex-col gap-2 rounded-xl border p-4 text-left transition ${
        selected
          ? "border-indigo-500 bg-indigo-50/60 ring-1 ring-indigo-500"
          : "border-neutral-200 bg-white hover:border-neutral-300"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-semibold text-neutral-900">{tier.label}</span>
        {selected && (
          <span className="rounded bg-indigo-600 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white">
            Recommended
          </span>
        )}
      </div>
      <div className="font-mono text-2xl font-semibold text-neutral-900">
        {money(tier.monthly_total)}
        <span className="text-sm font-normal text-neutral-500">/mo</span>
      </div>
      <p className="text-xs leading-relaxed text-neutral-600">{tier.philosophy}</p>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-neutral-600">
        <span>RTO {tier.rto}</span>
        <span>RPO {tier.rpo}</span>
      </div>
      {!tier.within_budget && (
        <span className="text-xs font-medium text-amber-700">Over budget</span>
      )}
    </button>
  );
}

export function PlanView({ plan }: { plan: Plan }) {
  const [selected, setSelected] = useState(plan.default_tier);
  const tier = plan.tiers.find((t) => t.name === selected) ?? plan.tiers[0];
  const [showBelow, setShowBelow] = useState(false);

  return (
    <div className="flex flex-col gap-8">
      {/* ── what it was sized from ── */}
      <section className="rounded-xl border border-neutral-200 bg-white p-4">
        <h3 className="text-sm font-semibold text-neutral-900">Sized from</h3>
        <div className="mt-2 flex flex-wrap gap-x-8 gap-y-1">
          <Row label="average" value={`${plan.sizing_basis.avg_rps} req/sec`} />
          <Row label="peak" value={`${plan.sizing_basis.peak_rps} req/sec`} />
          <Row label="band" value={plan.sizing_basis.tier} />
        </div>
        <p className="mt-2 text-sm leading-relaxed text-neutral-600">
          {plan.sizing_basis.sized_from}
        </p>
      </section>

      {/* ── the network shape, and why ── */}
      {plan.network_topology_reason && (
        <section className="rounded-xl border border-neutral-200 bg-white p-4">
          <h3 className="text-sm font-semibold text-neutral-900">
            Network shape: {plan.network_topology}
          </h3>
          <p className="mt-2 text-sm leading-relaxed text-neutral-600">
            {plan.network_topology_reason}
          </p>
        </section>
      )}

      {/* ── whether this description matched a known service shape ── */}
      {plan.archetype_note && (
        <section className="rounded-xl border border-neutral-200 bg-white p-4">
          <h3 className="text-sm font-semibold text-neutral-900">
            Workload shape: {plan.archetype}
          </h3>
          <p className="mt-2 text-sm leading-relaxed text-neutral-600">
            {plan.archetype_note}
          </p>
        </section>
      )}

      {/* ── the three compliant options ── */}
      <section className="flex flex-col gap-3">
        <h3 className="text-sm font-semibold text-neutral-900">
          Three options, all meeting your stated requirements
        </h3>
        <div className="grid gap-3 sm:grid-cols-3">
          {plan.tiers.map((t) => (
            <TierCard
              key={t.name}
              tier={t}
              selected={t.name === selected}
              onSelect={() => setSelected(t.name)}
            />
          ))}
        </div>
      </section>

      {/* ── the selected tier's bill ── */}
      <section className="rounded-xl border border-neutral-200 bg-white">
        <div className="border-b border-neutral-200 px-4 py-3">
          <h3 className="text-sm font-semibold text-neutral-900">
            {tier.label} — line items
          </h3>
        </div>
        <div className="divide-y divide-neutral-100">
          {tier.components.map((c) => (
            <div key={c.label + c.sku} className="flex items-baseline justify-between gap-4 px-4 py-2">
              <div className="min-w-0">
                <div className="truncate text-sm text-neutral-900">{c.label}</div>
                <div className="truncate font-mono text-xs text-neutral-500">{c.sku}</div>
              </div>
              <div className="shrink-0 font-mono text-sm tabular-nums text-neutral-900">
                {money(c.monthly_usd)}
              </div>
            </div>
          ))}
        </div>
        <div className="flex items-baseline justify-between border-t border-neutral-200 px-4 py-3">
          <span className="text-sm font-semibold text-neutral-900">Every month</span>
          <span className="font-mono text-lg font-semibold tabular-nums text-neutral-900">
            {money(tier.monthly_total)}
          </span>
        </div>
        {tier.committed_use_note && (
          <p className="border-t border-neutral-100 px-4 py-2 text-xs leading-relaxed text-neutral-500">
            {tier.committed_use_note}
          </p>
        )}
      </section>

      {/* ── non-fatal findings from validation, e.g. NAT costing more than
           trivial compute -- a fact about small workloads, not an error ── */}
      {tier.warnings.length > 0 && (
        <section className="rounded-xl border border-amber-200 bg-amber-50/50 p-4">
          <ul className="flex flex-col gap-1.5">
            {tier.warnings.map((w) => (
              <li key={w} className="text-sm leading-relaxed text-amber-900/90">
                {w}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* ── what changed vs. the tier below, and the risk each change removes ── */}
      {(tier.pattern_diff_vs_previous_tier.length > 0 || tier.no_further_improvement) && (
        <section className="flex flex-col gap-2">
          <h3 className="text-sm font-semibold text-neutral-900">
            What changed from the tier below
          </h3>
          {tier.no_further_improvement ? (
            <p className="text-sm text-neutral-600">{tier.no_further_improvement}</p>
          ) : (
            <ul className="flex flex-col gap-1.5">
              {tier.pattern_diff_vs_previous_tier.map((d) => (
                <li key={d} className="text-sm leading-relaxed text-neutral-700">
                  {d}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {/* ── why each addition is there ── */}
      {Object.keys(tier.justifications).length > 0 && (
        <section className="flex flex-col gap-2">
          <h3 className="text-sm font-semibold text-neutral-900">
            Why these were added
          </h3>
          <ul className="flex flex-col gap-1.5">
            {Object.entries(tier.justifications).map(([component, why]) => (
              <li key={component} className="text-sm text-neutral-700">
                <span className="font-mono text-xs text-neutral-500">{component}</span>{" "}
                — {why}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* ── what was deliberately left out ──
           The differentiator: an architecture that quietly omits a CDN looks
           identical to one that never considered it. */}
      {plan.excluded_with_reason.length > 0 && (
        <section className="rounded-xl border border-emerald-200 bg-emerald-50/50 p-4">
          <h3 className="text-sm font-semibold text-emerald-900">
            Left out on purpose
          </h3>
          <ul className="mt-2 flex flex-col gap-1.5">
            {plan.excluded_with_reason.map((line) => (
              <li key={line} className="text-sm leading-relaxed text-emerald-900/90">
                {line}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* ── recovery objectives ── */}
      <section className="rounded-xl border border-neutral-200 bg-white p-4">
        <h3 className="text-sm font-semibold text-neutral-900">If something fails</h3>
        <div className="mt-2 grid gap-x-8 sm:grid-cols-2">
          <Row label="zone loss — back in" value={tier.rto} />
          <Row label="zone loss — data lost" value={tier.rpo} />
          <Row label="region loss — back in" value={tier.region_rto} />
          <Row label="region loss — data lost" value={tier.region_rpo} />
        </div>
        {tier.gives_up.length > 0 && (
          <ul className="mt-3 flex flex-col gap-1.5 border-t border-neutral-100 pt-3">
            {tier.gives_up.map((gap) => (
              <li key={gap} className="text-sm text-neutral-600">{gap}</li>
            ))}
          </ul>
        )}
      </section>

      {/* ── obligations, by lookup ── */}
      {plan.compliance_notes.length > 0 && (
        <section className="flex flex-col gap-3">
          <h3 className="text-sm font-semibold text-neutral-900">
            What applies to you
          </h3>
          {plan.compliance_notes.map((note) => (
            <div
              key={note.regulation}
              className="rounded-xl border border-neutral-200 bg-white p-4"
            >
              <div className="text-sm font-semibold text-neutral-900">
                {note.regulation}
              </div>
              <p className="mt-1 text-sm text-neutral-600">{note.obligation}</p>
              <p className="mt-2 text-sm text-neutral-900">
                <span className="text-xs uppercase tracking-wide text-neutral-500">
                  satisfied by{" "}
                </span>
                {note.control}
              </p>
            </div>
          ))}
        </section>
      )}

      {/* ── assumptions, each with the question that replaces it ── */}
      {plan.assumed_fields.length > 0 && (
        <section className="rounded-xl border border-amber-200 bg-amber-50/60 p-4">
          <h3 className="text-sm font-semibold text-amber-900">
            We had to assume {plan.assumed_fields.length}{" "}
            {plan.assumed_fields.length === 1 ? "thing" : "things"}
          </h3>
          <ul className="mt-2 flex flex-col gap-2">
            {plan.assumed_fields.map((a) => (
              <li key={a.field} className="text-sm text-amber-900/90">
                <span className="font-mono text-xs">{a.field}</span> ={" "}
                <span className="font-mono text-xs">{String(a.assumption)}</span>
                <div className="text-amber-900/70">{a.question}</div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* ── budget ── */}
      {plan.unspent_budget && (
        <section className="rounded-xl border border-neutral-200 bg-white p-4">
          <h3 className="text-sm font-semibold text-neutral-900">
            {money(plan.unspent_budget.amount_usd)} unspent
          </h3>
          <p className="mt-1 text-sm leading-relaxed text-neutral-600">
            {plan.unspent_budget.note}
          </p>
        </section>
      )}
      {plan.over_budget_note && (
        <section className="rounded-xl border border-amber-300 bg-amber-50 p-4">
          <p className="text-sm font-medium text-amber-900">{plan.over_budget_note}</p>
        </section>
      )}

      {/* ── the design that does not qualify ── */}
      {plan.below_requirements_panel && (
        <section className="rounded-xl border border-neutral-200 bg-neutral-50">
          <button
            type="button"
            onClick={() => setShowBelow((v) => !v)}
            aria-expanded={showBelow}
            className="flex w-full items-center justify-between px-4 py-3 text-left"
          >
            <span className="text-sm font-medium text-neutral-700">
              {plan.below_requirements_panel.label}
            </span>
            <span className="font-mono text-xs text-neutral-500">
              {showBelow ? "hide" : "show"}
            </span>
          </button>
          {showBelow && (
            <div className="border-t border-neutral-200 px-4 py-3">
              <ul className="flex flex-col gap-1.5">
                {plan.below_requirements_panel.violations.map((v) => (
                  <li key={v} className="text-sm text-neutral-700">
                    It {v}
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-sm text-neutral-500">
                {plan.below_requirements_panel.note}
              </p>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
