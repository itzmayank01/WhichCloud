"""What DRIVES the C3 and C6 failures. Line-level, not tier-level.

A check that says "azure is 162% above the median" names a symptom. The
actionable form names the line, because that is what someone would go and
look at.
"""

from __future__ import annotations

import statistics
import sys
from collections import defaultdict

from audit.fixtures.requirements import FIXTURES
from audit.phase0_triage import _requirement_for
from audit.phase3_consistency import PROVIDERS, TIERS, _options


def main() -> int:
    reqs = {f.id: _requirement_for(f) for f in FIXTURES}

    print()
    print("C6 — WHICH LINE DRIVES THE CROSS-PROVIDER GAP")
    print("=" * 78)
    for fixture in FIXTURES:
        for tier in TIERS:
            opts = {p: _options(reqs[fixture.id], p).get(tier) for p in PROVIDERS}
            if any(o is None for o in opts.values()):
                continue
            totals = {p: float(o.monthly) for p, o in opts.items()}
            median = statistics.median(totals.values())
            worst = max(totals, key=lambda p: abs(totals[p] - median))
            spread = abs(totals[worst] - median) / median if median else 0
            if spread <= 0.40:
                continue

            print(f"\n{fixture.id}/{tier}   median {median:,.0f}   "
                  f"{worst} {totals[worst]:,.0f} ({spread:+.0%})")

            # Group each provider's lines by the diagram role they pay for, so
            # "Compute" on one cloud lines up with "Compute" on another even
            # when the SKUs share no vocabulary at all.
            from whichcloud import topology
            by_group = {}
            for p, o in opts.items():
                topo = topology.build(o.spec, o.estimate, o.applied)
                sums = defaultdict(float)
                for item in o.estimate.items:
                    sums[topology._kind_for(item)] += float(item.monthly_usd)
                by_group[p] = sums

            others = [p for p in PROVIDERS if p != worst]
            gaps = []
            for group in set().union(*(set(v) for v in by_group.values())):
                mine = by_group[worst].get(group, 0.0)
                theirs = statistics.median([by_group[p].get(group, 0.0) for p in others])
                gaps.append((mine - theirs, group, mine, theirs))
            for delta, group, mine, theirs in sorted(gaps, key=lambda g: -abs(g[0]))[:4]:
                print(f"    {delta:>+10,.2f}  {group:<18} {worst} {mine:>9,.2f}  "
                      f"vs others {theirs:>9,.2f}")

    print()
    print()
    print("C3 — WHERE MONOTONICITY BREAKS")
    print("=" * 78)
    for fixture in FIXTURES:
        for provider in PROVIDERS:
            opts = _options(reqs[fixture.id], provider)
            costs = [(t, float(opts[t].monthly)) for t in TIERS if t in opts]
            for (ta, ca), (tb, cb) in zip(costs, costs[1:]):
                if ca <= cb:
                    continue
                print(f"\n{fixture.id}/{provider}: {ta} {ca:,.2f} > {tb} {cb:,.2f}")
                la = {i.label: float(i.monthly_usd) for i in opts[ta].estimate.items}
                lb = {i.label: float(i.monthly_usd) for i in opts[tb].estimate.items}
                diffs = [
                    (lb.get(k, 0.0) - la.get(k, 0.0), k, la.get(k, 0.0), lb.get(k, 0.0))
                    for k in set(la) | set(lb)
                ]
                for d, k, a, b in sorted(diffs, key=lambda x: x[0])[:4]:
                    print(f"    {d:>+10,.2f}  {k:<38} {a:>9,.2f} -> {b:>9,.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
