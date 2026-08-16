import { api } from "@/lib/api";
import { Reveal } from "@/components/landing/Reveal";

/**
 * The evidence for the claim the rest of the page makes.
 *
 * "Computed, not guessed" appears four times before this section and is
 * demonstrated in none of them, which leaves the page's central claim resting
 * on the reader's willingness to believe it. This is the working: where every
 * price came from, and what happened when they were checked against a second
 * source that has no reason to agree.
 *
 * The split is counted from the catalog at render. The validation runs are
 * dated and attributed instead, because they call external APIs and cannot
 * honestly be presented as live -- a figure that took an hour to measure
 * should not be dressed up as one measured just now.
 */

/* Measured by scripts/validate_prices.py and scripts/validate_gcp_compute.py.
   Each row names the source it was checked against, and that source is always
   a different one from the source the price came from -- checking a feed
   against itself would agree every time and prove nothing. */
const RUNS = [
  {
    provider: "AWS",
    checked: "AWS Price List Bulk API",
    matched: 807,
    of: 807,
    pct: "100.0%",
    note: "Every instance type in both sources agrees to the cent.",
  },
  {
    provider: "Azure",
    checked: "Vantage instance catalog",
    matched: 923,
    of: 928,
    pct: "99.5%",
    note: "Five disagree, all M and F series. Under investigation.",
  },
  {
    provider: "GCP",
    checked: "Cloud Billing Catalog API",
    matched: 292,
    of: 322,
    pct: "90.7%",
    note: "30 C4D highmem run 3.37% high: one RAM rate per family.",
  },
] as const;

const MEASURED_ON = "16 August 2026";

/* Ordered so the bar reads fetched-first, which is also largest-first. */
const KINDS = [
  {
    key: "fetched",
    label: "Fetched",
    bar: "bg-accent",
    body: "Returned by the provider's own pricing API and stored exactly as it arrived.",
  },
  {
    key: "composed",
    label: "Composed",
    bar: "bg-[#7BA4F5]",
    body: "The provider sells the parts, not the whole. Cloud SQL quotes vCPU and RAM separately, so a 2-vCPU, 8 GB instance is their vCPU rate twice plus their RAM rate eight times. Every term is theirs.",
  },
  {
    key: "derived",
    label: "Derived",
    bar: "bg-[#B9CDF9]",
    body: "A documented multiplier on a fetched rate. Azure bills an HA standby as a second instance, so multi-AZ is twice the primary.",
  },
] as const;

