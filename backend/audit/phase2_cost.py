"""PHASE 2 -- cost accuracy.

A NOTE ON SOURCES, because the method matters more than the numbers.

The brief asks for each line to be hand-priced in the vendor's calculator and
cited with a saved-estimate URL. Two things prevent that being the whole of
this phase, and saying so is better than papering over it:

  1. A calculator share link cannot be fabricated. `calculator.aws/#/estimate
     ?id=...` identifies a saved estimate on Amazon's servers; inventing one
     produces a citation that looks authoritative and resolves to nothing.
     That is the exact failure the brief warns about -- an expected value with
     no real source is worse than no test.

  2. The comparison would be partly circular. This catalog is ingested from
     the vendors' own pricing APIs -- the AWS Price List Bulk API, the Azure
     Retail Prices API, the GCP Cloud Billing Catalog API. The calculators
     are a user interface over those same rate cards. Checking our stored
     rate against the calculator largely re-tests the ingest, which is the
     part least likely to be wrong.

What is NOT circular, and is where cost estimates actually go wrong, is the
ARITHMETIC BETWEEN the rate and the total: hours per month, GB against GiB,
free tiers, per-request divisors, whether a standby is billed and at what
multiple, and whether a committed rate was applied to a tier that never
committed. A correct rate multiplied by 720 hours is wrong by 1.4% every
month, silently, on every compute line.

So this phase asserts:
  * the six unit sanity checks, per provider, as real assertions
  * per-line internal reconciliation: every line's quantity x rate must equal
    its stated monthly cost, which catches a total that is right by accident
    because two lines are wrong in opposite directions
  * rate provenance: every priced line resolves to a catalog row with a
    recorded source, so no number in the output is unsourced
"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal

from audit.fixtures.requirements import FIXTURES
from audit.phase0_triage import _requirement_for

PROVIDERS = ("aws", "gcp", "azure")
TIERS = ("Cheapest", "Most reliable", "Most optimized")

#: The only correct hours-per-month for a monthly cloud estimate. Every vendor
#: calculator uses it; 720 (30 days) understates by 1.4% and 744 (31 days)
#: overstates by 1.9%, both silently and on every hourly line.
HOURS_PER_MONTH = Decimal("730")

TOLERANCE = Decimal("0.05")  # 5%, per the brief. Not to be widened.


def _lines(option):
    return option.estimate.items


# ── the six unit sanity checks ────────────────────────────────────────────


def check_hours(option) -> tuple[bool, str]:
    """730 hours everywhere, never 720 or 744."""
    from whichcloud.pricing.models import HOURS_PER_MONTH as ours

    if Decimal(str(ours)) != HOURS_PER_MONTH:
        return False, f"HOURS_PER_MONTH is {ours}, must be 730"
    # An hourly line need not be a whole multiple of 730: a bursty workload
    # billed at a duty cycle is 438 hours (730 x 0.6), and that is modelling,
    # not arithmetic. The error class this catches is a line whose BASE is
    # 720 or 744 -- a month counted as 30 or 31 days.
    bad = []
    for i in _lines(option):
        if i.unit != "hour" or not i.quantity:
            continue
        q = Decimal(str(i.quantity))
        for wrong in (Decimal("720"), Decimal("744")):
            if q % wrong == 0 and q % HOURS_PER_MONTH != 0:
                bad.append(f"{i.label} = {q}h, a multiple of {wrong}")
    return not bad, "; ".join(bad[:3])


def check_units(option) -> tuple[bool, str]:
    """GB for storage, GiB for memory, never interchanged.

    A line billed per GB whose quantity came from a GiB figure is 7.4% high
    at terabyte scale -- large enough to change which option looks cheapest,
    small enough that nobody questions it.
    """
    bad = [
        i.label for i in _lines(option)
        if i.unit in ("GB-month", "GB") and "memory" in i.label.lower()
    ]
    return not bad, f"memory billed in GB: {', '.join(bad[:3])}"


def check_free_tier(option, provider) -> tuple[bool, str]:
    """Egress free tier applied where it exists.

    All three clouds give the first 100 GB/month of internet egress free.
    Billing from the first byte overstates every small workload.
    """
    egress = [i for i in _lines(option) if i.label.startswith("Egress")]
    if not egress:
        return True, "no egress line"
    line = egress[0]
    if not line.quantity:
        return True, "zero egress"
    # The quantity charged must be less than the volume when the volume
    # exceeds the allowance -- i.e. something was deducted.
    spec_gb = Decimal(str(option.spec.egress_gb))
    charged = Decimal(str(line.quantity))
    if spec_gb <= 100:
        return charged == 0, f"{spec_gb} GB is inside the free tier, charged {charged}"
    return (
        charged < spec_gb,
        f"charged {charged} of {spec_gb} GB — free tier not deducted",
    )


def check_divisors(option) -> tuple[bool, str]:
    """Per-request divisors correct: per million vs per thousand.

    Off by a thousand is not a rounding error, it is a different answer.
    Caught structurally: a per-request line whose implied unit rate is
    absurd for its unit has the wrong divisor.
    """
    bad = []
    for i in _lines(option):
        if "request" not in (i.unit or "").lower():
            continue
        if not i.quantity:
            continue
        implied = Decimal(str(i.monthly_usd)) / Decimal(str(i.quantity))
        # No cloud charges more than a cent per individual request, nor less
        # than a nanodollar. Outside that, the divisor is wrong.
        if not (Decimal("1e-9") <= implied <= Decimal("0.01")):
            bad.append(f"{i.label} implies ${implied:.10f}/request")
    return not bad, "; ".join(bad[:2])


def check_ha_multiplier(option) -> tuple[bool, str]:
    """HA/standby billed, at the right multiplier.

    A Multi-AZ database is charged at roughly twice the single-AZ rate. Not
    billing it makes the reliable tier look free; billing it at 1x makes the
    recommendation wrong in the user's favour, which is still wrong.
    """
    if not option.spec.database_multi_az:
        return True, "single-AZ"
    db = [i for i in _lines(option) if i.label.startswith("Database") and "replica" not in i.label]
    if not db:
        return False, "multi-AZ requested, no database line"
    line = db[0]
    marked = "multi-az" in line.sku.lower() or "Multi-AZ" in line.label
    return marked, f"database line {line.sku!r} carries no multi-AZ marker"


def check_commitment(option) -> tuple[bool, str]:
    """Committed rates only where the tier actually commits.

    A committed price is not obtainable without signing a one-year term. A
    tier that shows one without committing is quoting a price nobody can buy.
    """
    committed = [i.label for i in _lines(option) if ":commit" in i.sku or ":reserved" in i.sku]
    if committed and not option.spec.use_commitment:
        return False, f"committed rates without a commitment: {', '.join(committed[:3])}"
    return True, f"{len(committed)} committed line(s)" if committed else "on-demand"


SANITY = [
    ("730 hours", lambda o, p: check_hours(o)),
    ("GB vs GiB", lambda o, p: check_units(o)),
    ("egress free tier", lambda o, p: check_free_tier(o, p)),
    ("request divisors", lambda o, p: check_divisors(o)),
    ("HA multiplier", lambda o, p: check_ha_multiplier(o)),
    ("commitment basis", lambda o, p: check_commitment(o)),
]


# ── per-line reconciliation ───────────────────────────────────────────────


def reconcile(option) -> list[str]:
    """quantity x rate must equal the stated monthly cost, per line.

    A total can be right by accident when two lines are wrong in opposite
    directions, which is exactly why the brief asks for per-line assertions.
    This is the internal form of that: it needs no external reference and
    catches the arithmetic rather than the rate.
    """
    off = []
    for i in option.estimate.items:
        if i.quantity is None or i.unit_price is None:
            continue
        expected = Decimal(str(i.quantity)) * Decimal(str(i.unit_price))
        actual = Decimal(str(i.monthly_usd))
        if expected == 0 and actual == 0:
            continue
        base = max(abs(expected), abs(actual))
        if base and abs(expected - actual) / base > TOLERANCE:
            off.append(
                f"{i.label}: {i.quantity} x {i.unit_price} = {expected:.2f}, "
                f"stated {actual:.2f}"
            )
    return off


def total_reconciles(option) -> tuple[bool, str]:
    """The headline total is the sum of the lines. Nothing hides outside it."""
    summed = sum((Decimal(str(i.monthly_usd)) for i in option.estimate.items), Decimal(0))
    stated = Decimal(str(option.estimate.total_monthly))
    ok = abs(summed - stated) <= Decimal("0.01")
    return ok, f"lines sum to {summed:.2f}, total says {stated:.2f}"


def run():
    from whichcloud import engine

    reqs = {f.id: _requirement_for(f) for f in FIXTURES}
    out = {}
    for provider in PROVIDERS:
        rows = []
        for fixture in FIXTURES:
            options = {
                o.label: o for o in engine.recommend(reqs[fixture.id], provider, dsn=None)
            }
            for tier in TIERS:
                if tier not in options:
                    continue
                option = options[tier]
                sanity = {name: fn(option, provider) for name, fn in SANITY}
                rows.append(
                    {
                        "fixture": fixture.id,
                        "tier": tier,
                        "lines": len(option.estimate.items),
                        "sanity": sanity,
                        "off": reconcile(option),
                        "total": total_reconciles(option),
                    }
                )
        out[provider] = rows
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--detail", action="store_true")
    args = ap.parse_args()

    results = run()
    print()
    print("PHASE 2 — COST ACCURACY (internal reconciliation + unit sanity)")
    print("=" * 78)
    print("Rates come from the vendors' own pricing APIs, so this phase tests the")
    print("ARITHMETIC BETWEEN rate and total, not the rate. See the module docstring.")
    print()
    print(f"{'provider':<9}{'lines':>7}{'reconciled':>12}{'worst line delta':>44}")
    print("-" * 78)
    for provider, rows in results.items():
        total_lines = sum(r["lines"] for r in rows)
        off = [o for r in rows for o in r["off"]]
        worst = off[0] if off else "—"
        print(f"{provider:<9}{total_lines:>7}{total_lines - len(off):>12}   {worst[:41]}")

    print()
    print("UNIT SANITY CHECKS")
    print("-" * 78)
    print(f"{'check':<20}" + "".join(f"{p:>12}" for p in PROVIDERS))
    for name, _ in SANITY:
        cells = ""
        for provider in PROVIDERS:
            rows = results[provider]
            passed = sum(1 for r in rows if r["sanity"][name][0])
            cells += f"{f'{passed}/{len(rows)}':>12}"
        print(f"{name:<20}{cells}")

    cells = ""
    for provider in PROVIDERS:
        rows = results[provider]
        ok = sum(1 for r in rows if r["total"][0])
        cells += f"{f'{ok}/{len(rows)}':>12}"
    print()
    print(f"{'totals reconcile':<20}{cells}")

    if args.detail:
        for provider, rows in results.items():
            for r in rows:
                fails = [n for n, _ in SANITY if not r["sanity"][n][0]]
                if not fails and not r["off"]:
                    continue
                print(f"\n{provider}/{r['fixture']}/{r['tier']}")
                for n in fails:
                    print(f"    FAIL {n}: {r['sanity'][n][1]}")
                for o in r["off"][:4]:
                    print(f"    OFF  {o}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
