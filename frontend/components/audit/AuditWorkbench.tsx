"use client";

import { useState } from "react";
import { api, money, type AuditReport } from "@/lib/api";

/**
 * The audit results view.
 *
 * The design rule it follows: a saving with no trade-off attached is a
 * sales figure, not a finding. Every row carries what the technique
 * costs you, and what a billing export CANNOT confirm about whether it
 * applies at all — because a CUR gives a service and a total, and says
 * nothing about whether the workload tolerates an interruption.
 */
export function AuditWorkbench() {
  const [report, setReport] = useState<AuditReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  async function upload(file: File) {
    setBusy(true);
    setError(null);
    setReport(null);
    try {
      setReport(await api.audit(file));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not read that file.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <label className="flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed border-neutral-300 bg-neutral-50 px-6 py-10 text-center hover:border-neutral-400">
        <span className="text-sm font-semibold text-neutral-900">
          {busy ? "Reading…" : "Choose a billing export (.csv)"}
        </span>
        <span className="text-xs text-neutral-500">
          Up to 25 MB. Credits and refunds are skipped — they are not spend.
        </span>
        <input
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          disabled={busy}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void upload(file);
          }}
        />
      </label>

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm leading-relaxed text-red-800">
          {error}
        </div>
      )}

      {report && (
        <>
          <section className="rounded-xl border border-neutral-200 bg-white p-5">
            <div className="flex flex-wrap items-baseline justify-between gap-4">
              <div>
                <div className="text-xs uppercase tracking-wide text-neutral-500">
                  On this bill
                </div>
                <div className="font-mono text-2xl font-semibold tabular-nums text-neutral-900">
                  {money(report.total_monthly_usd)}
                </div>
                <div className="mt-0.5 text-xs text-neutral-500">
                  {report.lines_read.toLocaleString()} line(s) read
                </div>
              </div>
              <div className="text-right">
                <div className="text-xs uppercase tracking-wide text-emerald-700">
                  Worth investigating
                </div>
                <div className="font-mono text-2xl font-semibold tabular-nums text-emerald-700">
                  {money(report.total_saving_usd)}
                </div>
                <div className="mt-0.5 text-xs text-neutral-500">
                  {report.saving_pct}% of the bill
                </div>
              </div>
            </div>
            {/* HOW THE HEADLINE WAS COMPUTED. Without this the number is
                unfalsifiable, and the obvious reading of it — add every
                finding up — is the wrong one. */}
            <p className="mt-3 border-t border-neutral-100 pt-3 text-xs leading-relaxed text-neutral-600">
              {report.saving_basis}
            </p>
          </section>

          {report.warnings.map((w) => (
            <div
              key={w}
              className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm leading-relaxed text-amber-900"
            >
              {w}
            </div>
          ))}

          <section className="rounded-xl border border-neutral-200 bg-white">
            <h2 className="border-b border-neutral-200 px-4 py-3 text-sm font-semibold text-neutral-900">
              Findings
            </h2>
            <ul className="divide-y divide-neutral-100">
              {report.findings.map((f) => {
                const key = f.service + f.technique_id;
                const open = expanded === key;
                return (
                  <li key={key} className="px-4 py-3">
                    <button
                      onClick={() => setExpanded(open ? null : key)}
                      className="flex w-full items-baseline justify-between gap-4 text-left"
                    >
                      <div className="min-w-0">
                        <div className="truncate text-sm font-medium text-neutral-900">
                          {f.technique}
                        </div>
                        <div className="truncate text-xs text-neutral-500">
                          {f.service} · {money(f.monthly_usd)}/month today
                        </div>
                      </div>
                      <div className="shrink-0 font-mono text-sm tabular-nums text-emerald-700">
                        −{money(f.saved_monthly_usd)}
                      </div>
                    </button>

                    {open && (
                      <div className="mt-3 flex flex-col gap-3 border-l-2 border-neutral-200 pl-3">
                        <p className="text-sm leading-relaxed text-neutral-700">
                          {f.summary}
                        </p>

                        {/* NOT MEASURED, AND IT SAYS SO. The Design path
                            prices the swap against the catalog; this one
                            estimates from a cited figure, and blurring
                            the two would be the dishonesty the whole
                            project is against. */}
                        {!f.measured && (
                          <p className="text-xs leading-relaxed text-neutral-600">
                            <span className="font-semibold">Estimated</span>, not
                            measured — a billing export gives a service and a
                            total, not the instance family needed to price the
                            swap exactly. Basis: {f.basis}
                          </p>
                        )}

                        {f.needs_confirmation.length > 0 && (
                          <div>
                            <div className="text-xs font-semibold text-amber-800">
                              Only applies if — a bill cannot tell us these
                            </div>
                            <ul className="mt-1 list-disc space-y-0.5 pl-5">
                              {f.needs_confirmation.map((c) => (
                                <li key={c} className="text-xs leading-relaxed text-amber-900">
                                  {c}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {f.tradeoffs.length > 0 && (
                          <div>
                            <div className="text-xs font-semibold text-neutral-900">
                              What it costs you
                            </div>
                            <ul className="mt-1 list-disc space-y-0.5 pl-5">
                              {f.tradeoffs.map((t) => (
                                <li key={t} className="text-xs leading-relaxed text-neutral-700">
                                  {t}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {f.tool && (
                          <div className="text-xs text-neutral-600">
                            Implemented with{" "}
                            {f.tool_url ? (
                              <a
                                href={f.tool_url}
                                target="_blank"
                                rel="noreferrer"
                                className="font-medium text-blue-700 underline"
                              >
                                {f.tool}
                              </a>
                            ) : (
                              <span className="font-medium">{f.tool}</span>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          </section>

          {/* COVERAGE, HONESTLY. "We looked and found nothing" and "we did
              not look" are different claims, and dropping the second is
              how a report implies completeness it does not have. */}
          {report.reviewed_no_finding.length > 0 && (
            <section className="rounded-xl border border-neutral-200 bg-white">
              <h2 className="border-b border-neutral-200 px-4 py-3 text-sm font-semibold text-neutral-900">
                Reviewed, nothing found
              </h2>
              <ul className="divide-y divide-neutral-100">
                {report.reviewed_no_finding.map((r) => (
                  <li key={r.service} className="px-4 py-2.5">
                    <div className="flex items-baseline justify-between gap-4">
                      <span className="text-sm text-neutral-900">{r.service}</span>
                      <span className="font-mono text-sm tabular-nums text-neutral-500">
                        {money(r.monthly_usd)}
                      </span>
                    </div>
                    <div className="mt-0.5 text-xs leading-relaxed text-neutral-500">
                      {r.why}
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </div>
  );
}