export async function Provenance() {
  let total = 0;
  let split: Record<string, number> = {};
  try {
    const p = await api.provenance();
    total = p.total;
    split = p.split;
  } catch {
    /* The section still stands on the validation runs alone. */
  }

  const pct = (n: number) => (total ? (n / total) * 100 : 0);

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mx-auto mb-12 max-w-2xl text-center">
        <div className="font-mono text-[13.5px] uppercase tracking-[0.14em] text-accent font-medium">
          Provenance
        </div>
        <h2 className="mt-3 text-balance text-[clamp(1.75rem,3.6vw,2.5rem)] font-semibold leading-tight tracking-[-0.025em]">
          Checked against the source
        </h2>
        <p className="mt-4 text-[16px] leading-relaxed text-ink-2">
          Saying the prices are real is easy. This is how they can be checked:
          where each one came from, and what happened when the catalog was
          compared against a second source with no reason to agree with it.
        </p>
      </div>

      {/* ── where the numbers came from ── */}
      <Reveal className="rounded-2xl border border-line bg-surface p-6 elev-2 sm:p-8">
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <h3 className="text-[17px] font-semibold tracking-[-0.015em]">
            Every price in the catalog
          </h3>
          <span className="tnum font-mono text-[13px] text-ink-3">
            {total ? `${total.toLocaleString()} priced items` : "catalog unreachable"}
          </span>
        </div>

        {total > 0 && (
          <>
            {/* One bar rather than three, because the proportion is the
                finding: the composed and derived slivers are almost invisible
                at true scale, and that is the honest picture. */}
            <div
              className="mt-5 flex h-3 w-full overflow-hidden rounded-full bg-sunk"
              role="img"
              aria-label={KINDS.map(
                (k) => `${k.label} ${(split[k.key] ?? 0).toLocaleString()}`,
              ).join(", ")}
            >
              {KINDS.map((k) => {
                const n = split[k.key] ?? 0;
                if (!n) return null;
                return (
                  <span
                    key={k.key}
                    className={`${k.bar} h-full`}
                    /* A hairline minimum, so a real 0.28% stays visible
                       instead of rounding away to nothing. */
                    style={{ width: `max(3px, ${pct(n)}%)` }}
                  />
                );
              })}
            </div>

            <dl className="mt-6 grid gap-6 sm:grid-cols-3">
              {KINDS.map((k) => {
                const n = split[k.key] ?? 0;
                return (
                  <div key={k.key}>
                    <dt className="flex items-baseline gap-2">
                      <span className={`${k.bar} h-2.5 w-2.5 shrink-0 rounded-[2px]`} />
                      <span className="text-[15px] font-semibold">{k.label}</span>
                      <span className="tnum ml-auto font-mono text-[13px] text-ink-3">
                        {pct(n).toFixed(2)}%
                      </span>
                    </dt>
                    <dd className="mt-1.5 tnum font-mono text-[19px] font-semibold tracking-tight">
                      {n.toLocaleString()}
                    </dd>
                    <dd className="mt-2 text-[14px] leading-relaxed text-ink-2">
                      {k.body}
                    </dd>
                  </div>
                );
              })}
            </dl>
          </>
        )}

        <p className="mt-6 border-t border-line pt-4 text-[14.5px] leading-relaxed text-ink-2">
          There is no fourth category. A price that cannot be reached one of
          these three ways is reported as missing, and an estimate with a
          missing part never wins a comparison.
        </p>
      </Reveal>

      {/* ── what happened when they were checked ── */}
      <Reveal className="mt-6 overflow-hidden rounded-2xl border border-line bg-surface elev-2">
        <div className="flex flex-wrap items-baseline justify-between gap-3 border-b border-line px-6 py-5 sm:px-8">
          <h3 className="text-[17px] font-semibold tracking-[-0.015em]">
            Checked against a second source
          </h3>
          <span className="font-mono text-[13px] text-ink-3">
            measured {MEASURED_ON}
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-line font-mono text-[11.5px] uppercase tracking-[0.09em] text-ink-3">
                <th className="px-6 py-3 font-medium sm:px-8">Catalog</th>
                <th className="px-6 py-3 font-medium">Checked against</th>
                <th className="px-6 py-3 text-right font-medium">Agreed</th>
                <th className="px-6 py-3 text-right font-medium sm:px-8">Rate</th>
              </tr>
            </thead>
            <tbody>
              {RUNS.map((r) => (
                <tr key={r.provider} className="border-b border-line last:border-0 align-top">
                  <td className="px-6 py-4 sm:px-8">
                    <div className="text-[15px] font-semibold">{r.provider}</div>
                    <div className="mt-1 max-w-[22rem] text-[13.5px] leading-relaxed text-ink-3">
                      {r.note}
                    </div>
                  </td>
                  <td className="px-6 py-4 text-[14px] text-ink-2">{r.checked}</td>
                  <td className="tnum px-6 py-4 text-right font-mono text-[14px] text-ink-2">
                    {r.matched}/{r.of}
                  </td>
                  <td className="tnum px-6 py-4 text-right font-mono text-[16px] font-semibold sm:px-8">
                    {r.pct}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <p className="border-t border-line px-6 py-4 text-[14px] leading-relaxed text-ink-3 sm:px-8">
          GCP is the weakest of the three and is printed here at its measured
          rate rather than rounded up. A further 139 machine types are excluded
          from that run, not passed by it: local SSD, GPU and bare metal carry
          attached hardware the comparison does not model, so counting them
          would be measuring the method rather than the price.
        </p>
      </Reveal>
    </div>
  );
}
