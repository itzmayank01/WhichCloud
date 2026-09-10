"""Why is a tier ever DEARER at a lower budget?

Budget can only reject or degrade, so a smaller budget can only ever produce
the same architecture or a lesser one. A lesser architecture that costs MORE
is not a policy anyone wrote; it is a mechanism nobody intended.

This does not fix it. It finds where the money moves.
"""

from __future__ import annotations

import sys
from dataclasses import replace

from audit.fixtures.requirements import FIXTURES
from audit.phase0_triage import _requirement_for
from audit.phase3_consistency import BUDGETS, PROVIDERS, TIERS, _options, _shape


def main() -> int:
    print()
    print("PHASE 3 — BUDGET INVERSION: dearer at a lower budget?")
    print("=" * 78)
    found = []
    reqs = {f.id: _requirement_for(f) for f in FIXTURES}

    for fixture in FIXTURES:
        for provider in PROVIDERS:
            for tier in TIERS:
                costs = {}
                opts_by_budget = {}
                for budget in BUDGETS:
                    opts = _options(reqs[fixture.id], provider, budget)
                    if tier not in opts:
                        continue
                    costs[budget] = float(opts[tier].monthly)
                    opts_by_budget[budget] = opts[tier]
                if len(costs) < 2:
                    continue
                ordered = [costs[b] for b in sorted(costs)]
                # Inverted = a LOWER budget produced a HIGHER cost.
                if ordered[0] > ordered[-1] * 1.001:
                    found.append((fixture, provider, tier, costs, opts_by_budget))

    if not found:
        print("  none — cost never rises as the budget falls")
        return 0

    print(f"{'fixture':<8}{'provider':<9}{'tier':<16}" + "".join(f"{f'${b:,.0f}':>13}" for b in BUDGETS))
    print("-" * 78)
    for fixture, provider, tier, costs, _ in found:
        row = "".join(f"{costs.get(b, 0):>13,.2f}" for b in BUDGETS)
        print(f"{fixture.id:<8}{provider:<9}{tier:<16}{row}")

    print()
    print("MECHANISM — what differs between the cheapest and dearest run")
    print("=" * 78)
    for fixture, provider, tier, costs, opts in found:
        lo, hi = min(costs, key=costs.get), max(costs, key=costs.get)
        print()
        print(f"{fixture.id}/{provider}/{tier}: ${costs[hi]:,.2f} at ${hi:,.0f} budget "
              f"vs ${costs[lo]:,.2f} at ${lo:,.0f}")

        a, b = _shape(opts[hi]), _shape(opts[lo])
        moved = {k: (a[k], b[k]) for k in a if a[k] != b[k]}
        print(f"  spec: " + ("  ".join(f"{k} {v[0]}->{v[1]}" for k, v in moved.items()) or "IDENTICAL"))

        # The line items are where the money actually is. A spec that shrank
        # while the bill grew means the SKU changed underneath it.
        la = {i.label: (i.sku, float(i.monthly_usd)) for i in opts[hi].estimate.items}
        lb = {i.label: (i.sku, float(i.monthly_usd)) for i in opts[lo].estimate.items}
        deltas = []
        for label in set(la) | set(lb):
            sa, ca = la.get(label, ("—", 0.0))
            sb, cb = lb.get(label, ("—", 0.0))
            if abs(ca - cb) > 0.5:
                deltas.append((ca - cb, label, sa, sb, ca, cb))
        for d, label, sa, sb, ca, cb in sorted(deltas, key=lambda x: -abs(x[0]))[:6]:
            arrow = "" if sa == sb else f"   SKU {sb} -> {sa}"
            print(f"    {d:>+10,.2f}  {label:<38} {cb:>9,.2f} -> {ca:>9,.2f}{arrow}")

        print(f"  gave up at ${hi:,.0f}: {len(opts[hi].tradeoffs)} tradeoffs")
        for t in opts[hi].tradeoffs:
            if "budget" in t or "fit" in t:
                print(f"      · {t[:96]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
